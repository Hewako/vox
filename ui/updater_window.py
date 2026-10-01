"""
Update notification window.

Phases:
  1. Ready to download — progress bar hidden, two buttons.
  2. Downloading       — progress bar active, buttons disabled.
  3. Ready to install  — progress done, only one "Done" button visible.
  4. Error             — red status text, buttons re-enabled.
  5. Applying          — install_update() runs, app closes.
"""
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
from core import errors as error_codes
from core.updater import download_file, install_update
from ui.widgets import FlatButton

logger = logging.getLogger(__name__)


def show_update_window(root, manifest, on_later=None):
    """
    Show the update dialog.

    manifest — dict {'version', 'download_url', 'notes'} from version.json
    on_later — callback if the user chooses to postpone
    """
    version = manifest.get("version", "?")
    download_url = manifest.get("download_url", "").strip()
    notes = manifest.get("notes", "").strip()

    win = tk.Toplevel(root)
    win.title(t("update_title"))
    win.geometry("520x520")
    win.resizable(False, False)
    win.configure(bg=BG)
    win.transient(root)
    win.grab_set()

    # ── Header ───────────────────────────────────────────────
    header = tk.Frame(win, bg=BG)
    header.pack(fill="x", padx=24, pady=(22, 4))

    tk.Label(header, text=t("update_available", v=version),
             bg=BG, fg=FG,
             font=("Helvetica", 18, "bold")).pack(anchor="w")

    tk.Label(header, text=f"Vox {version}",
             bg=BG, fg=FG_SUBTLE,
             font=("Helvetica", 12)).pack(anchor="w", pady=(4, 0))

    # ── What's new ───────────────────────────────────────────
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

    # ── Progress bar ─────────────────────────────────────────
    prog_wrap = tk.Frame(win, bg=BG)
    prog_wrap.pack(fill="x", padx=24, pady=(16, 0))

    prog_var = tk.DoubleVar(value=0)
    prog = tk.Canvas(prog_wrap, height=8, bg=BG_INPUT,
                      highlightthickness=0, bd=0)
    prog.pack(fill="x")

    prog_fill = prog.create_rectangle(
        0, 0, 0, 8, fill=ACCENT, outline="")

    def set_progress(pct, color=ACCENT):
        prog.update_idletasks()
        w = prog.winfo_width()
        prog.itemconfig(prog_fill, fill=color)
        prog.coords(prog_fill, 0, 0, w * (pct / 100), 8)

    status_var = tk.StringVar(value="")
    status_lbl = tk.Label(prog_wrap, textvariable=status_var,
                          bg=BG, fg=FG_SUBTLE,
                          font=("Helvetica", 10),
                          anchor="w", justify="left",
                          wraplength=460)
    status_lbl.pack(fill="x", pady=(6, 0))

    # ── Buttons ──────────────────────────────────────────────
    btn_row = tk.Frame(win, bg=BG)
    btn_row.pack(fill="x", padx=24, pady=(16, 22))

    state = {
        "phase": "ready",     # ready | downloading | done | applying
        "zip_path": None,
    }

    def close():
        win.destroy()
        if on_later:
            on_later()

    def ui(fn):
        root.after(0, fn)

    def show_error(exc):
        """Classify exception, show localized code + description."""
        code = error_codes.classify(exc)
        msg = f"{t('error_prefix')}: {code} · {error_codes.describe_localized(code)}"
        logger.error(f"update failed: {code} — {exc}")
        set_progress(100, color=DANGER)
        status_lbl.config(fg=DANGER)
        status_var.set(msg)
        state["phase"] = "ready"
        start_btn.config(state="normal")
        later_btn.config(state="normal")

    def do_apply():
        """User pressed Done after download — apply the update."""
        if state["phase"] != "done":
            return
        zip_path = state["zip_path"]
        if not zip_path or not Path(zip_path).exists():
            show_error(RuntimeError("Downloaded archive is missing"))
            return

        state["phase"] = "applying"
        status_var.set(t("update_installing"))
        status_lbl.config(fg=FG_SUBTLE)

        def worker():
            try:
                install_update(zip_path)
                # install_update launches a helper that waits for us
                # to exit, then swaps the .app and relaunches it.
                ui(lambda: root.after(300, root.destroy))
            except Exception as e:
                ui(lambda: show_error(e))

        threading.Thread(target=worker, daemon=True).start()

    def switch_to_done(zip_path):
        """Download finished — show Done phase with one button."""
        state["phase"] = "done"
        state["zip_path"] = zip_path
        set_progress(100, color=SUCCESS)
        status_lbl.config(fg=SUCCESS)
        status_var.set(t("update_ready"))

        # Hide Later, rename start button to Done and repoint its action
        later_btn.pack_forget()
        start_btn.set_style(bg=SUCCESS, hover=SUCCESS,
                            fg="white", text=t("update_btn_ready"))
        start_btn.command = do_apply

    def start_download():
        if state["phase"] == "done":
            do_apply()
            return
        if state["phase"] == "downloading":
            return

        if not download_url:
            status_lbl.config(fg=DANGER)
            status_var.set(t("update_no_url"))
            return

        state["phase"] = "downloading"
        start_btn.config(state="disabled")
        later_btn.config(state="disabled")
        status_lbl.config(fg=FG_SUBTLE)

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
                ui(lambda: switch_to_done(zip_path))

            except Exception as e:
                ui(lambda: show_error(e))

        threading.Thread(target=worker, daemon=True).start()

    start_btn = FlatButton(
        btn_row, t("update_btn_download"), start_download,
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

    # ── Window closing ───────────────────────────────────────
    def on_close():
        if state["phase"] in ("downloading", "applying"):
            return
        close()

    win.protocol("WM_DELETE_WINDOW", on_close)
    win.lift()
    win.focus_force()
