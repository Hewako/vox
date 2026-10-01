"""
Animated settings icon player.

Loads the PNG frame sequence produced by
`scripts/render_settings_icon.py` and plays it on demand on a Label.

The frames folder is searched in several locations so the icon works
both when the app runs from source and inside a bundled .app:
  - <project>/assets/settings_anim                      (source tree)
  - <Vox.app>/Contents/Resources/assets/settings_anim   (bundled)
"""
import logging
import sys
from pathlib import Path

from PIL import Image, ImageTk

logger = logging.getLogger(__name__)


# ─── Config ──────────────────────────────────────────────────
FRAME_DELAY_MS = 33     # ~30 fps, matches the source Lottie timeline
DISPLAY_SIZE = 26       # icon size in the header, in pixels


def _find_frames_dir():
    """
    Return the directory that holds frame_*.png, or None if not found.
    Tries the source tree first, then the .app bundle.
    """
    candidates = [
        Path(__file__).parent.parent / "assets" / "settings_anim",
    ]

    exe = str(sys.executable)
    if ".app/Contents/MacOS/" in exe:
        app_root = Path(exe.split(".app/Contents/MacOS/")[0] + ".app")
        candidates.append(
            app_root / "Contents" / "Resources" / "assets" / "settings_anim"
        )

    for p in candidates:
        if p.exists() and any(p.glob("frame_*.png")):
            return p
    return None


class SettingsIconPlayer:
    """
    Plays the settings icon animation on a tkinter Label.

    Usage:
        player = SettingsIconPlayer(root, label_widget)
        player.show_idle()
        player.play_once()
    """

    def __init__(self, root, label_widget, delay_ms=FRAME_DELAY_MS):
        self.root = root
        self.label = label_widget
        self.delay_ms = delay_ms
        self.frames = []
        self.idx = 0
        self.after_id = None
        self._on_done = None
        self._load_frames()

    # ─── Loading ─────────────────────────────────────────────
    def _load_frames(self):
        folder = _find_frames_dir()
        if folder is None:
            logger.warning(
                "settings_icon: frames folder not found (checked source "
                "and bundle paths)")
            return

        paths = sorted(folder.glob("frame_*.png"))
        try:
            for p in paths:
                img = Image.open(p).convert("RGBA")
                if img.width != DISPLAY_SIZE:
                    img = img.resize((DISPLAY_SIZE, DISPLAY_SIZE),
                                     Image.Resampling.LANCZOS)
                self.frames.append(ImageTk.PhotoImage(img))
            logger.info("settings_icon: loaded %d frames at %dpx from %s",
                        len(self.frames), DISPLAY_SIZE, folder)
        except Exception as e:
            logger.error(f"settings_icon: failed to load frames: {e}")
            self.frames = []

    def is_ready(self):
        return len(self.frames) > 0

    # ─── Playback ────────────────────────────────────────────
    def show_idle(self):
        if not self.frames:
            return
        self.idx = 0
        self._display(0)

    def play_once(self, on_done=None):
        if not self.frames or self.after_id is not None:
            return
        self._on_done = on_done
        self.idx = 0
        self._tick_once()

    # ─── Internals ───────────────────────────────────────────
    def _display(self, index):
        img = self.frames[index]
        self.label.config(image=img)
        self.label.image = img

    def _tick_once(self):
        if not self.frames:
            return
        self._display(self.idx)
        self.idx += 1
        if self.idx >= len(self.frames):
            self.after_id = None
            self.show_idle()
            cb = self._on_done
            self._on_done = None
            if cb is not None:
                try:
                    cb()
                except Exception as e:
                    logger.debug(f"settings_icon: on_done raised: {e}")
            return
        self.after_id = self.root.after(self.delay_ms, self._tick_once)
