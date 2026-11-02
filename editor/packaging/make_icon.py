"""Draw the app icon (a black tile with the safelight REC dot and VS monogram) as a macOS .iconset."""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
FONT = HERE.parent / "vellum_editor" / "assets" / "fonts" / "SpaceGrotesk.ttf"


def tile(size: int) -> Image.Image:
    s = size / 1024
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([int(100 * s), int(100 * s), int(924 * s), int(924 * s)], radius=int(185 * s), fill=(13, 13, 15, 255))
    d.ellipse([int(250 * s), int(250 * s), int(370 * s), int(370 * s)], fill=(255, 77, 61, 255))
    f = ImageFont.truetype(str(FONT), int(360 * s))
    try:
        f.set_variation_by_name("Bold")
    except Exception:
        pass
    d.text((int(250 * s), int(420 * s)), "VS", font=f, fill=(237, 234, 228, 255))
    return im


def main(out_dir: str) -> None:
    iconset = Path(out_dir)
    iconset.mkdir(parents=True, exist_ok=True)
    for base in (16, 32, 128, 256, 512):
        tile(base).save(iconset / f"icon_{base}x{base}.png")
        tile(base * 2).save(iconset / f"icon_{base}x{base}@2x.png")
    print(f"wrote {iconset}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(HERE / "icon.iconset"))
