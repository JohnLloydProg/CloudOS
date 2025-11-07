import customtkinter as ctk

class Taskbar(ctk.CTkFrame):
    def __init__(self, master, **kw):
        super().__init__(master, fg_color="transparent", corner_radius=0, width=56, **kw)
        self.grid_propagate(False)

        # external callbacks injected by app.py
        self.on_toggle_files = None
        self.on_shutdown = None
        self.on_logout = None

        # local state for toggle
        self.files_active = True   # start with FM visible; flip if you want default hidden

        self.emoji_font = ctk.CTkFont(size=28)  # large emojis

        btn = dict(
            width=48, height=48, corner_radius=8,
            fg_color="#b7db75",                
            hover_color=("#e9f3e9", "#2a3b2a"),
            text_color=("#1b1f1b", "white"),
            font=self.emoji_font
        )

        # Files (toggle)
        self.btn_files = ctk.CTkButton(self, text="📁", **btn, command=self._toggle_files)
        self.btn_files.grid(row=0, column=0, padx=4, pady=(8, 6))

        # Logout (optional hook)
        self.btn_logout = ctk.CTkButton(self, text="⇦", **btn, command=self._logout)
        self.btn_logout.grid(row=1, column=0, padx=4, pady=6)

        # Power (exit app)
        self.btn_power = ctk.CTkButton(self, text="⏻", **btn, command=self._shutdown)
        self.btn_power.grid(row=100, column=0, padx=4, pady=(6, 10))

        # initial visual state for files button
        self._style_files_button()

    # --- Button handlers -------------------------------------------------
    def _toggle_files(self):
        if callable(self.on_toggle_files):
            self.on_toggle_files()
        self._style_files_button()

    def _logout(self):
        if callable(self.on_logout):
            self.on_logout()

    def _shutdown(self):
        if callable(self.on_shutdown):
            self.on_shutdown()

    # --- Visual state ----------------------------------------------------
    def _style_files_button(self):
        """Subtle filled background when File Manager is active."""
        if self.files_active:
            # small soft fill to indicate 'on'
            self.btn_files.configure(fg_color=("#b7db75", "#2a3b2a"))
        else:
            self.btn_files.configure(fg_color="#b7db75")