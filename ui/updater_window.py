"""
Update notification window.

Flow:
  1. Ready       - "Download and update" + "Later".
  2. Downloading - progress bar active, buttons disabled.
  3. Applying    - download finished, install_update() runs.
                   On success the message changes to "Installed",
                   then the app closes and the helper script swaps
                   .app and relaunches Vox.
  4. Error       - red status, error code, browser opens the
                   matching section of ERROR_CODES.md on GitHub.
                   Window stays open until the user closes it.
"""
import threading
import logging
import tempfile
import webbrowser
import tkinter as tk
from pathlib import Path

from config import (
    BG, BG_CARD, BG_INPUT, FG, FG_SUBTLE,
    ACCENT, ACCENT_HOVER, BORDER, SUCCESS, DANGER, DANGER_HOVER,
)
from i18n import t
from core import errors as error_codes
from core.updater import download_file, install_update
from ui.widgets import FlatButton

logger = logging.getLogger(__name__)


REPO_URL = "https://github.com/Hewako/vox"


def _code_url(code: str) -> str:
    """GitHub URL to the ERROR_CODES.md section for a code."""
    return f"{REPO_URL}/blob/main/ERROR_CODES.md#{code.lower()}"


def show_update_window(root, manifest, on_later=None):
    """Show the update dialog."""
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

    # Header
    header = tk.Frame(win, bg=BG)
    header.pack(fill="x", padx=24, pady=(22, 4))
    tk.Label(header, text=t("update_available", v=version),
             bg=BG, fg=FG,
             font=("Helvetica", 18, "bold")).pack(anchor="w")
    tk.Label(header, text=f"Vox {version}",
             bg=BG, fg=FG_SUBTLE,
             font=("Helvetica", 12)).pack(anchor="w", pady=(4, 0))

    # What's new
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

    # Progress bar
    prog_wrap = tk.Frame(win, bg=BG)
    prog_wrap.pack(fill="x", padx=24, pady=(16, 0))
    prog = tk.Canvas(prog_wrap, height=8, bg=BG_INPUT,
                     highlightthickness=0, bd=0)
    prog.pack(fill="x")
    prog_fill = prog.create_rectangle(0, 0, 0, 8, fill=ACCENT, outline="")

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

    # Buttons
    btn_row = tk.Frame(win, bg=BG)
    btn_row.pack(fill="x", padx=24, pady=(16, 22))

    state = {"phase": "ready"}

    def close():
        try:
            win.grab_release()
        except Exception:
            pass
        win.destroy()
        if on_later:
            on_later()

    def ui(fn):
        root.after(0, fn)

    def show_error(exc):
        """Classify, show, then open GitHub section for that code."""
        code = error_codes.classify(exc)
        desc = error_codes.describe_localized(code)
        msg = f"{t('error_prefix')}: {code} \u00b7 {desc}"
        logger.error(f"update failed: {code} \u2014 {exc}")

        set_progress(100, color=DANGER)
        status_lbl.config(fg=DANGER)
        status_var.set(msg)
        state["phase"] = "error"

        url = _code_url(code)
        start_btn.set_style(bg=DANGER, hover=DANGER_HOVER,
                            fg="white", text=t("update_btn_github"))
        start_btn.command = lambda u=url: webbrowser.open(u)
        # Re-enable both buttons so the click actually fires.
        start_btn.config(state="normal")

        later_btn.set_style(bg=BG_INPUT, hover=BORDER,
                            fg=FG, text=t("update_btn_close"))
        later_btn.command = close
        later_btn.config(state="normal")

        # Auto-open browser after a short delay. Window stays open.
        win.after(1500, lambda u=url: webbrowser.open(u))

    def do_apply(zip_path):
        """Downloaded - install now, no user click needed."""
        state["phase"] = "applying"
        status_var.set(t("update_installing"))
        status_lbl.config(fg=SUCCESS)
        set_progress(100, color=SUCCESS)
        start_btn.config(state="disabled")
        later_btn.config(state="disabled")

        def on_install_ok():
            status_var.set(t("update_installed"))
            status_lbl.config(fg=SUCCESS)
            # Give the user a moment to read the message before
            # the helper swaps the .app and relaunches Vox.
            win.after(800, root.destroy)

        def worker():
            try:
                install_update(zip_path)
                ui(on_install_ok)
            except Exception as exc:
                ui(lambda err=exc: show_error(err))

        threading.Thread(target=worker, daemon=True).start()

    def start_download():
        if state["phase"] in ("downloading", "applying", "error"):
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
                        ui(lambda p=pct: set_progress(p))

                download_file(download_url, zip_path, on_progress)
                # Straight to install - no intermediate phase.
                ui(lambda zp=zip_path: do_apply(zp))
            except Exception as exc:
                ui(lambda err=exc: show_error(err))

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

    def on_close():
        if state["phase"] in ("downloading", "applying"):
            return
        close()

    win.protocol("WM_DELETE_WINDOW", on_close)
    win.lift()
    win.focus_force()
