"""Vox About window."""
import sys
import threading
import platform
import webbrowser
import tkinter as tk

from config import (
    __version__, BG, BG_CARD, BG_INPUT, FG, FG_SUBTLE, FG_DIM,
    ACCENT, BORDER, WHISPER_BIN, FFMPEG_BIN, FFPROBE_BIN,
    MODELS_DIR, CACHE_DIR, SETTINGS_FILE, LOG_FILE,
)
from i18n import t
from ui.widgets import FlatButton
from ui.changelog_window import show_changelog_window
from ui.errors_window import show_errors_window
from core.cache import cache_size_mb
from core.utils import open_file, open_in_finder
from core.updater import check_for_update

LINKS = {
    "whisper.cpp": "https://github.com/ggerganov/whisper.cpp",
    "ffmpeg": "https://ffmpeg.org/",
    "tkinterdnd2": "https://github.com/petasis/tkdnd",
}

def show_about(root):
    win = tk.Toplevel(root)
    win.title(t("about_title"))
    win.geometry("600x900")
    win.resizable(False, False)
    win.configure(bg=BG)

    top = tk.Frame(win, bg=BG)
    top.pack(fill="x", padx=24, pady=(20, 4))

    try:
        from ui.about_icon import ABOUT_ICON_BASE64
        img = tk.PhotoImage(data=ABOUT_ICON_BASE64)
        lbl = tk.Label(top, image=img, bg=BG, bd=0)
        lbl.image = img
        lbl.pack(anchor="w")
    except Exception:
        pass

    tk.Label(top, text="Vox", bg=BG, fg=FG,
             font=("Helvetica", 30, "bold")).pack(anchor="w", pady=(10, 0))

    ver_row = tk.Frame(top, bg=BG)
    ver_row.pack(anchor="w", pady=(2, 0))

    tk.Label(ver_row, text=t("about_version", v=__version__),
             bg=BG, fg=FG_SUBTLE,
             font=("Helvetica", 13)).pack(side="left")

    tk.Label(ver_row, text="  ·  ",
             bg=BG, fg=FG_DIM,
             font=("Helvetica", 13)).pack(side="left")

    whats_new = tk.Label(
        ver_row,
        text=t("changelog_title"),
        bg=BG, fg=ACCENT,
        font=("Helvetica", 13, "underline"),
        cursor="pointinghand",
    )
    whats_new.pack(side="left")

    def open_changelog(event=None):
        show_changelog_window(win)
        return "break"

    whats_new.bind("<Button-1>", open_changelog)
    whats_new.bind("<Enter>",
                   lambda e: whats_new.config(fg=FG))
    whats_new.bind("<Leave>",
                   lambda e: whats_new.config(fg=ACCENT))

    tk.Label(top, text=t("about_description"),
             bg=BG, fg=FG_SUBTLE,
             font=("Helvetica", 11)).pack(anchor="w", pady=(8, 0))

    _section(win, t("about_components"), [
        ("whisper-cli", WHISPER_BIN),
        ("ffmpeg", FFMPEG_BIN),
        ("ffprobe", FFPROBE_BIN),
    ])

    models = []
    if MODELS_DIR.exists():
        models = [m for m in MODELS_DIR.glob("ggml-*.bin")
                  if "silero" not in m.name.lower()]

    cache_mb = cache_size_mb()

    _section(win, t("about_data"), [
        (t("about_models"), f"{len(models)} · {MODELS_DIR}"),
        (t("about_cache"), f"{cache_mb:.1f} MB · {CACHE_DIR}"),
        (t("about_settings"), str(SETTINGS_FILE)),
        (t("about_logs"), str(LOG_FILE)),
    ])

    sys_info = f"Python {sys.version.split()[0]}"
    if sys.platform == "darwin":
        sys_info = f"macOS {platform.mac_ver()[0]} · {sys_info}"
    else:
        sys_info = f"{platform.system()} · {sys_info}"

    _section(win, t("about_system"), [
        (t("about_platform"), sys_info),
        (t("about_arch"), platform.machine()),
    ])

    links_card = tk.Frame(win, bg=BG_CARD)
    links_card.pack(fill="x", padx=24, pady=(8, 0))
    links_inner = tk.Frame(links_card, bg=BG_CARD)
    links_inner.pack(fill="x", padx=16, pady=12)

    tk.Label(links_inner, text=t("about_uses"),
             bg=BG_CARD, fg=FG,
             font=("Helvetica", 12, "bold")).pack(anchor="w", pady=(0, 8))

    link_row = tk.Frame(links_inner, bg=BG_CARD)
    link_row.pack(anchor="w")

    for i, (name, url) in enumerate(LINKS.items()):
        lbl = tk.Label(link_row, text=name,
                       bg=BG_CARD, fg=ACCENT,
                       font=("Helvetica", 11, "underline"),
                       cursor="pointinghand")
        lbl.pack(side="left")
        lbl.bind("<Button-1>", lambda e, u=url: webbrowser.open(u))
        if i < len(LINKS) - 1:
            tk.Label(link_row, text="  ·  ",
                     bg=BG_CARD, fg=FG_DIM,
                     font=("Helvetica", 11)).pack(side="left")

    update_status_var = tk.StringVar(value="")
    update_status_lbl = tk.Label(win, textvariable=update_status_var,
                                  bg=BG, fg=FG_SUBTLE,
                                  font=("Helvetica", 10))

    btn_row = tk.Frame(win, bg=BG)
    btn_row.pack(fill="x", padx=24, pady=(12, 22))

    update_btn = FlatButton(
        btn_row, t("about_btn_update"), None,
        bg=BG_INPUT, hover=BORDER, fg=FG,
        padx=14, pady=8,
        font=("Helvetica", 11))
    update_btn.pack(side="left")
    update_status_lbl.pack(anchor="w", padx=24, pady=(6, 0))

    def ui(fn):
        root.after(0, fn)

    def do_check():
        update_btn.config(state="disabled")
        ui(lambda: update_status_var.set(t("update_checking")))

        def worker():
            data = check_for_update()
            if data is None:
                ui(lambda: update_status_var.set(t("update_up_to_date")))
                ui(lambda: update_btn.config(state="normal"))
                return

            ui(lambda: update_status_var.set(
                t("update_available", v=data.get("version", "?"))))

            def open_window():
                from ui.updater_window import show_update_window
                show_update_window(root, data,
                                    on_later=lambda: update_btn.config(
                                        state="normal"))

            ui(open_window)

        threading.Thread(target=worker, daemon=True).start()

    update_btn.command = do_check

    FlatButton(btn_row, t("about_btn_log"),
               lambda: open_file(LOG_FILE),
               bg=BG_INPUT, hover=BORDER, fg=FG,
               padx=14, pady=8,
               font=("Helvetica", 11)).pack(side="left", padx=(8, 0))

    FlatButton(btn_row, t("about_btn_models"),
               lambda: open_in_finder(MODELS_DIR),
               bg=BG_INPUT, hover=BORDER, fg=FG,
               padx=14, pady=8,
               font=("Helvetica", 11)).pack(side="left", padx=(8, 0))

    FlatButton(btn_row, t("about_btn_errors"),
               lambda: show_errors_window(win),
               bg=BG_INPUT, hover=BORDER, fg=FG,
               padx=14, pady=8,
               font=("Helvetica", 11)).pack(side="left", padx=(8, 0))

    FlatButton(btn_row, t("about_btn_close"),
               win.destroy,
               bg=BG_INPUT, hover=BORDER, fg=FG_SUBTLE,
               padx=14, pady=8,
               font=("Helvetica", 11)).pack(side="right")

    tk.Label(win,
             text=f"Vox {__version__} · Made by Hewako",
             bg=BG, fg=FG_DIM,
             font=("Helvetica", 10)).pack(pady=(0, 14))

def _section(parent, title, rows):
    card = tk.Frame(parent, bg=BG_CARD)
    card.pack(fill="x", padx=24, pady=(8, 0))

    inner = tk.Frame(card, bg=BG_CARD)
    inner.pack(fill="x", padx=16, pady=12)

    tk.Label(inner, text=title, bg=BG_CARD, fg=FG,
             font=("Helvetica", 12, "bold")).pack(anchor="w", pady=(0, 8))

    for label, value in rows:
        row = tk.Frame(inner, bg=BG_CARD)
        row.pack(fill="x", pady=1)

        tk.Label(row, text=label, bg=BG_CARD, fg=FG_SUBTLE,
                 font=("Helvetica", 11),
                 width=11, anchor="nw").pack(side="left")

        tk.Label(row, text=str(value), bg=BG_CARD, fg=FG,
                 font=("Menlo", 10),
                 anchor="w", justify="left",
                 wraplength=420).pack(side="left", fill="x", expand=True)
