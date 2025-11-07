import customtkinter as ctk
from PIL import Image, ImageSequence
from tkinter import font as tkfont

# Palette
GREEN_0 = "#f2f8d3"
TEXT_1  = "#4e6133"

WINDOW_W, WINDOW_H = 1200, 720


class SplashScreen(ctk.CTkFrame):
    """
    Full-window splash screen.

    - Shows a centered animated GIF from assets/splash.gif (if available)
    - Animates a short welcome/loading text under it
    - After `duration` ms, calls on_done() to switch to the next screen
    """

    def __init__(self, master, duration: int = 3000, on_done=None):
        super().__init__(master, fg_color=GREEN_0)
        self.master = master
        self.on_done = on_done
        self.duration = duration

        # Animation state
        self._frames = []
        self._delay = 80           # default GIF frame delay (ms)
        self._frame_index = 0
        self._gif_job = None

        self._dot_count = 0
        self._text_job = None

        # Layout: center container
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        container = ctk.CTkFrame(self, fg_color="transparent")
        container.grid(row=0, column=0, sticky="nsew")
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        inner = ctk.CTkFrame(container, fg_color="transparent")
        inner.grid(row=0, column=0)

        # GIF label (image assigned after load)
        self.gif_label = ctk.CTkLabel(inner, text="")
        self.gif_label.pack(pady=(0, 8))

        # Choose font for welcome/loading text (use Gaegu if available)
        if "Gaegu" in tkfont.families():
            text_font = ctk.CTkFont(family="Gaegu", size=36, weight="bold")
        else:
            text_font = ctk.CTkFont(size=20, weight="bold")

        # Loading / welcome text (animated with dots)
        self.text_label = ctk.CTkLabel(
            inner,
            text="Welcome",
            text_color=TEXT_1,
            font=text_font,
        )
        self.text_label.pack()

        # Load GIF frames & start animations
        self._load_gif("assets/splash.gif")

        if self._frames:
            self._animate_gif()

        self._animate_text()

        # Schedule finish
        self.after(self.duration, self._finish)

    # ---------- GIF handling ---------------------------------------------

    def _load_gif(self, path: str):
        """Load all frames of the GIF at `path` into self._frames."""
        try:
            gif = Image.open(path)
        except Exception as e:
            print(f"[SplashScreen] Could not load GIF '{path}': {e}")
            self._frames = []
            return

        # Use GIF's own frame delay if available
        self._delay = gif.info.get("duration", 80)

        frames = []
        for frame in ImageSequence.Iterator(gif):
            frm = frame.convert("RGBA")
            w, h = frm.size
            ctk_img = ctk.CTkImage(light_image=frm, dark_image=frm, size=(w, h))
            frames.append(ctk_img)

        self._frames = frames

    def _animate_gif(self):
        """Cycle through GIF frames."""
        if not self._frames:
            return

        self.gif_label.configure(image=self._frames[self._frame_index])
        self._frame_index = (self._frame_index + 1) % len(self._frames)
        self._gif_job = self.after(self._delay, self._animate_gif)

    # ---------- Text animation -------------------------------------------

    def _animate_text(self):
        """Animate a simple 'Welcome' with pulsing symbols."""
        self.text_label.configure(text="Welcome " + "꩜ " * self._dot_count)
        self._dot_count = (self._dot_count + 1) % 4  # cycles 0–3
        self._text_job = self.after(400, self._animate_text)

    # ---------- Finish ----------------------------------------------------

    def _finish(self):
        """Stop animations and trigger the next screen."""
        # Stop GIF loop
        if self._gif_job is not None:
            try:
                self.after_cancel(self._gif_job)
            except Exception:
                pass
            self._gif_job = None

        # Stop text loop
        if self._text_job is not None:
            try:
                self.after_cancel(self._text_job)
            except Exception:
                pass
            self._text_job = None

        # Switch to next screen
        if callable(self.on_done):
            self.on_done()

        # Remove splash from view
        self.destroy()
