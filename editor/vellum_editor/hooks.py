"""Hook versions: alternative two-line openers burned over the vertical file until the drop (reference hooks/mk.py)."""
from __future__ import annotations

import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

from .ffmpeg import probe_json, run
from .text import center_text, tiktok


def hook_overlay(line1: str, line2: str, k: int, w: int, h: int) -> Image.Image:
    s = w / 1080
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 380 * s, w, 640 * s], fill=(0, 0, 0, 255))
    f = tiktok(76 * s, "Bold")
    center_text(d, w, 420 * s, line1, f, (255, 255, 255))
    center_text(d, w, 515 * s, line2, f, (255, 255, 255) if k == 2 else (255, 77, 61))
    return im


def make_hooks(vertical_post: Path, title: str, hooks: list[tuple[str, str]], drop_seconds: float, out_dir: Path) -> list[Path]:
    info = probe_json(vertical_post)
    v = next(s for s in info["streams"] if s.get("codec_type") == "video")
    w, h = int(v["width"]), int(v["height"])
    made = []
    with tempfile.TemporaryDirectory(prefix="vellum-hook-") as tmp:
        for k, (l1, l2) in enumerate(hooks, start=2):
            if not (l1.strip() or l2.strip()):
                continue
            png = Path(tmp) / f"hook{k}.png"
            hook_overlay(l1.strip(), l2.strip(), k, w, h).save(png)
            out = out_dir / f"{title} - vertical HOOK {k} (post this).mp4"
            run([
                "-i", str(vertical_post), "-i", str(png),
                "-filter_complex", f"[0:v][1:v]overlay=0:0:enable='lt(t,{drop_seconds:.3f})'",
                "-c:v", "libx264", "-crf", "17", "-preset", "medium", "-pix_fmt", "yuv420p",
                "-c:a", "copy", "-movflags", "+faststart", str(out),
            ])
            made.append(out)
    return made
