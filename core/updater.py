"""
Update checker and installer for Vox.

How it works:

1. Once a day (or on demand from About) the app fetches version.json
   from the repo. It holds the current version and a download URL for
   the .zip.
2. If the remote version is newer, the user sees a banner.
3. On confirm, the .zip is downloaded, unpacked into /tmp.
4. A helper bash script waits for Vox to exit, replaces the .app in
   /Applications and launches it again.
"""
import os
import sys
import ssl
import json
import time
import shutil
import zipfile
import logging
import tempfile
import subprocess
from pathlib import Path
from urllib.request import urlopen, Request

from config import (
    __version__, UPDATE_URL, UPDATE_CHECK_INTERVAL_HOURS,
    APP_SUPPORT,
)

logger = logging.getLogger(__name__)

LAST_CHECK_FILE = APP_SUPPORT / "last_update_check.txt"


# ─── SSL context ─────────────────────────────────────────────
def _ssl_context():
    """
    Return an SSL context. Prefer certifi's CA bundle when available,
    so HTTPS works even on Python builds without system certificates
    (a common issue on macOS with python.org installers).
    """
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception as e:
        logger.debug(f"certifi not available, using default: {e}")
        return ssl.create_default_context()


# ─── Version helpers ─────────────────────────────────────────
def parse_version(v):
    """'1.0.0' -> (1, 0, 0, 0). Bad parts become zeros."""
    if not v:
        return (0, 0, 0, 0)
    parts = str(v).strip().split(".")
    nums = []
    for p in parts:
        try:
            nums.append(int(p))
        except ValueError:
            nums.append(0)
    while len(nums) < 4:
        nums.append(0)
    return tuple(nums[:4])


def is_newer(remote, current):
    """True if remote > current."""
    return parse_version(remote) > parse_version(current)


# ─── Manifest fetch ──────────────────────────────────────────
def _cache_bust(url):
    """Append a random query param so GitHub doesn't serve a cached copy."""
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}_={int(time.time() * 1000)}"


def fetch_manifest():
    """Fetch version.json. Returns dict or None."""
    try:
        req = Request(_cache_bust(UPDATE_URL), headers={
            "User-Agent": f"Vox/{__version__}",
            "Cache-Control": "no-cache, no-store",
            "Pragma": "no-cache",
        })
        with urlopen(req, timeout=10, context=_ssl_context()) as resp:
            raw = resp.read().decode("utf-8")
        return json.loads(raw)
    except Exception as e:
        logger.info(f"update: fetch failed: {e}")
        return None


def check_for_update():
    """
    Returns dict {'version', 'download_url', 'notes'} if a newer version
    exists, otherwise None.
    """
    data = fetch_manifest()
    if not data:
        return None

    remote_v = data.get("version")
    if not remote_v:
        logger.info("update: version.json has no 'version' field")
        return None

    if not is_newer(remote_v, __version__):
        logger.info(f"update: {remote_v} is not newer than {__version__}")
        return None

    logger.info(f"update: version {remote_v} is available")
    return data


def should_check():
    """Has enough time passed since the last check?"""
    try:
        if not LAST_CHECK_FILE.exists():
            return True
        last = float(LAST_CHECK_FILE.read_text().strip())
        elapsed_h = (time.time() - last) / 3600
        return elapsed_h >= UPDATE_CHECK_INTERVAL_HOURS
    except Exception:
        return True


def mark_checked():
    """Remember the time of the last check."""
    try:
        LAST_CHECK_FILE.write_text(str(time.time()))
    except Exception as e:
        logger.debug(f"update: mark_checked failed: {e}")


def check_for_update_if_due():
    """
    Checks for updates if enough time has passed since the last check.
    Safe to call from a background thread.
    """
    if not should_check():
        return None
    mark_checked()
    return check_for_update()


# ─── Download ────────────────────────────────────────────────
def download_file(url, dest, on_progress=None):
    """Download url to dest. Calls on_progress(done, total) as it goes."""
    on_progress = on_progress or (lambda d, t: None)
    req = Request(url, headers={"User-Agent": f"Vox/{__version__}"})

    with urlopen(req, timeout=30, context=_ssl_context()) as resp:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        chunk_size = 256 * 1024

        with open(dest, "wb") as f:
            while True:
                buf = resp.read(chunk_size)
                if not buf:
                    break
                f.write(buf)
                done += len(buf)
                on_progress(done, total)

    return dest


# ─── Install ─────────────────────────────────────────────────
def _find_app_bundle():
    """
    Path to the current .app bundle, or None if running from source
    (python main.py).
    """
    for candidate in (sys.executable,
                      sys.argv[0] if sys.argv else ""):
        if ".app/Contents/MacOS/" in candidate:
            app_path = candidate.split(".app/Contents/MacOS/")[0] + ".app"
            return Path(app_path)
    return None


def install_update(zip_path, on_status=None):
    """
    Unpack the downloaded zip and replace the current Vox.app.
    Returns True if the helper script was launched. The app itself
    should exit right after — the swap happens outside the app.
    """
    on_status = on_status or (lambda m: None)
    zip_path = Path(zip_path)

    if not zip_path.exists():
        raise FileNotFoundError(f"File not found: {zip_path}")

    current_app = _find_app_bundle()
    if current_app is None:
        raise RuntimeError(
            "Vox is not running from a .app bundle. "
            "Auto-update is only available for the built app."
        )

    tmp_dir = Path(tempfile.mkdtemp(prefix="vox_update_"))
    on_status("Unpacking…")

    with zipfile.ZipFile(zip_path) as z:
        z.extractall(tmp_dir)

    new_app = None
    for candidate in tmp_dir.rglob("Vox.app"):
        new_app = candidate
        break

    if new_app is None or not new_app.exists():
        raise RuntimeError("Vox.app not found inside the archive")

    # Move the unpacked bundle out of tmp_dir so the cleanup
    # at the end doesn't wipe it.
    staging = Path(tempfile.mkdtemp(prefix="vox_staging_"))
    staged_app = staging / "Vox.app"
    shutil.move(str(new_app), str(staged_app))

    # Helper script lives outside temp dirs so it survives cleanup.
    helper = Path(tempfile.gettempdir()) / "vox_update_helper.sh"
    helper.write_text(f"""#!/bin/bash
# Wait for Vox to exit
sleep 1

# Swap the app bundle
rm -rf "{current_app}"
mv "{staged_app}" "{current_app}"
xattr -cr "{current_app}" 2>/dev/null

# Launch the updated Vox
open "{current_app}"

# Clean up
rm -rf "{staging}"
rm -rf "{tmp_dir}"
rm -f "{helper}"
""")
    os.chmod(helper, 0o755)

    on_status("Restarting…")

    subprocess.Popen(
        ["/bin/bash", str(helper)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    return True