"""Render settings icon frames from the Lottie source."""
import sys
from pathlib import Path

from PIL import Image
from rlottie_python import LottieAnimation

# Config
PROJECT = Path(__file__).parent.parent
SRC = PROJECT / "assets" / "settings_anim.json"
OUT_DIR = PROJECT / "assets" / "settings_anim"

# Output size. Source Lottie is 32x32; we render at 64 for retina.
SIZE = 64

# Icon color: light gray similar to FG_SUBTLE from config, so the
# icon reads clearly on the dark background. Change if theme changes.
TARGET_COLOR = (200, 200, 205, 255)   # RGBA

def recolor(img: Image.Image, color: tuple) -> Image.Image:
    """
    Replace the icon's RGB with a single color, using the original
    alpha channel as the mask. Produces a clean monochrome icon
    regardless of whatever colors the Lottie source used.
    """
    img = img.convert("RGBA")
    alpha = img.split()[-1]
    solid = Image.new("RGBA", img.size, color)
    solid.putalpha(alpha)
    return solid

def main():
    if not SRC.exists():
        print(f"Source not found: {SRC}")
        sys.exit(1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    anim = LottieAnimation.from_file(str(SRC))
    total = anim.lottie_animation_get_totalframe()
    print(f"Frames: {total}  Source size: {anim.lottie_animation_get_size()}")
    print(f"Rendering to {SIZE}x{SIZE} ...")

    for i in range(total):
        raw = anim.render_pillow_frame(frame_num=i, width=SIZE, height=SIZE)
        if i == 0:
            print(f"  frame 0 mode = {raw.mode}, size = {raw.size}")
        frame = recolor(raw, TARGET_COLOR)
        out = OUT_DIR / f"frame_{i:02d}.png"
        frame.save(out)

    print(f"Done: {total} frames -> {OUT_DIR}")

if __name__ == "__main__":
    main()
