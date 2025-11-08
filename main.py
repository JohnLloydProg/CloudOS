import customtkinter as ctk
from objects import User
from firebase import Firebase
from scheduling import Computer
from desktop.login import LoginWindow
from desktop.taskbar import Taskbar
from desktop.desktop import Desktop
from desktop.splash import SplashScreen
from threading import Thread
from dotenv import load_dotenv
import os
import sys
from tkinter import font as tkfont


#WINDOW_W, WINDOW_H = 1200, 720

def create_root():
    app = ctk.CTk()
    app.overrideredirect(True)
    app.geometry(f"{app.winfo_screenwidth()}x{app.winfo_screenheight()}+0+0")

    return app

def load_custom_fonts():
    """Register bundled TTF fonts (Gaegu) for this process."""
    if not sys.platform.startswith("win"):
        return  # current hack is Windows-only; safe no-op elsewhere

    try:
        from ctypes import windll, c_wchar_p

        FR_PRIVATE = 0x10  # only this

        gaegu_path = os.path.abspath(os.path.join("assets", "fonts", "Gaegu-Regular.ttf"))

        added = windll.gdi32.AddFontResourceExW(
            c_wchar_p(gaegu_path),
            FR_PRIVATE,
            None
        )

        if added == 0:
            print("Failed to register Gaegu font:", gaegu_path)
        else:
            print("Gaegu font registered.")
    except Exception as e:
        print("Error loading custom fonts:", e)

def main():
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("green")

    computer = Computer()
    firebase = Firebase(computer)
    app = create_root()
    load_custom_fonts()

    # base layout
    app.grid_rowconfigure(0, weight=1)
    app.grid_columnconfigure(0, weight=1)

    # start fully transparent so we can fade in to login
    app.attributes("-alpha", 0.0)

    # ---------- Fade helper ---------------------------------------------
    def fade_transition(fade_out=True, step=0.05, delay=15, callback=None):
        """
        Generic fade:
        - if fade_out=True: alpha 1 -> 0, run callback at 0, then fade back 0 -> 1
        - if fade_out=False: alpha 0 -> 1 only (no callback)
        """
        alpha = float(app.attributes("-alpha"))

        if fade_out:
            # fade 1 -> 0
            if alpha > 0:
                new_alpha = max(0.0, alpha - step)
                app.attributes("-alpha", new_alpha)
                app.after(delay, lambda: fade_transition(True, step, delay, callback))
            else:
                # at 0: swap content
                if callback:
                    callback()
                # then fade back in
                app.after(delay, lambda: fade_transition(False, step, delay, None))
        else:
            # fade 0 -> 1
            if alpha < 1:
                new_alpha = min(1.0, alpha + step)
                app.attributes("-alpha", new_alpha)
                app.after(delay, lambda: fade_transition(False, step, delay, None))
            else:
                app.attributes("-alpha", 1.0)

    # ---------- Desktop builder -----------------------------------------
    def build_desktop(user:User):
        """Create the desktop UI (no fade logic here; handled outside)."""
        # clear everything
        for w in app.winfo_children():
            w.destroy()

        # layout for taskbar + desktop
        for i in range(3):
            app.grid_rowconfigure(i, weight=0)
            app.grid_columnconfigure(i, weight=0)

        app.grid_rowconfigure(0, weight=1)
        app.grid_columnconfigure(0, weight=0)  # taskbar
        app.grid_columnconfigure(1, weight=1)  # desktop

        app.title("Grass – Desktop")

        taskbar = Taskbar(app)
        taskbar.grid(row=0, column=0, sticky="nsw", padx=8, pady=8)

        desktop = Desktop(app, firebase, user)
        desktop.grid(row=0, column=1, sticky="nsew", padx=(0, 8), pady=8)

        # ----- Logout -> back to login with fade + no splash --------------
        def logout_to_login():
            def rebuild_login():
                # clear everything
                for w in app.winfo_children():
                    w.destroy()

                # reset grid used by desktop
                for i in range(3):
                    app.grid_rowconfigure(i, weight=0)
                    app.grid_columnconfigure(i, weight=0)

                app.grid_rowconfigure(0, weight=1)
                app.grid_columnconfigure(0, weight=1)

                app.title("Login")
                LoginWindow(app, firebase, on_success=start_splash_sequence)


            fade_transition(fade_out=True, callback=rebuild_login)

        # wire taskbar callbacks
        if hasattr(taskbar, "on_toggle_files"):
            taskbar.on_toggle_files = lambda: desktop.close_window() if desktop.active else desktop.show_file_manager()
        if hasattr(taskbar, "on_logout"):
            taskbar.on_logout = logout_to_login
        if hasattr(taskbar, "on_shutdown"):
            taskbar.on_shutdown = app.destroy

    # ---------- Login -> Splash -> Desktop chain -------------------------
    def start_splash_sequence(user:User):

        def show_splash():
            # clear login widgets
            for w in app.winfo_children():
                w.destroy()

            # single-cell for splash
            app.grid_rowconfigure(0, weight=1)
            app.grid_columnconfigure(0, weight=1)
            app.title("Loading…")

            # when splash completes, we trigger fade -> desktop
            def splash_done():
                build_desktop(user)

            splash = SplashScreen(app, duration=3000, on_done=splash_done)
            splash.grid(row=0, column=0, sticky="nsew")

        # do: fade out login, swap to splash, fade in splash
        fade_transition(fade_out=True, callback=show_splash)

    # ---------- Initial: fade -> login -----------------------------------
    def show_login_initial():
        for w in app.winfo_children():
            w.destroy()

        for i in range(3):
            app.grid_rowconfigure(i, weight=0)
            app.grid_columnconfigure(i, weight=0)

        app.grid_rowconfigure(0, weight=1)
        app.grid_columnconfigure(0, weight=1)
        app.title("Welcome")

        LoginWindow(app, firebase, on_success=start_splash_sequence)

        fade_transition(fade_out=False)


    # build login immediately (invisible), then fade in
    show_login_initial()

    
    process = Thread(target=computer.run, daemon=True)
    app.after(100, lambda: process.start())
    app.mainloop()


if __name__ == "__main__":
    load_dotenv()
    main()
