"""Окно «Не хватает зависимостей»."""
import tkinter as tk

from config import (
    BG, BG_CARD, BG_INPUT, FG, FG_SUBTLE, FG_DIM,
    ACCENT, ACCENT_HOVER, BORDER, SUCCESS, DANGER,
)
from i18n import t
from ui.widgets import FlatButton


INSTALL_CMD = "brew install whisper-cpp ffmpeg"


def show_missing_deps(root, missing):
    result = {"ok": False}

    win = tk.Toplevel(root)
    win.title(t("missing_title"))
    win.geometry("620x540")
    win.resizable(False, False)
    win.configure(bg=BG)

    header = tk.Frame(win, bg=BG)
    header.pack(fill="x", padx=24, pady=(22, 6))

    tk.Label(header, text=t("missing_title"),
             bg=BG, fg=FG,
             font=("Helvetica", 20, "bold")).pack(anchor="w")

    tk.Label(header, text=t("missing_intro"),
             bg=BG, fg=FG_SUBTLE,
             font=("Helvetica", 12),
             justify="left").pack(anchor="w", pady=(8, 0))

    card = tk.Frame(win, bg=BG_CARD)
    card.pack(fill="x", padx=24, pady=(16, 0))

    inner = tk.Frame(card, bg=BG_CARD)
    inner.pack(fill="x", padx=16, pady=14)

    tk.Label(inner, text=t("missing_what"),
             bg=BG_CARD, fg=FG,
             font=("Helvetica", 12, "bold")).pack(anchor="w", pady=(0, 10))

    for item in missing:
        row = tk.Frame(inner, bg=BG_CARD)
        row.pack(fill="x", pady=3)

        tk.Label(row, text="✗", bg=BG_CARD, fg=DANGER,
                 font=("Helvetica", 13, "bold")).pack(side="left")
        tk.Label(row, text=item.get("name", "?"),
                 bg=BG_CARD, fg=FG,
                 font=("Menlo", 11)).pack(side="left", padx=(8, 0))
        if item.get("hint"):
            tk.Label(row, text=f"— {item['hint']}",
                     bg=BG_CARD, fg=FG_DIM,
                     font=("Helvetica", 10)).pack(side="left", padx=(6, 0))

    cmd_card = tk.Frame(win, bg=BG_CARD)
    cmd_card.pack(fill="x", padx=24, pady=(12, 0))

    cmd_inner = tk.Frame(cmd_card, bg=BG_CARD)
    cmd_inner.pack(fill="x", padx=16, pady=14)

    tk.Label(cmd_inner, text=t("missing_copy_hint"),
             bg=BG_CARD, fg=FG,
             font=("Helvetica", 12, "bold")).pack(anchor="w", pady=(0, 10))

    cmd_box = tk.Frame(cmd_inner, bg=BG_INPUT)
    cmd_box.pack(fill="x")

    tk.Label(cmd_box, text=INSTALL_CMD,
             bg=BG_INPUT, fg=FG,
             font=("Menlo", 12),
             anchor="w", padx=12, pady=10).pack(side="left",
                                                 fill="x", expand=True)

    status_var = tk.StringVar(value="")

    def copy_cmd():
        win.clipboard_clear()
        win.clipboard_append(INSTALL_CMD)
        status_var.set("✓ Copied / Скопировано")
        win.after(1500, lambda: status_var.set(""))

    FlatButton(cmd_box, t("missing_btn_copy"),
               copy_cmd,
               bg=BG_INPUT, hover=BORDER, fg=FG,
               padx=12, pady=8,
               font=("Helvetica", 10)).pack(side="right", padx=6)

    tk.Label(cmd_inner, textvariable=status_var,
             bg=BG_CARD, fg=SUCCESS,
             font=("Helvetica", 10)).pack(anchor="w", pady=(6, 0))

    tk.Label(win, text=t("missing_brew_hint"),
             bg=BG, fg=FG_DIM,
             font=("Helvetica", 10)).pack(pady=(10, 0))

    btn_row = tk.Frame(win, bg=BG)
    btn_row.pack(fill="x", padx=24, pady=(20, 22))

    def recheck():
        from core.utils import check_deps
        problems = check_deps()
        if not problems:
            result["ok"] = True
            win.destroy()
        else:
            status_var.set("Still missing: " + ", ".join(problems))
            win.after(2500, lambda: status_var.set(""))

    FlatButton(btn_row, t("missing_btn_recheck"),
               recheck,
               bg=ACCENT, hover=ACCENT_HOVER, fg="white",
               padx=20, pady=10,
               font=("Helvetica", 12, "bold")).pack(side="left")

    FlatButton(btn_row, t("missing_btn_close"),
               win.destroy,
               bg=BG_INPUT, hover=BORDER, fg=FG_SUBTLE,
               padx=16, pady=10,
               font=("Helvetica", 11)).pack(side="right")

    win.transient(root)
    win.grab_set()
    win.lift()
    win.focus_force()
    root.wait_window(win)

    return result["ok"]