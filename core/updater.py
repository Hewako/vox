"""
Update checker and installer for Vox.

How it works:

1. On startup, and once a day after that, the app fetches version.json
   from the repo. It holds the current version and a download URL for
   the .zip.
2. If the remote version is newer, the user sees the update dialog.
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
    One-shot check used by the manual button. Always hits the network.
    Returns dict {'version', 'download_url', 'notes'} if a newer
    version exists, otherwise None.
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


# ─── Time-gated auto check ───────────────────────────────────
def should_check():
    """Has enough time passed since the last successful check?"""
    try:
        if not LAST_CHECK_FILE.exists():
            return True
        last = float(LAST_CHECK_FILE.read_text().strip())
        elapsed_h = (time.time() - last) / 3600
        return elapsed_h >= UPDATE_CHECK_INTERVAL_HOURS
    except Exception:
        return True


def mark_checked():
    """Remember the time of the last successful check."""
    try:
        LAST_CHECK_FILE.write_text(str(time.time()))
    except Exception as e:
        logger.debug(f"update: mark_checked failed: {e}")


def check_for_update_if_due():
    """
    Auto check used on startup. Only hits the network if at least
    UPDATE_CHECK_INTERVAL_HOURS have passed since the last successful
    fetch. If the fetch fails (offline, DNS issue, ...), the interval
    file is NOT updated, so the next launch will retry.

    Safe to call from a background thread.
    Returns the manifest dict if a newer version is available,
    otherwise None.
    """
    if not should_check():
        logger.debug("update: skipping auto check, not due yet")
        return None

    data = fetch_manifest()
    if data is None:
        # Fetch failed. Don't touch the marker, retry next launch.
        return None

    # Fetch succeeded — remember this moment.
    mark_checked()

    remote_v = data.get("version")
    if not remote_v:
        logger.info("update: version.json has no 'version' field")
        return None

    if not is_newer(remote_v, __version__):
        logger.info(f"update: {remote_v} is not newer than {__version__}")
        return None

    logger.info(f"update: version {remote_v} is available")
    return data


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

    # Use ditto instead of zipfile.extractall so that unix permissions
    # (in particular the executable bit on Contents/MacOS/*) are
    # preserved. zipfile.extractall() silently drops them, which makes
    # the resulting .app impossible to launch.
    ditto = "/usr/bin/ditto"
    unpack = subprocess.run(
        [ditto, "-x", "-k", str(zip_path), str(tmp_dir)],
        capture_output=True, text=True,
    )
    if unpack.returncode != 0:
        raise RuntimeError(
            f"ditto failed to unpack archive: {unpack.stderr.strip()}"
        )

    new_app = None
    for candidate in tmp_dir.rglob("Vox.app"):
        new_app = candidate
        break

    if new_app is None or not new_app.exists():
        raise RuntimeError("Vox.app not found inside the archive")

    # Sanity check: the main binary must be executable. If not, fix it
    # so we do not ship a broken bundle if ditto misbehaves.
    vox_bin = new_app / "Contents" / "MacOS" / "Vox"
    if vox_bin.exists() and not os.access(vox_bin, os.X_OK):
        logger.warning("update: Vox binary is not executable, fixing perms")
        os.chmod(vox_bin, 0o755)

    # Move the unpacked bundle out of tmp_dir so the cleanup
    # at the end doesn't wipe it.
    staging = Path(tempfile.mkdtemp(prefix="vox_staging_"))
    staged_app = staging / "Vox.app"
    shutil.move(str(new_app), str(staged_app))

    # Helper script lives outside temp dirs so it survives cleanup.
    helper = Path(tempfile.gettempdir()) / "vox_update_helper.sh"
    helper_log = Path.home() / "Library" / "Logs" / "Vox-update-helper.log"
    lsregister = (
        "/System/Library/Frameworks/CoreServices.framework/"
        "Frameworks/LaunchServices.framework/Support/lsregister"
    )

    helper.write_text(f"""#!/bin/bash
exec >> "{helper_log}" 2>&1
set -x
echo "===== $(date) helper started ====="
echo "current_app={current_app}"
echo "staged_app={staged_app}"

sleep 1

echo "removing old app..."
rm -rf "{current_app}"

echo "moving new app into place..."
mv "{staged_app}" "{current_app}"

echo "clearing xattrs..."
xattr -cr "{current_app}" 2>/dev/null

echo "re-registering with LaunchServices..."
"{lsregister}" -f "{current_app}" || true
sleep 1

echo "launching via open..."
open "{current_app}"

sleep 3
if ! pgrep -f "{current_app}/Contents/MacOS/Vox" > /dev/null; then
    echo "open failed, falling back to direct launch"
    "{current_app}/Contents/MacOS/Vox" &
fi

echo "cleaning up..."
rm -rf "{staging}"
rm -rf "{tmp_dir}"
rm -f "{helper}"
echo "===== helper done ====="
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