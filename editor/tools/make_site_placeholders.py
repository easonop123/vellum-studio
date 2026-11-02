"""Render placeholder demo videos for the website (public/demos/).

Abstract, procedurally drawn "night city" scenes laid out like a Vellum
vertical edit: raw intro, white flash, red title, graded beat cuts, REC bar.
No real footage and no music, so nothing copyrighted ends up in the repo.

    python editor/tools/make_site_placeholders.py

Swap these for real exports later (see YOUR-STEPS.md).
"""
from __future__ import annotations

import math
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "public" / "demos"
FONTS = ROOT / "editor" / "vellum_editor" / "assets" / "fonts"
FPS = 24

THEMES = {
    "tokyo": dict(sky=((8, 6, 24), (40, 10, 52)), lights=[(255, 60, 170), (60, 220, 255), (255, 210, 120), (150, 90, 255)]),
    "italy": dict(sky=((30, 14, 10), (120, 60, 30)), lights=[(255, 190, 110), (255, 140, 70), (255, 230, 170), (200, 120, 90)]),
    "new york": dict(sky=((6, 10, 22), (30, 40, 70)), lights=[(255, 180, 80), (255, 230, 160), (120, 170, 255), (255, 120, 60)]),
}


def font(name: str, size: int, variation: str | None = None) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(FONTS / name), size)
    if variation:
        try:
            f.set_variation_by_name(variation)
        except Exception:
            pass
    return f


# ---------------------------------------------------------------- scenes

class Scene:
    """A drifting field of bokeh lights over a skyline, seeded per shot."""

    def __init__(self, w: int, h: int, theme: dict, seed: int, kind: int):
        self.w, self.h, self.kind = w, h, kind
        rng = np.random.default_rng(seed)
        top, bottom = (np.array(c, np.float32) / 255 for c in theme["sky"])
        y = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
        self.bg = np.broadcast_to(top * (1 - y) + bottom * y, (h, w, 3)).copy()
        n = 26 if kind == 0 else 14
        self.cx = rng.uniform(-0.1, 1.1, n)
        self.cy = rng.uniform(0.15, 0.95, n)
        self.r = rng.uniform(0.03, 0.11, n) * (1.6 if kind == 0 else 1.0)
        self.col = np.array([theme["lights"][i] for i in rng.integers(0, len(theme["lights"]), n)], np.float32) / 255
        self.amp = rng.uniform(0.25, 0.8, n)
        self.vx = rng.uniform(-0.05, 0.05, n) + (0.09 if kind == 1 else 0)
        self.phase = rng.uniform(0, 6.28, n)
        # skyline silhouette with lit windows
        sk = Image.new("L", (w, h), 0)
        d = ImageDraw.Draw(sk)
        x = 0
        self.windows = []
        while x < w:
            bw = int(rng.uniform(0.07, 0.2) * w)
            bh = int(rng.uniform(0.25, 0.7) * h)
            d.rectangle([x, h - bh, x + bw, h], fill=255)
            for wy in range(h - bh + 6, h - 4, max(4, h // 40)):
                for wx in range(x + 4, x + bw - 4, max(4, w // 50)):
                    if rng.random() < 0.18:
                        self.windows.append((wx, wy, rng.random()))
            x += bw + int(rng.uniform(0, 0.03) * w)
        self.sky_mask = np.asarray(sk, np.float32)[..., None] / 255
        self.win_col = np.array(theme["lights"][0], np.float32) / 255
        self.yy, self.xx = np.mgrid[0:h, 0:w].astype(np.float32)

    def frame(self, t: float) -> np.ndarray:
        img = self.bg.copy()
        pan = t * (0.02 if self.kind != 1 else 0.06)
        for i in range(len(self.cx)):
            cx = ((self.cx[i] + self.vx[i] * t + pan) % 1.3 - 0.15) * self.w
            cy = self.cy[i] * self.h
            r = self.r[i] * self.w
            x0, x1 = int(max(0, cx - r - 2)), int(min(self.w, cx + r + 2))
            y0, y1 = int(max(0, cy - r - 2)), int(min(self.h, cy + r + 2))
            if x1 <= x0 or y1 <= y0:
                continue
            dist = np.hypot(self.xx[y0:y1, x0:x1] - cx, self.yy[y0:y1, x0:x1] - cy) / r
            disc = np.clip((1.0 - dist) * 6, 0, 1) * (0.55 + 0.45 * dist.clip(0, 1))
            a = self.amp[i] * (0.75 + 0.25 * math.sin(t * 2.3 + self.phase[i]))
            img[y0:y1, x0:x1] += disc[..., None] * self.col[i] * a
        # buildings in front, with a few windows twinkling
        img = img * (1 - self.sky_mask * 0.92)
        for wx, wy, ph in self.windows:
            if math.sin(t * 1.7 + ph * 40) > -0.6:
                img[wy:wy + 2, wx:wx + 2] += self.win_col * 0.9
        return np.clip(img, 0, 1)


# ---------------------------------------------------------------- looks

def raw_look(a: np.ndarray) -> np.ndarray:
    """Straight-off-the-phone: flat and a little washed out (like the intro of an edit)."""
    g = a.mean(axis=2, keepdims=True)
    a = g + (a - g) * 0.62
    a = (a - 0.5) * 0.82 + 0.5 + 0.035
    return np.clip(a, 0, 1)


_VIG: dict[tuple[int, int], np.ndarray] = {}


def graded_look(a: np.ndarray) -> np.ndarray:
    """Darkroom grade: contrast, saturation, teal shadows, warm highlights, lifted blacks, vignette."""
    h, w, _ = a.shape
    a = (a - 0.5) * 1.10 + 0.5
    g = a.mean(axis=2, keepdims=True)
    a = np.clip(g + (a - g) * 1.14, 0, 1)
    lum = a.mean(axis=2, keepdims=True)
    shadows = np.clip(1 - lum * 2, 0, 1)
    highs = np.clip(lum * 2 - 1, 0, 1)
    a = a + shadows * np.array([-0.07, -0.01, 0.09]) * 0.6 + highs * np.array([0.09, 0.03, -0.07]) * 0.6
    a = 0.035 + a * (0.97 - 0.035)
    if (h, w) not in _VIG:
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        r = np.hypot((xx / w - 0.5) / 0.62, (yy / h - 0.5) / 0.62)
        _VIG[(h, w)] = np.clip(1 - 0.38 * np.clip(r - 0.55, 0, 1) ** 1.6 * 2.2, 0.55, 1)[..., None]
    return np.clip(a * _VIG[(h, w)], 0, 1)


def to_img(a: np.ndarray) -> Image.Image:
    return Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))


# ---------------------------------------------------------------- vertical edit layout

def vertical_edit(title: str, theme: dict, seconds: float, seed: int, w: int = 540, h: int = 960):
    """Frames laid out like the house vertical: picture band in the middle, text above, REC bar below."""
    bpm = 124.0
    beat = 60 / bpm
    drop = 8 * beat / 2  # four beats of raw intro
    band_h = int(w * 9 / 16)
    band_y = int(h * 656 / 1920)
    n = int(seconds * FPS)
    tt_big = font("TikTokSans.ttf", int(w * 0.057), "Bold")
    tt_small = font("TikTokSans.ttf", int(w * 0.031), "Medium")
    tt_bar = font("TikTokSans.ttf", int(w * 0.028), "SemiBold")
    mono = font("JetBrainsMono.ttf", int(w * 0.022), "Medium")
    anton = font("Anton.ttf", int(band_h * 0.62))
    shots = [Scene(w, band_h, theme, seed * 100 + k, k % 3) for k in range(24)]
    title_up = title.upper()

    for f in range(n):
        t = f / FPS
        rel = t - drop
        canvas = Image.new("RGB", (w, h), (0, 0, 0))
        d = ImageDraw.Draw(canvas)
        if rel < 0:
            k = int(t / (beat / 2))
            frame = to_img(raw_look(shots[k % 6].frame(t)))
            fd = ImageDraw.Draw(frame)
            fd.text((10, band_h - 24), f"IMG_{4821 + k * 7}.MOV", font=mono, fill=(255, 255, 255))
            canvas.paste(frame, (0, band_y))
            msg, sub = "the clips they sent me", "no edit, no grade"
        else:
            k = int(rel / (beat / 2))
            hold = rel < beat * 3
            shot = shots[6] if hold else shots[7 + k % 17]
            a = graded_look(shot.frame(t))
            if hold:  # hero title behind the light field
                n_letters = min(len(title_up), int(rel * FPS) // 2)
                layer = Image.new("L", (w, band_h), 0)
                ImageDraw.Draw(layer).text(
                    ((w - anton.getlength(title_up)) / 2, band_h * 0.12), title_up[:n_letters], font=anton, fill=255
                )
                m = np.asarray(layer, np.float32)[..., None] / 255
                red = np.array([214, 24, 32], np.float32) / 255
                a = a * (1 - m) + red * m
            img = to_img(a)
            fi = int(rel * FPS) % int(beat * FPS / 2)
            if fi == 0 and not hold:  # punch-in on each cut
                img = img.resize((int(w * 1.08), int(band_h * 1.08))).crop((int(w * 0.04), int(band_h * 0.04), int(w * 0.04) + w, int(band_h * 0.04) + band_h))
            if int(rel * FPS) < 2:  # white flash on the drop
                img = Image.blend(img, Image.new("RGB", img.size, (255, 255, 255)), 0.85 if int(rel * FPS) == 0 else 0.45)
            canvas.paste(img, (0, band_y))
            msg, sub = "what i made with them", None
            e = int(rel * FPS)
            by = band_y + band_h + int(h * 0.018)
            d.text((int(w * 0.04), by), "@vellumstudio.edits", font=tt_bar, fill=(200, 200, 200))
            if (e // 12) % 2 == 0:
                r = int(w * 0.0095)
                cy = by + int(tt_bar.size * 0.62)
                d.ellipse([w - int(w * 0.28) - 2 * r, cy - r, w - int(w * 0.28), cy + r], fill=(255, 77, 61))
            d.text((w - int(w * 0.265), by), f"REC {e // FPS // 60:02d}:{e // FPS % 60:02d}", font=tt_bar, fill=(230, 230, 230))
        tw = d.textlength(msg, font=tt_big)
        d.text(((w - tw) / 2, band_y - int(h * 0.08)), msg, font=tt_big, fill=(255, 255, 255))
        if sub:
            sw = d.textlength(sub, font=tt_small)
            d.text(((w - sw) / 2, band_y + band_h + int(h * 0.02)), sub, font=tt_small, fill=(170, 170, 170))
        yield canvas


def wipe_pair(theme: dict, seconds: float, seed: int, w: int = 540, h: int = 676):
    scene = Scene(w, h, theme, seed, 0)
    for f in range(int(seconds * FPS)):
        a = scene.frame(f / FPS)
        yield to_img(raw_look(a)), to_img(graded_look(a))


# ---------------------------------------------------------------- encode

def encoder(path: Path, w: int, h: int, crf: int = 30) -> subprocess.Popen:
    return subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(FPS), "-i", "-",
         "-c:v", "libx264", "-preset", "slow", "-crf", str(crf), "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-an", str(path)],
        stdin=subprocess.PIPE,
    )


def write_video(path: Path, frames, poster_at: int, poster: Path | None = None):
    proc = None
    for i, img in enumerate(frames):
        if proc is None:
            proc = encoder(path, *img.size)
        proc.stdin.write(img.tobytes())
        if poster and i == poster_at:
            img.save(poster, quality=82, optimize=True, progressive=True)
    proc.stdin.close()
    proc.wait()
    print(f"{path.name}: {path.stat().st_size / 1024:.0f} KB")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    write_video(OUT / "hero.mp4", vertical_edit("tokyo", THEMES["tokyo"], 7.5, 1), poster_at=84, poster=OUT / "hero.jpg")
    for i, (slug, name) in enumerate([("tokyo", "tokyo"), ("italy", "italy"), ("new-york", "new york")]):
        write_video(OUT / f"{slug}.mp4", vertical_edit(name, THEMES[name], 7.5, 10 + i), poster_at=84, poster=OUT / f"{slug}.jpg")
    raw_frames, edit_frames = [], []
    for r, e in wipe_pair(THEMES["new york"], 6.0, 77):
        raw_frames.append(r)
        edit_frames.append(e)
    write_video(OUT / "raw.mp4", iter(raw_frames), poster_at=0)
    write_video(OUT / "edit.mp4", iter(edit_frames), poster_at=0, poster=OUT / "edit.jpg")


if __name__ == "__main__":
    main()
