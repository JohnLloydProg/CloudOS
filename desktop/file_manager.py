import customtkinter as ctk
from typing import Callable
from tkinter import filedialog, simpledialog
from decorators import decode_illegal_symbols
from firebase import Firebase
from objects import User
from PIL import Image, ImageOps
import datetime as _dt
from pathlib import Path
from tkinter import font as tkfont
import os

# --- Palette -------------------------------------------------------------
GREEN_0 = "#f2f8d3"   
GREEN_1 = "#eaf4c8"   
GREEN_2 = "#b7db75"   
BORDER   = "#97b853"  
TEXT_1  = "#4e6133"   
TEXT_2  = "#6c8340"   
ACCENT  = "#a6cf60"   

# --- Assets / icons (optional PNGs; emojis are fallbacks) ----------------
ASSETS = Path("assets")
ICON_DIR = ASSETS / "icons"
ICON_COLOR = TEXT_1
ICON_SIZE_GRID = (64, 64)
ICON_SIZE_LIST = (22, 22)

TYPE_META = {
    "folder": ("folder", "📁"),
    "image":  ("image",  "🖼️"),
    "audio":  ("audio",  "🎵"),
    "video":  ("video",  "🎞️"),
    "text":   ("text",   "📄"),
    "file":   ("file",   "📄"),
}

def _shorten_name(name: str, max_chars: int = 14) -> str:
    """
    Return a display name that keeps the beginning (so 'sleepy...' is visible)
    and trims from the tail if too long. Keeps extension when possible.
    """
    if len(name) <= max_chars:
        return name

    stem, ext = os.path.splitext(name)
    ext = ext[:5]  # safety cap

    # space for stem + "..." + ext
    keep = max_chars - len(ext) - 3
    if keep <= 3:
        # fallback: just cut raw and add ...
        return name[:max_chars - 3] + "..."

    return stem[:keep] + "..." + ext


def _guess_type(name: str, is_dir: bool) -> str:
    if is_dir: return "folder"
    ext = Path(name).suffix.lower()
    if ext in {".png",".jpg",".jpeg",".gif",".bmp",".webp"}: return "image"
    if ext in {".mp3",".wav",".flac",".m4a",".ogg"}:         return "audio"
    if ext in {".mp4",".mov",".avi",".mkv",".webm"}:         return "video"
    if ext in {".txt",".md",".rtf",".pdf",".py",".js"}:      return "text"
    return "file"

def _tinted_ctkimage_from_png(path: Path, size):
    """Load PNG, make it monochrome with ICON_COLOR, return CTkImage."""
    img = Image.open(path).convert("RGBA")
    gray = ImageOps.grayscale(img)
    colorized = ImageOps.colorize(gray, black=(0,0,0,0), white=ICON_COLOR)
    colorized.putalpha(img.split()[-1])  # keep alpha
    colorized = colorized.resize(size, Image.LANCZOS)
    return ctk.CTkImage(light_image=colorized, dark_image=colorized, size=size)

# ========================================================================

class FileManager(ctk.CTkFrame):
    """Compact file manager with Back ←, path text, and list/grid toggle."""
    def __init__(self, parent:ctk.CTkFrame, firebase:Firebase, user:User, on_text_file:Callable):
        super().__init__(parent, fg_color=GREEN_0, corner_radius=16)
        self.firebase = firebase
        self.user = user
        self.parent = parent
        self.on_text_file = on_text_file
        self.clicked = None

        # Fonts (create after root exists)
                # Fonts (create after root exists)
        # Gaegu: only for file/folder names
        if "Gaegu" in tkfont.families():
            self.FONT_NAME      = ctk.CTkFont(family="Gaegu", size=18)
            self.FONT_NAME_BIG  = ctk.CTkFont(family="Gaegu", size=20, weight="bold")
        else:
            self.FONT_NAME      = ctk.CTkFont(size=18)
            self.FONT_NAME_BIG  = ctk.CTkFont(size=20, weight="bold")

        # UI fonts: used for buttons, path bar, size/date, etc.
        self.FONT_UI      = ctk.CTkFont(size=13)
        self.FONT_UI_SM   = ctk.CTkFont(size=12)
        self.FONT_UI_HDG  = ctk.CTkFont(size=14, weight="bold")


        self.view_mode = "grid"      # default: grid
        self.entries = []
        self.path = "/"
        self.history = []            # stack of previous paths

        self._selected_widget = None
        self.selected = None   # (kind, name)

        # Performance helpers
        self._render_after_id = None
        self._rendering = False
        self._icon_cache = {}        # {(kind, size_tuple): CTkImage}
        # Selection tracking for clickable items (row/cell)
        self._selected_widget = None

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._build_topbar()
        self._build_browser()

        self.load_directory("/")  # demo data (replace via load_directory)
        self._render()

        # Debounced reflow on width changes
        self.bind("<Configure>", self._on_configure)

    # --- Top bar:  [←]  /current/path  [☷][⬚] ---------------------------
    def _build_topbar(self):
        bar = ctk.CTkFrame(self, fg_color=GREEN_2, corner_radius=14, height=42)
        bar.grid(row=0, column=0, sticky="ew", padx=6, pady=(6,6))

        # 3 columns: [Back] [Address (expands)] [View toggles]
        bar.grid_columnconfigure(0, weight=0)
        bar.grid_columnconfigure(1, weight=0)
        bar.grid_columnconfigure(2, weight=0)
        bar.grid_columnconfigure(3, weight=0)
        bar.grid_columnconfigure(4, weight=0)
        bar.grid_columnconfigure(5, weight=1)   # address expands
        bar.grid_columnconfigure(6, weight=0)

        # Back
        self.btn_back = ctk.CTkButton(
            bar, text="←", width=40, height=30, font=self.FONT_UI_SM,
            fg_color=GREEN_1, hover_color="#eef6ec", text_color=TEXT_1,
            corner_radius=12, command=self.go_back
        )
        self.btn_back.grid(row=0, column=0, padx=(10,8), pady=6)

        self.delete_btn = ctk.CTkButton(
            bar,
            text="🗑",
            width=40,                 
            height=30,
            fg_color=GREEN_1,   
            hover_color="#eef6ec",    
            text_color=TEXT_1,
            font=self.FONT_UI_SM,
            corner_radius=12,
            command=self.delete_selected,
        )
        self.delete_btn.grid(row=0, column=1, padx=(4, 2), pady=10, sticky="w")

        self.upload_btn = ctk.CTkButton(
            bar,
            text="↑",
            width=40,                 
            height=30,
            fg_color=GREEN_1,   
            hover_color="#eef6ec",    
            text_color=TEXT_1,
            font=self.FONT_UI_SM,
            corner_radius=12,
            command=self.upload,
        )
        self.upload_btn.grid(row=0, column=2, padx=(4, 2), pady=10, sticky="w")

        self.folder_btn = ctk.CTkButton(
            bar,
            text="📁",
            width=40,                 
            height=30,
            fg_color=GREEN_1,   
            hover_color="#eef6ec",    
            text_color=TEXT_1,
            font=self.FONT_UI_SM,
            corner_radius=12,
            command=self.create_folder,
        )
        self.folder_btn.grid(row=0, column=3, padx=(4, 2), pady=10, sticky="w")

        self.editor_btn = ctk.CTkButton(
            bar,
            text="txt",
            width=40,                 
            height=30,
            fg_color=GREEN_1,   
            hover_color="#eef6ec",    
            text_color=TEXT_1,
            font=self.FONT_UI_SM,
            corner_radius=12,
            command=lambda: self.on_text_file(self.path),
        )
        self.editor_btn.grid(row=0, column=4, padx=(4, 2), pady=10, sticky="w")



        # Address (full-width, read-only entry inside a rounded container)
        addr_wrap = ctk.CTkFrame(bar, fg_color=GREEN_1, corner_radius=12)
        addr_wrap.grid(row=0, column=5, sticky="ew", padx=8, pady=6)
        addr_wrap.grid_columnconfigure(0, weight=1)

        self.path_var = ctk.StringVar(value=self.path)
        self.addr_entry = ctk.CTkEntry(
            addr_wrap, textvariable=self.path_var, state="disabled",
            border_width=0, fg_color="transparent", text_color=TEXT_1,
            font=self.FONT_UI_SM
        )
        # pack to fill the pill so long paths remain visible
        self.addr_entry.grid(row=0, column=0, sticky="ew", padx=10, pady=6)

        # View toggles
        toggle = ctk.CTkFrame(bar, fg_color="transparent")
        toggle.grid(row=0, column=6, padx=(8,10))
        ctk.CTkButton(toggle, text="☷", width=32, height=28, font=self.FONT_UI_SM,
                    fg_color=GREEN_1, hover_color="#eef6ec", text_color=TEXT_1,
                    corner_radius=10, command=lambda: self._switch("list")
                    ).pack(side="left", padx=3)
        ctk.CTkButton(toggle, text="⬚", width=32, height=28, font=self.FONT_UI_SM,
                    fg_color=GREEN_1, hover_color="#eef6ec", text_color=TEXT_1,
                    corner_radius=10, command=lambda: self._switch("grid")
                    ).pack(side="left", padx=3)

    # --- Browser area -----------------------------------------------------
    def _build_browser(self):
        wrap = ctk.CTkFrame(self, fg_color=GREEN_0, corner_radius=16)
        wrap.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0,8))
        wrap.grid_rowconfigure(0, weight=1)
        wrap.grid_columnconfigure(0, weight=1)
        # Make the scrollable area use the same background and corner radius
        # as the surrounding wrapper so there are no visible white/rough
        # corners where the inner canvas meets the outer frame.
        # Use a transparent scrollable frame so the parent's rounded corners
        # remain visible and the internal canvas doesn't produce sharp rectangular
        # corners. Increase padding so content doesn't touch the rounded edges.
        self.scroll = ctk.CTkScrollableFrame(wrap, fg_color="transparent", corner_radius=16)
        self.scroll.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)

    # --- Navigation -------------------------------------------------------
    def open_folder(self, name: str):
        self.history.append(self.path)
        self.path = (self.path.rstrip("/") + "/" + name).replace("//", "/")
        self.load_directory(self.path)    # replace with backend list
        self._render()
        self.path_var.set(self.path)


    def go_back(self):
        if not self.history:
            return
        self.path = self.history.pop()
        self.load_directory(self.path)    # replace with backend list
        self._render()
        self.path_var.set(self.path)


    # --- Rendering --------------------------------------------------------
    def _clear(self):
        for w in self.scroll.winfo_children():
            w.destroy()

    def _switch(self, mode):
        if self.view_mode != mode:
            self.view_mode = mode
            self._render()

    def _on_configure(self, _evt):
        """Debounce reflow to avoid dozens of renders while resizing."""
        if self._render_after_id:
            try: self.after_cancel(self._render_after_id)
            except Exception: pass
        # schedule a single render after 120ms of inactivity
        self._render_after_id = self.after(120, self._render)

    def _render(self):
        if self._rendering:
            return
        self._rendering = True
        try:
            self._clear()

            # Empty state
            if not self.entries:
                empty = ctk.CTkLabel(
                    self.scroll,
                    text="No files here yet.",
                    text_color=TEXT_2,
                    font=self.FONT_UI_SM,
                )
                empty.pack(pady=24)
                return

            # LIST VIEW
            if self.view_mode == "list":
                for kind, name, size, date in self.entries:
                    self._row_list(kind, name, size, date)
                return

            # GRID VIEW
            grid = ctk.CTkFrame(self.scroll, fg_color="transparent")
            grid.pack(fill="both", expand=True, padx=2, pady=2)

            avail = self.scroll.winfo_width()
            if avail <= 1:
                # first layout pass: width not ready; try again shortly
                if self._render_after_id:
                    try:
                        self.after_cancel(self._render_after_id)
                    except Exception:
                        pass
                self._render_after_id = self.after(60, self._render)
                return

            card_min = 200
            cols = max(3, min(8, avail // card_min))

            for c in range(cols):
                grid.grid_columnconfigure(c, weight=1, uniform="g")

            for i, item in enumerate(self.entries):
                r, c = divmod(i, cols)
                self._cell_grid(grid, *item).grid(
                    row=r, column=c, padx=12, pady=12, sticky="n"
                )
        finally:
            self._rendering = False

    # --- Icons ------------------------------------------------------------
    def _get_icon_image(self, kind: str, size):
        key = (kind, size)
        if key in self._icon_cache:
            return self._icon_cache[key]
        png = ICON_DIR / f"{kind}.png"
        if png.exists():
            try:
                img = _tinted_ctkimage_from_png(png, size)
                self._icon_cache[key] = img
                return img
            except Exception:
                pass
        self._icon_cache[key] = None
        return None

    # --- Selection / activation helpers ---------------------------------
    def _select_widget(self, widget, kind, name):
        """Visually mark a widget as selected and remember which item it is."""
        # restore previous
        prev = getattr(self, "_selected_widget", None)
        if prev is not None and prev is not widget:
            try:
                prev.configure(fg_color=getattr(prev, "_default_fg", GREEN_1))
            except Exception:
                pass

        self._selected_widget = widget
        self.selected = (kind, name)
        self.clicked = (kind, name)

        try:
            widget.configure(fg_color="#dbead9")
        except Exception:
            pass

    def _open_item(self, kind, name):
        """Placeholder for opening an item. Folders will navigate now; files are TODO."""
        if kind == "folder":
            self.open_folder(name)
        else:
            # TODO: implement file open behavior (preview / external app)
            print(f"[open_item] would open: {name} (type={kind})")
            if (kind == "text"):
                self.on_text_file(f"{self.path.strip("/")}/{name}")

    # --- List row ---------------------------------------------------------
    def _row_list(self, kind, name, size, date):
        # Make list rows use same corner radius as grid cells for consistency
        row = ctk.CTkFrame(self.scroll, fg_color=GREEN_1, corner_radius=14)
        # remember default color so we can restore it after hover/selection
        row._default_fg = GREEN_1
        row.pack(fill="x", padx=4, pady=4)

        # Label container with same corner radius as parent
        lbl_wrap = ctk.CTkFrame(row, fg_color="transparent", corner_radius=14)
        lbl_wrap.pack(side="left", padx=8, pady=6)

        ico = self._get_icon_image(kind, ICON_SIZE_LIST)
        if ico:
            ctk.CTkLabel(lbl_wrap, text="", image=ico).pack(side="left")
        else:
            ctk.CTkLabel(lbl_wrap, text=TYPE_META[kind][1], text_color=TEXT_1, font=self.FONT_UI_HDG
                         ).pack(side="left")

        def on_click():
            if (self.clicked == (kind, name)):
                self._open_item(kind, name)
            self._select_widget(row, kind, name)
            self.parent.after(500, lambda: setattr(self, "clicked", None))

        # Button in rounded container (kept for accessibility) — clicking
        # anywhere on the row will also trigger the same action.
        btn_wrap = ctk.CTkFrame(row, fg_color="transparent", corner_radius=14)
        btn_wrap.pack(side="left", fill="x", expand=True, padx=2, pady=6)
        # inner button (use same hover color so it matches parent)
        ctk.CTkButton(btn_wrap, text=name, command=on_click,
                      fg_color="transparent", hover_color="#eef6ec",
                      text_color=TEXT_1, corner_radius=14, font=self.FONT_UI_SM
                      ).pack(fill="x")

        # Right-side info in rounded container (create before binding)
        info_wrap = ctk.CTkFrame(row, fg_color="transparent", corner_radius=14)
        info_wrap.pack(side="right", padx=10, pady=8)
        ctk.CTkLabel(info_wrap, text=size, text_color=TEXT_2, font=self.FONT_UI_SM).pack(side="left", padx=4)
        ctk.CTkLabel(info_wrap, text=date, text_color=TEXT_2, font=self.FONT_UI_SM).pack(side="left", padx=4)

        # make the entire row and all descendants clickable and hoverable
        def _on_enter(_e, w=row):
            try:
                if getattr(self, "_selected_widget", None) is not row:
                    row.configure(fg_color="#eef6ec")
            except Exception:
                pass
        def _on_leave(_e, w=row):
            try:
                if getattr(self, "_selected_widget", None) is not row:
                    row.configure(fg_color=getattr(row, "_default_fg", GREEN_1))
            except Exception:
                pass

        # bind the row and all its children so hovering any part affects the whole
        def bind_recursive(parent_widget):
            try:
                parent_widget.bind("<Button-1>", lambda e: on_click())
                parent_widget.bind("<Enter>", _on_enter)
                parent_widget.bind("<Leave>", _on_leave)
                # show pointer cursor on all bound widgets to indicate clickability
                try:
                    parent_widget.configure(cursor="hand2")
                except Exception:
                    pass
            except Exception:
                pass
            for ch in parent_widget.winfo_children():
                bind_recursive(ch)

        bind_recursive(row)

    # --- Grid cell (no fixed size; adapts to your current window width) ---
    def _cell_grid(self, parent, kind, name, size, date):
        cell = ctk.CTkFrame(parent, fg_color=GREEN_1, corner_radius=16)
        cell.grid_propagate(True)
        cell._default_fg = GREEN_1

        ico = self._get_icon_image(kind, ICON_SIZE_GRID)
        if ico:
            ctk.CTkLabel(cell, text="", image=ico).pack(padx=16, pady=(16,10))
        else:
            ctk.CTkLabel(cell, text=TYPE_META[kind][1], text_color=TEXT_1, font=self.FONT_UI_HDG
                         ).pack(padx=16, pady=(20,10))

        def on_click():
            if (self.clicked == (kind, name)):
                self._open_item(kind, name)
            self._select_widget(cell, kind, name)
            self.parent.after(500, lambda: setattr(self, "clicked", None))


        # Button in rounded container (kept for accessibility). Also bind
        # the entire cell so clicking anywhere activates it.
        btn_wrap = ctk.CTkFrame(cell, fg_color="transparent", corner_radius=14)
        btn_wrap.pack(padx=12, pady=(0,14), fill="x")
        display_name = _shorten_name(name, max_chars=14)
        ctk.CTkButton(btn_wrap, text=display_name, command=on_click,
                      fg_color="transparent", hover_color="#eef6ec",
                      text_color=TEXT_1, corner_radius=14, font=self.FONT_UI_SM
                      ).pack(fill="x")

        # hover and click bindings for whole cell
        def _on_enter_cell(_e, c=cell):
            try:
                if getattr(self, "_selected_widget", None) is not c:
                    c.configure(fg_color="#eef6ec")
            except Exception:
                pass
        def _on_leave_cell(_e, c=cell):
            try:
                if getattr(self, "_selected_widget", None) is not c:
                    c.configure(fg_color=getattr(c, "_default_fg", GREEN_1))
            except Exception:
                pass
        # bind the cell and all descendants for uniform hover/click behavior
        def bind_recursive_cell(parent_widget):
            try:
                parent_widget.bind("<Button-1>", lambda e: on_click())
                parent_widget.bind("<Enter>", _on_enter_cell)
                parent_widget.bind("<Leave>", _on_leave_cell)
                # show pointer cursor on all bound widgets to indicate clickability
                try:
                    parent_widget.configure(cursor="hand2")
                except Exception:
                    pass
            except Exception:
                pass
            for ch in parent_widget.winfo_children():
                bind_recursive_cell(ch)

        bind_recursive_cell(cell)
        return cell

    # --- Public backend hook ---------------------------------------------
    def load_directory(self, path: str):
        """
        Replace demo data with your cloud listing.
        items: iterable of { 'name': str, 'is_dir': bool, 'size': '2 KB', 'date': 'YYYY-MM-DD' }
        """
        if path != self.path:
            self.history.append(self.path)
            self.path = path
        self.path_var.set(self.path)

        root:dict = self.firebase.get_owned_files(self.user)
        for directory in self.path.strip("/").split("/"):
            if (len(directory) > 1):
                root = root.get(directory, {})

        self.entries.clear()
        for name in root.keys():
            if (name != 'type'):
                parsed_name = decode_illegal_symbols(name)
                kind = _guess_type(parsed_name, root.get(name, {}).get('type') == 'folder')
                self.entries.append((kind, parsed_name, '-', ""))

        self._render()

    def delete_selected(self):
        """Delete the currently selected file (local demo now; Firebase-safe later)."""
        if not self.selected:
            print("[FileManager] No file selected.")
            return

        kind, name = self.selected
        cloud_path = (self.path.rstrip("/") + "/" + name).strip("/")
        if kind == "folder":
            self.firebase.delete_folder(self.user, name, self.path)
            self.master.after(200, lambda: self.load_directory(self.path))
            return

        # --- Real Firebase delete (when fb/user are set) -------------------
        try:
            self.firebase.delete_owned_file(self.user, cloud_path)
            print(f"[FileManager] Deleted from Firebase: {cloud_path}")
            self.master.after(200, lambda: self.load_directory(self.path))
        except Exception as e:
            print(f"[FileManager] Delete failed: {e}")
            return

        # Re-fetch directory from backend once you have that wired:
        # self.refresh_from_firebase()
    
    def upload(self):
        path = filedialog.askopenfilename()
        if not path:
            return
        
        filename = os.path.basename(path)
        self.firebase.upload_thread(self.user, (self.path.rstrip("/") + "/" + filename).strip("/"), path, on_finish=lambda result: self.load_directory(self.path))

    def create_folder(self):
        folder_name = simpledialog.askstring("Create folder", "File Name:")
        if not folder_name:
            return
        self.firebase.create_folder(self.user, folder_name, self.path)
        self.master.after(200, lambda: self.load_directory(self.path))
