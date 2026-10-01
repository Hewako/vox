"""
Error codes reference window.

Shows the full list of error codes with localized descriptions.
Opened from the About dialog via the "Errors" button.
"""
import logging
import tkinter as tk

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

    # ── Header (top) ─────────────────────────────────────────
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

    # ── Buttons: pack BEFORE body so they anchor to the bottom ──
    btn_row = tk.Frame(win, bg=BG)
    btn_row.pack(side="bottom", fill="x", padx=24, pady=(12, 20))

    FlatButton(btn_row, t("errors_window_close"), win.destroy,
               bg=BG, hover=BORDER, fg=FG,
               padx=18, pady=10,
               font=f_btn).pack(side="right")

    # ── Body fills the remaining middle space ────────────────
    body = tk.Frame(win, bg=BG_CARD)
    body.pack(side="top", fill="both", expand=True, padx=24, pady=(0, 0))

    # Canvas + inner frame = real scrollable area
    canvas = tk.Canvas(body, bg=BG_CARD, highlightthickness=0, bd=0)
    scrollbar = tk.Scrollbar(body, orient="vertical",
                             command=canvas.yview,
                             bd=0, relief="flat",
                             bg=BG_CARD, troughcolor=BG_CARD,
                             activebackground=BORDER,
                             highlightthickness=0, width=10)
    canvas.configure(yscrollcommand=scrollbar.set)

    scrollbar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)

    inner = tk.Frame(canvas, bg=BG_CARD)
    inner_id = canvas.create_window((0, 0), window=inner, anchor="nw")

    def on_inner_configure(event=None):
        canvas.configure(scrollregion=canvas.bbox("all"))

    def on_canvas_resize(event):
        canvas.itemconfig(inner_id, width=event.width)

    inner.bind("<Configure>", on_inner_configure)
    canvas.bind("<Configure>", on_canvas_resize)

    def on_mousewheel(event):
        if event.delta == 0:
            return
        canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")

    win.bind("<MouseWheel>", on_mousewheel)

    pad = tk.Frame(inner, bg=BG_CARD)
    pad.pack(fill="both", expand=True, padx=20, pady=16)

    wrap = WIN_W - 200
    for code in sorted(errors.CODES.keys()):
        row = tk.Frame(pad, bg=BG_CARD)
        row.pack(fill="x", pady=4)

        tk.Label(row, text=code, bg=BG_CARD, fg=ACCENT,
                 font=f_mono, width=6, anchor="nw").pack(side="left")

        tk.Label(row, text=errors.describe_localized(code),
                 bg=BG_CARD, fg=FG,
                 font=f_ui,
                 justify="left", wraplength=wrap,
                 anchor="w").pack(side="left", fill="x", expand=True)

    win.bind("<Escape>", lambda e: win.destroy())
    win.protocol("WM_DELETE_WINDOW", win.destroy)

    win.lift()
    win.focus_force()
    return win
