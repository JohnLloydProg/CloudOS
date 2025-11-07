import customtkinter as ctk
from PIL import Image
from .file_manager import FileManager
import math, time

WINDOW_W, WINDOW_H = 1040, 600   # default fallback size
# Window size ratios (fraction of available desktop area)
# Adjust these to control how much of the desktop the floating window occupies.
WINDOW_WIDTH_RATIO = 0.75  # 70-80% requested; default to 75%
WINDOW_HEIGHT_RATIO = 0.80

class Desktop(ctk.CTkFrame):
    """Desktop with bg image and a closeable floating window."""
    def __init__(self, parent):
        # Use transparent background so rounded child windows show the
        # desktop background image — this prevents dark/black bleed in the
        # rounded corners.
        super().__init__(parent, fg_color="transparent")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Background image (keep original PIL image to allow dynamic resizing)
        bg_path = "assets/bg_final.png"
        try:
            self._bg_pil = Image.open(bg_path).convert("RGBA")
        except Exception:
            self._bg_pil = None
        # create an initial CTkImage (will be updated on first configure)
        if self._bg_pil is not None:
            self._bg_ctkimg = ctk.CTkImage(light_image=self._bg_pil, dark_image=self._bg_pil, size=(1200, 720))
        else:
            self._bg_ctkimg = None
        self._bg_label = ctk.CTkLabel(self, text="", image=self._bg_ctkimg)
        self._bg_label.place(relx=0, rely=0, relwidth=1, relheight=1)

        # keep background responsive to parent size (handles maximize)
        self.bind("<Configure>", lambda e: self._update_background())

        # Floating window (hidden/shown with place/forget)
        self.window = ctk.CTkFrame(self, fg_color="#f7fbf6", corner_radius=24,
                                   width=WINDOW_W, height=WINDOW_H)
        self.window.grid_propagate(False)

        # Title bar
        top = ctk.CTkFrame(self.window, fg_color="#d5e6cf", corner_radius=24, height=40)
        # Inset the title bar so the outer window's rounded corners remain
        # visible (prevents square/white corners at the very top edges).
        top.pack(fill="x", padx=12, pady=(12, 0))
        ctrl = ctk.CTkFrame(top, fg_color="transparent")
        ctrl.pack(side="right", padx=12, pady=6)
        close_btn = ctk.CTkButton(
            ctrl, text="✕", width=28, height=24,
            fg_color="transparent", hover_color="#eaf3e7",
            text_color="#7a946f", corner_radius=8,
            command=self.close_window
        )
        close_btn.pack(side="left", padx=4)

        # Client area
        self.client = ctk.CTkFrame(self.window, fg_color="transparent")
        self.client.pack(fill="both", expand=True, padx=12, pady=12)

        self.active = None
        self._window_visible = False
        self.show_file_manager()  # start visible

    def _center_place(self):
        # get available desktop width/height
        avail_w = self.winfo_width()
        avail_h = self.winfo_height()

        # If layout isn't ready yet (often width==1 on initial pack), retry shortly.
        if not avail_w or avail_w <= 1 or not avail_h or avail_h <= 1:
            # schedule a retry after a short delay to let the layout finish
            try:
                self.after(50, self._center_place)
            except Exception:
                pass
            return

        # Use relative placement so the window reliably spans the requested
        # fraction of the Desktop frame even while layout changes.
        rel_w = WINDOW_WIDTH_RATIO
        rel_h = WINDOW_HEIGHT_RATIO
        rel_x = (1.0 - rel_w) / 2.0
        rel_y = (1.0 - rel_h) / 2.0

        # Place using relwidth/relheight to fill the requested portion of the
        # parent. This avoids passing absolute width/height to place (which
        # customtkinter warns about) and keeps the window responsive.
        self.window.place(relx=rel_x, rely=rel_y, relwidth=rel_w, relheight=rel_h)
        self._window_visible = True

    def _update_background(self, _evt=None):
        if not self._bg_pil:
            return
        try:
            win_w = max(1, self.winfo_width())
            win_h = max(1, self.winfo_height())

            img_w, img_h = self._bg_pil.size
            img_ratio = img_w / img_h
            win_ratio = win_w / win_h

            # Fit entire image (no crop)
            if win_ratio > img_ratio:
                # window wider → fit height
                new_h = win_h
                new_w = int(new_h * img_ratio)
            else:
                # window taller → fit width
                new_w = win_w
                new_h = int(new_w / img_ratio)

            # Center the fitted image
            x_off = (win_w - new_w) // 2
            y_off = (win_h - new_h) // 2

            resized = self._bg_pil.resize((new_w, new_h), Image.LANCZOS)
            canvas = Image.new("RGBA", (win_w, win_h), (247, 251, 246, 255))  # same green bg
            canvas.paste(resized, (x_off, y_off))

            self._bg_ctkimg = ctk.CTkImage(light_image=canvas, dark_image=canvas, size=(win_w, win_h))
            self._bg_label.configure(image=self._bg_ctkimg)
        except Exception:
            pass

    def show_window(self):
        """Fade + slide in the floating window."""
        if not self._window_visible:
            self._animate_slide_in(duration=120, fps=25, offset=0.03)

    def close_window(self):
        """Fade + slide out the floating window."""
        if self._window_visible:
            self._animate_slide_out(duration=120, fps=25, offset=0.03)

    def show_file_manager(self):
        self.show_window()
        if self.active:
            self.active.destroy()
        self.active = FileManager(self.client)
        self.active.pack(fill="both", expand=True)

    # --- Animations -------------------------------------------------------
    def _animate_slide_in(self, duration=250, fps=30, offset=0.05):
        """Smoothly slide the floating window upward into view."""
        frames = int((duration / 1000) * fps)
        frame = 0
        start_rely = 0.5 - WINDOW_HEIGHT_RATIO / 2 + offset
        end_rely = 0.5 - WINDOW_HEIGHT_RATIO / 2

        # start slightly below center
        self.window.place(relx=0.5 - WINDOW_WIDTH_RATIO / 2,
                          rely=start_rely,
                          relwidth=WINDOW_WIDTH_RATIO,
                          relheight=WINDOW_HEIGHT_RATIO)
        self.window.lift()
        self._window_visible = True

        def animate():
            nonlocal frame
            progress = min(1.0, frame / frames)
            ease = 1 - math.cos((progress * math.pi) / 2)  # ease-out
            new_y = start_rely - (offset * ease)
            self.window.place_configure(rely=new_y)
            if progress < 1.0:
                frame += 1
                self.after(int(1000 / fps), animate)
            else:
                self.window.place_configure(rely=end_rely)

        animate()

    def _animate_slide_out(self, duration=200, fps=30, offset=0.05):
        frames = int((duration / 1000) * fps)
        frame = 0
        start_rely = 0.5 - WINDOW_HEIGHT_RATIO / 2
        end_rely = start_rely + offset

        def animate():
            nonlocal frame
            progress = min(1.0, frame / frames)
            ease = math.sin((progress * math.pi) / 2)  # ease-in
            new_y = start_rely + (offset * ease)
            self.window.place_configure(rely=new_y)

            if progress < 1.0:
                frame += 1
                self.after(int(1000 / fps), animate)
            else:
                # window finished sliding; small delay before hiding
                self.after(80, lambda: self.window.place_forget())
                self._window_visible = False

        animate()
