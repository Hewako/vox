"""First-run wizard: downloading Whisper models."""
import ssl
import time
import threading
import logging
import tkinter as tk
from tkinter import messagebox, ttk
from pathlib import Path
from urllib.request import urlopen, Request

from config import (
    MODELS_DIR, VAD_MODEL_NAME, BG, BG_CARD, BG_INPUT, FG, FG_SUBTLE,
    ACCENT, ACCENT_HOVER, BORDER, SUCCESS, DANGER,
)
from i18n import t
from ui.widgets import FlatButton

logger = logging.getLogger(__name__)

MAIN_MODEL_NAME = "ggml-large-v3-turbo.bin"
MAIN_MODEL_URL = (
    "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/"
    "ggml-large-v3-turbo.bin"
)
MAIN_MODEL_SIZE_MB = 1550

VAD_MODEL_URL = (
    "https://huggingface.co/ggml-org/whisper-vad/resolve/main/"
    "ggml-silero-v5.1.2.bin"
)
VAD_MODEL_SIZE_MB = 1

def _ssl_context():
    """
    Same as in core.updater: prefer certifi's CA bundle so HTTPS works
    on Python builds without system certificates.
    """
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception as e:
        logger.debug(f"certifi not available, using default: {e}")
        return ssl.create_default_context()

def has_any_model():
    if not MODELS_DIR.exists():
        return False
    for p in MODELS_DIR.glob("ggml-*.bin"):
        if "silero" not in p.name.lower():
            return True
    return False

def _fmt_eta(seconds):
    """Seconds -> '0:15' / '1:23' / '1:02:05'. Or '—' if unknown."""
    if seconds is None or seconds <= 0 or seconds > 86400 * 2:
        return "—"
    seconds = int(seconds)
    m, s = divmod(seconds, 60)
    if m < 60:
        return f"{m}:{s:02d}"
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}"

def _fmt_mb(mb):
    if mb is None:
        return "?"
    if mb < 1:
        return f"{mb * 1024:.0f} KB"
    if mb < 1024:
        return f"{mb:.1f} MB"
    return f"{mb / 1024:.2f} GB"

def show_wizard(root):
    if has_any_model():
        return True

    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    result = {"ok": False}

    win = tk.Toplevel(root)
    win.title(t("wizard_title"))
    win.geometry("620x440")
    win.resizable(False, False)
    win.configure(bg=BG)

    tk.Label(win, text=t("wizard_heading"),
             bg=BG, fg=FG,
             font=("Helvetica", 20, "bold")).pack(anchor="w",
                                                   padx=24, pady=(22, 6))

    tk.Label(win, text=t("wizard_subtitle"),
             bg=BG, fg=FG_SUBTLE,
             font=("Helvetica", 12),
             justify="left").pack(anchor="w", padx=24, pady=(0, 16))

    card = tk.Frame(win, bg=BG_CARD)
    card.pack(fill="x", padx=24, pady=(0, 16))

    inner = tk.Frame(card, bg=BG_CARD)
    inner.pack(fill="x", padx=16, pady=14)

    tk.Label(inner, text=t("wizard_what"),
             bg=BG_CARD, fg=FG,
             font=("Helvetica", 12, "bold")).pack(anchor="w", pady=(0, 8))

    for name, size in [(MAIN_MODEL_NAME, f"~{MAIN_MODEL_SIZE_MB} MB"),
                       (VAD_MODEL_NAME, f"~{VAD_MODEL_SIZE_MB} MB")]:
        row = tk.Frame(inner, bg=BG_CARD)
        row.pack(fill="x", pady=2)
        tk.Label(row, text="•", bg=BG_CARD, fg=FG_SUBTLE,
                 font=("Helvetica", 12)).pack(side="left")
        tk.Label(row, text=name, bg=BG_CARD, fg=FG,
                 font=("Menlo", 10)).pack(side="left", padx=(8, 0))
        tk.Label(row, text=size, bg=BG_CARD, fg=FG_SUBTLE,
                 font=("Helvetica", 10)).pack(side="right")

    tk.Label(inner, text=f"{t('wizard_where')}: {MODELS_DIR}",
             bg=BG_CARD, fg=FG_SUBTLE,
             font=("Helvetica", 10)).pack(anchor="w", pady=(8, 0))

    # Progress
    prog_wrap = tk.Frame(win, bg=BG)
    prog_wrap.pack(fill="x", padx=24, pady=(0, 8))

    prog_var = tk.DoubleVar(value=0)
    ttk.Progressbar(prog_wrap, variable=prog_var,
                    maximum=100).pack(fill="x")

    status_var = tk.StringVar(value=t("wizard_status_wait"))
    status_lbl = tk.Label(prog_wrap, textvariable=status_var,
                          bg=BG, fg=FG_SUBTLE,
                          font=("Helvetica", 11), anchor="w")
    status_lbl.pack(fill="x", pady=(6, 0))

    stats_var = tk.StringVar(value="")
    tk.Label(prog_wrap, textvariable=stats_var,
             bg=BG, fg=ACCENT,
             font=("Helvetica", 10, "bold"),
             anchor="w").pack(fill="x", pady=(2, 0))

    btn_row = tk.Frame(win, bg=BG)
    btn_row.pack(fill="x", padx=24, pady=(8, 22))

    state = {"downloading": False}

    def close_ok():
        result["ok"] = True
        win.destroy()

    def close_skip():
        if state["downloading"]:
            messagebox.showwarning("Vox", t("wizard_status_wait"))
            return
        result["ok"] = False
        win.destroy()

    def download_one(url, dest, label_key):
        dest = Path(dest)
        tmp = Path(str(dest) + ".part")
        label = t(label_key)

        try:
            req = Request(url, headers={"User-Agent": "Vox/1.0"})
            with urlopen(req, timeout=30,
                          context=_ssl_context()) as resp:
                total = int(resp.headers.get("Content-Length") or 0)
                downloaded = 0
                chunk_size = 1024 * 256

                start_time = time.time()

                with open(tmp, "wb") as f:
                    while True:
                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)

                        if total > 0:
                            pct = downloaded / total * 100
                            mb_done = downloaded / (1024 * 1024)
                            mb_total = total / (1024 * 1024)

                            elapsed = time.time() - start_time
                            if elapsed > 0.5:
                                speed = mb_done / elapsed
                                remaining_mb = mb_total - mb_done
                                eta = (remaining_mb / speed
                                       if speed > 0.01 else None)
                            else:
                                speed = 0
                                eta = None

                            speed_str = (f"{speed:.1f} MB/s"
                                         if speed > 0.01 else "— MB/s")
                            eta_str = _fmt_eta(eta)

                            win.after(0, lambda p=pct, m=mb_done,
                                      tt=mb_total, s=speed_str,
                                      e=eta_str, l=label:
                                      _update_progress(
                                          prog_var, status_var, stats_var,
                                          p, m, tt, s, e, l))
        except Exception as e:
            logger.error(f"Download {url} failed: {e}")
            if tmp.exists():
                try:
                    tmp.unlink()
                except Exception:
                    pass
            return False, str(e)

        try:
            if dest.exists():
                dest.unlink()
            tmp.rename(dest)
        except Exception as e:
            return False, str(e)

        return True, None

    def start_download():
        if state["downloading"]:
            return
        state["downloading"] = True
        start_btn.config(state="disabled")
        skip_btn.config(state="disabled")

        def worker():
            ok, err = download_one(
                VAD_MODEL_URL, MODELS_DIR / VAD_MODEL_NAME,
                "wizard_status_vad")
            if not ok:
                win.after(0, lambda: _fail(err))
                return
            ok, err = download_one(
                MAIN_MODEL_URL, MODELS_DIR / MAIN_MODEL_NAME,
                "wizard_status_main")
            if not ok:
                win.after(0, lambda: _fail(err))
                return
            win.after(0, _success)

        def _success():
            state["downloading"] = False
            prog_var.set(100)
            status_var.set(t("wizard_status_done"))
            stats_var.set("")
            status_lbl.config(fg=SUCCESS)
            win.after(600, close_ok)

        def _fail(err):
            state["downloading"] = False
            status_var.set(f"Error: {err}")
            stats_var.set("")
            status_lbl.config(fg=DANGER)
            start_btn.config(state="normal")
            skip_btn.config(state="normal")
            messagebox.showerror(
                "Vox",
                f"Download failed.\n\n{err}\n\n"
                f"{MAIN_MODEL_URL}\n→ {MODELS_DIR}/")

        threading.Thread(target=worker, daemon=True).start()

    start_btn = FlatButton(btn_row, t("wizard_btn_download"),
                           start_download,
                           bg=ACCENT, hover=ACCENT_HOVER, fg="white",
                           padx=20, pady=10,
                           font=("Helvetica", 12, "bold"))
    start_btn.pack(side="left")

    skip_btn = FlatButton(btn_row, t("wizard_btn_skip"),
                          close_skip,
                          bg=BG_INPUT, hover=BORDER, fg=FG_SUBTLE,
                          padx=16, pady=10,
                          font=("Helvetica", 11))
    skip_btn.pack(side="left", padx=8)

    FlatButton(btn_row, t("wizard_btn_exit"),
               lambda: (win.destroy(), result.update({"ok": False})),
               bg=BG_INPUT, hover=BORDER, fg=FG_SUBTLE,
               padx=16, pady=10,
               font=("Helvetica", 11)).pack(side="right")

    win.lift()
    win.focus_force()
    win.attributes("-topmost", True)
    win.after(200, lambda: win.attributes("-topmost", False))
    try:
        win.grab_set()
    except Exception:
        pass
    root.wait_window(win)

    return result["ok"]

def _update_progress(prog_var, status_var, stats_var,
                     pct, mb_done, mb_total, speed_str, eta_str, label):
    """Update progress bar, status and stats line."""
    prog_var.set(pct)
    status_var.set(f"{label}: {pct:.1f}%")
    stats_var.set(
        f"{_fmt_mb(mb_done)} / {_fmt_mb(mb_total)}"
        f"  ·  {speed_str}"
        f"  ·  ~{eta_str}"
    )