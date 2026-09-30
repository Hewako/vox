"""
Animated settings icon player.

Loads the PNG frame sequence produced by
`scripts/render_settings_icon.py` and plays it on demand on a Label.
Used for the settings button in the main window.

Frames are downscaled on load to a small display size suitable for
the header. Playback is one-shot: play_once() runs the full sequence
and returns to the idle frame.
"""

import logging
from pathlib import Path

from PIL import Image, ImageTk

logger = logging.getLogger(__name__)


# ─── Config ──────────────────────────────────────────────────
FRAME_DELAY_MS = 33  # ~30 fps, matches the source Lottie timeline
DISPLAY_SIZE = 26  # icon size in the header, in pixels

_ASSETS = Path(__file__).parent.parent / "assets" / "settings_anim"


class SettingsIconPlayer:
    """
    Plays the settings icon animation on a tkinter Label.

    Usage:
        player = SettingsIconPlayer(root, label_widget)
        player.show_idle()               # show first frame
        player.play_once(on_done=...)    # animate once, return to idle
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
        if not _ASSETS.exists():
            logger.warning("settings_icon: frame folder not found at %s", _ASSETS)
            return

        paths = sorted(_ASSETS.glob("frame_*.png"))
        if not paths:
            logger.warning("settings_icon: no frame_*.png files in %s", _ASSETS)
            return

        try:
            for p in paths:
                img = Image.open(p).convert("RGBA")
                if img.width != DISPLAY_SIZE:
                    img = img.resize((DISPLAY_SIZE, DISPLAY_SIZE), Image.Resampling.LANCZOS)
                self.frames.append(ImageTk.PhotoImage(img))
            logger.info(
                "settings_icon: loaded %d frames at %dpx",
                len(self.frames),
                DISPLAY_SIZE,
            )
        except Exception as e:
            logger.error(f"settings_icon: failed to load frames: {e}")
            self.frames = []

    def is_ready(self):
        return len(self.frames) > 0

    # ─── Playback ────────────────────────────────────────────
    def show_idle(self):
        """Show the first frame (icon at rest)."""
        if not self.frames:
            return
        self.idx = 0
        self._display(0)

    def play_once(self, on_done=None):
        """
        Play the whole sequence once and return to the idle frame.
        Does nothing if the animation is already running.
        """
        if not self.frames or self.after_id is not None:
            return
        self._on_done = on_done
        self.idx = 0
        self._tick_once()

    # ─── Internals ───────────────────────────────────────────
    def _display(self, index):
        img = self.frames[index]
        self.label.config(image=img)
        self.label.image = img  # keep reference, GC safety

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
