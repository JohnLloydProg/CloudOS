import customtkinter as ctk
from firebase import Firebase
from PIL import Image
from tkinter import font as tkfont

WINDOW_W, WINDOW_H = 1200, 720

# --- Meadow Login Palette ------------------------------------------------
GREEN_0 = "#f8fdf5"   
GREEN_1 = "#e7f6e3"   
GREEN_2 = "#c4e6ba"   
TEXT_1  = "#5b7a4a"   
TEXT_2  = "#8aaa7a"   

class LoginWindow(ctk.CTkFrame):
    def __init__(self, master, firebase:Firebase, on_success=None):
        super().__init__(master, fg_color="transparent")
        self.on_success = on_success
        self.firebase = firebase

        # Make this frame fill the root
        master.grid_rowconfigure(0, weight=1)
        master.grid_columnconfigure(0, weight=1)
        self.grid(row=0, column=0, sticky="nsew")

        # --- Variables ----------------------------------------------------
        self.username_var = ctk.StringVar(value="")
        self.password_var = ctk.StringVar(value="")

        # --- Background (match Desktop) -----------------------------------
        self._bg_pil = None
        self._bg_img = None

        # Background label (initially solid if image fails)
        self.bg_label = ctk.CTkLabel(
            self,
            text="",
            fg_color=GREEN_1,
        )
        self.bg_label.place(relx=0, rely=0, relwidth=1, relheight=1)

        # Try to load background after widget is realized
        self.after(10, self._load_background)

        # Keep bg responsive if window size changes
        self.bind("<Configure>", self._update_background)

        # --- Center login card (same style as previous) -------------------
        # --- Center login card (bigger & locked size) -------------------
        card_w, card_h = 420, 380  # significantly larger
        self.card = ctk.CTkFrame(
            self,
            fg_color=GREEN_0,
            corner_radius=28,
            width=card_w,
            height=card_h,
        )
        self.card.place(relx=0.5, rely=0.5, anchor="center")

        # Prevent CTk from shrinking the frame down to its children
        self.card.grid_propagate(False)

        # Card layout
        for r in range(8):
            self.card.grid_rowconfigure(r, weight=0)
        self.card.grid_rowconfigure(6, weight=1)  # spacer
        self.card.grid_columnconfigure(0, weight=1)


        if "Gaegu" in tkfont.families():
            title_font = ctk.CTkFont(family="Gaegu", size=56, weight="bold")
        else:
            title_font = ctk.CTkFont(size=36, weight="bold")
        
        subtitle_font = ctk.CTkFont(size=14)
        label_font = ctk.CTkFont(size=14)
        entry_font = ctk.CTkFont(size=14)
        btn_font = ctk.CTkFont(size=15, weight="bold")
        info_font = ctk.CTkFont(size=13)

        # Logo / Title
        ctk.CTkLabel(
            self.card,
            text="Ooh Green",
            font=title_font,
            text_color=TEXT_1,
        ).grid(row=0, column=0, pady=(26, 2), sticky="n")

        ctk.CTkLabel(
            self.card,
            text="Sign in",
            font=subtitle_font,
            text_color=TEXT_2,
        ).grid(row=1, column=0, pady=(0, 18), sticky="n")

        pad_x = 40

        # Username
        ctk.CTkLabel(
            self.card,
            text="Username",
            font=label_font,
            text_color=TEXT_1,
        ).grid(row=2, column=0, sticky="w", padx=pad_x, pady=(4, 0))

        self.ent_user = ctk.CTkEntry(
            self.card,
            textvariable=self.username_var,
            font=entry_font,
            fg_color=GREEN_1,
            border_color=GREEN_2,
            border_width=1,
            corner_radius=12,
            text_color=TEXT_1,
        )
        self.ent_user.grid(
            row=3,
            column=0,
            sticky="ew",
            padx=pad_x,
            pady=(2, 10),
        )

        # Password
        ctk.CTkLabel(
            self.card,
            text="Password",
            font=label_font,
            text_color=TEXT_1,
        ).grid(row=4, column=0, sticky="w", padx=pad_x, pady=(4, 0))

        self.ent_pass = ctk.CTkEntry(
            self.card,
            textvariable=self.password_var,
            show="●",
            font=entry_font,
            fg_color=GREEN_1,
            border_color=GREEN_2,
            border_width=1,
            corner_radius=12,
            text_color=TEXT_1,
        )
        self.ent_pass.grid(
            row=5,
            column=0,
            sticky="ew",
            padx=pad_x,
            pady=(2, 14),
        )

        # Info / feedback label
        self.info = ctk.CTkLabel(
            self.card,
            text="",
            text_color=TEXT_2,
            font=info_font,
        )
        self.info.grid(row=6, column=0, pady=(0, 8), sticky="n")

        # Login button
        btn_frame = ctk.CTkFrame(self.card, fg_color="transparent")
        btn_frame.grid(row=7, column=0, pady=(10, 32))
        btn_frame.grid_columnconfigure(0, weight=1)

        login_btn = ctk.CTkButton(
            btn_frame,
            text="Login",
            width=200,
            height=40,
            font=btn_font,
            fg_color=GREEN_2,
            hover_color="#eef6ec",
            text_color=TEXT_1,
            corner_radius=18,
            command=self._on_login,
        )
        login_btn.grid(row=0, column=0)

        # Bind Enter on fields (NO bind_all to avoid CTk error)
        self.ent_user.bind("<Return>", lambda e: self._on_login())
        self.ent_pass.bind("<Return>", lambda e: self._on_login())

        # Focus username when ready
        self.after(50, lambda: self.ent_user.focus_set())

    # --- Background handling ----------------------------------------------
    def _load_background(self):
        try:
            self._bg_pil = Image.open("assets/bg_try.jpg").convert("RGBA")
            w = max(1, self.winfo_width())
            h = max(1, self.winfo_height())
            img = self._bg_pil.resize((w, h), Image.LANCZOS)
            self._bg_img = ctk.CTkImage(
                light_image=img,
                dark_image=img,
                size=(w, h),
            )
            self.bg_label.configure(image=self._bg_img, fg_color="transparent")
        except Exception:
            # If it fails, we just keep the solid GREEN_1 background
            self._bg_pil = None
            self._bg_img = None

    def _update_background(self, _evt=None):
        """Resize bg when window/frame size changes."""
        if not self._bg_pil:
            return
        try:
            w = max(1, self.winfo_width())
            h = max(1, self.winfo_height())
            img = self._bg_pil.resize((w, h), Image.LANCZOS)
            self._bg_img = ctk.CTkImage(
                light_image=img,
                dark_image=img,
                size=(w, h),
            )
            self.bg_label.configure(image=self._bg_img)
        except Exception:
            pass

    # --- Login logic ------------------------------------------------------
    def _on_login(self):
        """Handle login click. Accept any credentials for now."""
        email = self.username_var.get().strip()
        pwd = self.password_var.get()

        user = self.firebase.login(email, pwd)

        if callable(self.on_success) and user:
            try:
                # Let app.py decide what to do (and when to destroy this frame)
                self.firebase.clean_at_exit(user)
                self.on_success(user)
            except Exception as e:
                self.info.configure(text=f"Login callback error: {e}")
                return


