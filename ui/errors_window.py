"""
Error codes reference window.

Shows the full list of error codes with localized descriptions.
Each code is a clickable link that opens the matching section of
ERROR_CODES.md on GitHub.
"""
import logging
import webbrowser
import tkinter as tk
from tkinter import ttk

from config import (
    BG, BG_CARD, FG, FG_SUBTLE, ACCENT, BORDER,
    get_font, FONT_SIZE_ORDER,
)
from i18n import t
from core import errors
from ui.widgets import FlatButton

logger = logging.getLogger(__name__)

WIN_W = 640
WIN_H = 720

REPO_URL = "https://github.com/Hewako/vox"


def _code_url(code: str) -> str:
    """GitHub URL to the ERROR_CODES.md section for a code."""
    return f"{REPO_URL}/blob/main/ERROR_CODES.md#{code.lower()}"


def show_errors_window(root):
    win = tk.Toplevel(root)
    win.title(t("errors_window_title"))
    win.geometry(f"{WIN_W}x{WIN_H}")
    win.resizable(True, True)
    win.minsize(520, 480)
    win.configure(bg=BG)
    win.transient(root)

    root.update_idletasks()
    x = root.winfo_rootx() + (root.winfo_width() - WIN_W) // 2
    y = root.winfo_rooty() + (root.winfo_height() - WIN_H) // 3
    win.geometry(f"{WIN_W}x{WIN_H}+{max(x, 40)}+{max(y, 40)}")

    from core.settings import load_settings
    font_size_key = load_settings().get("font_size", "medium")
    if font_size_key not in FONT_SIZE_ORDER:
        font_size_key = "medium"
    f_ui = get_font(font_size_key, "ui")
    f_small = get_font(font_size_key, "small")
    f_mono = get_font(font_size_key, "mono")
    f_btn = get_font(font_size_key, "btn")

    # ── Header ───────────────────────────────────────────────
    header = tk.Frame(win, bg=BG)
    header.pack(side="top", fill="x", padx=24, pady=(20, 4))
    tk.Label(header, text=t("errors_window_title"),
             bg=BG, fg=FG,
             font=(f_ui[0], f_ui[1] + 8, "bold")).pack(anchor="w")

    tk.Label(win, text=t("errors_window_intro"),
             bg=BG, fg=FG_SUBTLE,
             font=f_small,
             justify="left", wraplength=WIN_W - 60,
             anchor="w").pack(side="top", fill="x", padx=24, pady=(6, 12))

    # ── Bottom buttons ───────────────────────────────────────
    btn_row = tk.Frame(win, bg=BG)
    btn_row.pack(side="bottom", fill="x", padx=24, pady=(12, 20))

    # ── Body ─────────────────────────────────────────────────
    body = tk.Frame(win, bg=BG_CARD)
    body.pack(side="top", fill="both", expand=True, padx=24, pady=(0, 0))

    canvas = tk.Canvas(body, bg=BG_CARD, highlightthickness=0, bd=0)
    canvas.configure(yscrollincrement=1)

    scrollbar = ttk.Scrollbar(body, orient="vertical",
                              command=canvas.yview)
    canvas.configure(yscrollcommand=scrollbar.set)

    scrollbar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)

    inner = tk.Frame(canvas, bg=BG_CARD)
    canvas.create_window((0, 0), window=inner, anchor="nw")

    def on_inner_configure(event=None):
        canvas.configure(scrollregion=canvas.bbox("all"))

    inner.bind("<Configure>", on_inner_configure)

    def on_mousewheel(event):
        if event.delta == 0:
            return
        first, last = canvas.yview()
        if event.delta > 0 and first <= 0.0:
            return
        if event.delta < 0 and last >= 1.0:
            return
        canvas.yview_scroll(-event.delta, "units")

    canvas.bind_all("<MouseWheel>", on_mousewheel)

    def close():
        try:
            canvas.unbind_all("<MouseWheel>")
        except Exception:
            pass
        win.destroy()

    FlatButton(btn_row, t("errors_window_close"), close,
               bg=BG, hover=BORDER, fg=FG,
               padx=18, pady=10,
               font=f_btn).pack(side="right")

    # ── Content list ─────────────────────────────────────────
    pad = tk.Frame(inner, bg=BG_CARD)
    pad.pack(fill="both", expand=True, padx=20, pady=16)

    wrap = WIN_W - 200

    def make_code_link(parent, code):
        url = _code_url(code)
        lbl = tk.Label(parent, text=code,
                       bg=BG_CARD, fg=ACCENT,
                       font=(f_mono[0], f_mono[1], "underline"),
                       width=6, anchor="nw",
                       cursor="pointinghand")

        def on_click(event):
            webbrowser.open(url)
            return "break"

        def on_enter(event):
            lbl.config(fg=FG)

        def on_leave(event):
            lbl.config(fg=ACCENT)

        lbl.bind("<Button-1>", on_click)
        lbl.bind("<Enter>", on_enter)
        lbl.bind("<Leave>", on_leave)
        return lbl

    for code in sorted(errors.CODES.keys()):
        row = tk.Frame(pad, bg=BG_CARD)
        row.pack(fill="x", pady=4)

        make_code_link(row, code).pack(side="left")

        tk.Label(row, text=errors.describe_localized(code),
                 bg=BG_CARD, fg=FG,
                 font=f_ui,
                 justify="left", wraplength=wrap,
                 anchor="w").pack(side="left", fill="x", expand=True)

    win.bind("<Escape>", lambda e: close())
    win.protocol("WM_DELETE_WINDOW", close)

    win.lift()
    win.focus_force()
    return win
