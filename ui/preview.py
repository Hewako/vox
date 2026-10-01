"""Окно просмотра текста транскрипта."""
import tkinter as tk
from config import BG, BG_INPUT, FG, FG_SUBTLE, ACCENT, BORDER
from i18n import t
from ui.widgets import FlatButton
from core.utils import open_in_finder, open_file

def show_preview(root, path, previous=None):
    if previous and previous.winfo_exists():
        previous.destroy()

    text = path.read_text(encoding="utf-8")

    win = tk.Toplevel(root)
    win.title(t("preview_title_prefix", name=path.name))
    win.geometry("720x560")
    win.configure(bg=BG)

    header_p = tk.Frame(win, bg=BG)
    header_p.pack(fill="x", padx=16, pady=(12, 8))

    tk.Label(header_p, text=path.name,
             bg=BG, fg=FG,
             font=("Helvetica", 13, "bold")).pack(side="left")
    tk.Label(header_p,
             text=t("prev_stats", lines=len(text.splitlines()),
                    chars=len(text)),
             bg=BG, fg=FG_SUBTLE,
             font=("Helvetica", 11)).pack(side="right")

    text_wrap = tk.Frame(win, bg=BG_INPUT)
    text_wrap.pack(fill="both", expand=True, padx=16, pady=(0, 16))

    txt = tk.Text(
        text_wrap,
        bg=BG_INPUT, fg=FG,
        insertbackground=FG,
        bd=0, relief="flat", highlightthickness=0,
        font=("Menlo", 12), wrap="word",
        padx=12, pady=12)
    txt.pack(side="left", fill="both", expand=True)

    sb = tk.Scrollbar(text_wrap, command=txt.yview,
                      bd=0, relief="flat",
                      bg=BG_INPUT, troughcolor=BG_INPUT,
                      activebackground=BORDER,
                      highlightthickness=0, width=10)
    sb.pack(side="right", fill="y")
    txt.config(yscrollcommand=sb.set)

    txt.insert("1.0", text)
    txt.config(state="disabled")

    btn_p = tk.Frame(win, bg=BG)
    btn_p.pack(fill="x", padx=16, pady=(0, 16))

    FlatButton(btn_p, t("prev_btn_finder"),
               lambda: open_in_finder(path),
               bg=BG_INPUT, hover=BORDER, fg=FG,
               padx=14, pady=8,
               font=("Helvetica", 11)).pack(side="left")
    FlatButton(btn_p, t("prev_btn_editor"),
               lambda: open_file(path),
               bg=BG_INPUT, hover=BORDER, fg=FG,
               padx=14, pady=8,
               font=("Helvetica", 11)).pack(side="left", padx=8)

    return win