"""Manual check: the first-run wizard really downloads models.

Runs the real wizard window against a local HTTP server, presses
"Download" and verifies both files arrive. Needs a Python with tkinter
(python.org build); a window flashes for a couple of seconds.

    python3 scripts/check_wizard_download.py
"""
import functools
import http.server
import os
import sys
import tempfile
import threading
import tkinter as tk
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import i18n  # noqa: E402
from ui import setup_wizard as w  # noqa: E402

SIZES = {"ggml-large-v3-turbo.bin": 3_000_000, "ggml-silero-v5.1.2.bin": 200_000}

srv = Path(tempfile.mkdtemp())
for name, size in SIZES.items():
    (srv / name).write_bytes(os.urandom(size))

handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(srv))
handler.log_message = lambda *a, **k: None
httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
threading.Thread(target=httpd.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{httpd.server_address[1]}"

models = Path(tempfile.mkdtemp())
w.MODELS_DIR = models
w.MAIN_MODEL_URL = f"{base}/ggml-large-v3-turbo.bin"
w.VAD_MODEL_URL = f"{base}/ggml-silero-v5.1.2.bin"

root = tk.Tk()
root.withdraw()


def find_label(widget, text):
    if isinstance(widget, tk.Label) and widget.cget("text") == text:
        return widget
    for child in widget.winfo_children():
        found = find_label(child, text)
        if found:
            return found


def click_download():
    win = next(c for c in root.winfo_children() if isinstance(c, tk.Toplevel))
    find_label(win, i18n.t("wizard_btn_download")).event_generate("<Button-1>")
    root.after(10_000, win.destroy)  # fail-safe: the download should finish long before


root.after(400, click_download)
result = w.show_wizard(root)
got = {p.name: p.stat().st_size for p in models.iterdir()}
print("wizard returned:", result)
print("downloaded:", got)
assert result is True and got == SIZES, "wizard did not download the models"
print("OK")
