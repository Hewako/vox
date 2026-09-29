"""Окно с информацией о доступном обновлении."""
import threading
import logging
import tempfile
import tkinter as tk
from pathlib import Path

from config import (
    BG, BG_CARD, BG_INPUT, FG, FG_SUBTLE, FG_DIM,
    ACCENT, ACCENT_HOVER, BORDER, SUCCESS, DANGER,
)
from i18n import t
from ui.widgets import FlatButton
from core.updater import download_file, install_update

logger = logging.getLogger(__name__)


def show_update_window(root, manifest, on_later=None):
    """
    Показывает окно с информацией об апдейте.
    manifest — dict {'version', 'download_url', 'notes'} из version.json.
    on_later — колбэк, если пользователь нажал «Позже».
    """
    version = manifest.get("version", "?")
    download_url = manifest.get("download_url", "").strip()
    notes = manifest.get("notes", "").strip()

    win = tk.Toplevel(root)
    win.title(t("update_title"))
    win.geometry("520x480")
    win.resizable(False, False)
    win.configure(bg=BG)
    win.transient(root)
    win.grab_set()

    # ── Заголовок ────────────────────────────────────────────
    header = tk.Frame(win, bg=BG)
    header.pack(fill="x", padx=24, pady=(22, 4))

    tk.Label(header, text=t("update_available", v=version),
             bg=BG, fg=FG,
             font=("Helvetica", 18, "bold")).pack(anchor="w")

    tk.Label(header, text=f"Vox {version}",
             bg=BG, fg=FG_SUBTLE,
             font=("Helvetica", 12)).pack(anchor="w", pady=(4, 0))

    # ── Что нового ───────────────────────────────────────────
    if notes:
        notes_card = tk.Frame(win, bg=BG_CARD)
        notes_card.pack(fill="both", expand=True, padx=24, pady=(16, 0))

        notes_inner = tk.Frame(notes_card, bg=BG_CARD)
        notes_inner.pack(fill="both", expand=True, padx=16, pady=14)

        tk.Label(notes_inner, text=t("update_notes"),
                 bg=BG_CARD, fg=FG,
                 font=("Helvetica", 12, "bold")).pack(anchor="w",
                                                       pady=(0, 8))

        notes_text = tk.Text(
            notes_inner, height=10,
            bg=BG_CARD, fg=FG,
            bd=0, relief="flat", highlightthickness=0,
            font=("Helvetica", 11), wrap="word")
        notes_text.pack(fill="both", expand=True)
        notes_text.insert("1.0", notes)
        notes_text.config(state="disabled")

    # ── Прогресс ─────────────────────────────────────────────
    prog_wrap = tk.Frame(win, bg=BG)
    prog_wrap.pack(fill="x", padx=24, pady=(16, 0))

    prog_var = tk.DoubleVar(value=0)
    prog = tk.Canvas(prog_wrap, height=8, bg=BG_INPUT,
                      highlightthickness=0, bd=0)
    prog.pack(fill="x")

    prog_fill = prog.create_rectangle(
        0, 0, 0, 8, fill=ACCENT, outline="")

    def set_progress(pct):
        prog.update_idletasks()
        w = prog.winfo_width()
        prog.coords(prog_fill, 0, 0, w * (pct / 100), 8)

    status_var = tk.StringVar(value="")
    tk.Label(prog_wrap, textvariable=status_var,
             bg=BG, fg=FG_SUBTLE,
             font=("Helvetica", 10)).pack(anchor="w", pady=(6, 0))

    # ── Кнопки ───────────────────────────────────────────────
    btn_row = tk.Frame(win, bg=BG)
    btn_row.pack(fill="x", padx=24, pady=(16, 22))

    state = {"downloading": False, "zip_path": None}

    def close():
        win.destroy()
        if on_later:
            on_later()

    def ui(fn):
        root.after(0, fn)

    def download_and_install():
        if not download_url:
            ui(lambda: status_var.set("download_url пуст в version.json"))
            return

        state["downloading"] = True
        start_btn.config(state="disabled")
        later_btn.config(state="disabled")

        def worker():
            try:
                tmp_dir = Path(tempfile.mkdtemp(prefix="vox_upd_"))
                zip_path = tmp_dir / "Vox.app.zip"

                ui(lambda: status_var.set(t("update_downloading")))

                def on_progress(done, total):
                    if total > 0:
                        pct = done / total * 100
                        ui(lambda: set_progress(pct))

                download_file(download_url, zip_path, on_progress)

                ui(lambda: set_progress(100))
                ui(lambda: status_var.set(t("update_installing")))

                # Установка + перезапуск. После этого приложение само уйдёт.
                install_update(zip_path)

                ui(lambda: root.after(500, root.destroy))

            except Exception as e:
                logger.error(f"update failed: {e}")
                err = str(e)
                ui(lambda: status_var.set(f"{t('update_failed')}: {err}"))
                ui(lambda: start_btn.config(state="normal"))
                ui(lambda: later_btn.config(state="normal"))
                state["downloading"] = False

        threading.Thread(target=worker, daemon=True).start()

    start_btn = FlatButton(
        btn_row, t("update_btn_download"), download_and_install,
        bg=ACCENT, hover=ACCENT_HOVER, fg="white",
        padx=18, pady=10,
        font=("Helvetica", 12, "bold"))
    start_btn.pack(side="left")

    later_btn = FlatButton(
        btn_row, t("update_btn_later"), close,
        bg=BG_INPUT, hover=BORDER, fg=FG_SUBTLE,
        padx=16, pady=10,
        font=("Helvetica", 11))
    later_btn.pack(side="right")

    # ── Закрытие ─────────────────────────────────────────────
    def on_close():
        if state["downloading"]:
            return
        close()

    win.protocol("WM_DELETE_WINDOW", on_close)
    win.lift()
    win.focus_force()