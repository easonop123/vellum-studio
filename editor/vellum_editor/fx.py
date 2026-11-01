"""Frame effects, ported from the reference scripts (v4/v6/v7/v8) and made resolution-independent.

All pixel amounts are written in 1920x1080 "master" units and multiplied by the
render scale, so a 480x270 test render looks like a shrunk full render.
"""
from __future__ import annotations

import math
import random
from functools import lru_cache

import numpy as np
from PIL import Image, ImageFilter, ImageOps

WHITE = (255, 255, 255)
RED = (214, 24, 32)  # hero title red (#D61820)
BRED = (255, 77, 61)  # safelight (#FF4D3D)
BONE = (237, 234, 228)
GREY = (150, 146, 140)
BLACK = (10, 10, 12)


def ease(p: float) -> float:
    p = max(0.0, min(1.0, p))
    return p * p * (3 - 2 * p)


def scale_c(im: Image.Image, s: float, cx: float = 0.5, cy: float = 0.5) -> Image.Image:
    """Zoom in by s, keeping (cx, cy) fixed."""
    if abs(s - 1) < 1e-3:
        return im
    w, h = im.size
    nw, nh = int(w * s), int(h * s)
    big = im.resize((nw, nh), Image.BILINEAR)
    x, y = int((nw - w) * cx), int((nh - h) * cy)
    return big.crop((x, y, x + w, y + h))


def zoomblur(im: Image.Image, amt: float, n: int = 8) -> Image.Image:
    w, h = im.size
    sw, sh = max(2, w // 2), max(2, h // 2)
    sm = im.resize((sw, sh))
    acc = np.zeros((sh, sw, 3), np.float32)
    for j in range(n):
        acc += np.asarray(scale_c(sm, 1 + amt * 0.28 * j / (n - 1)), np.float32)
    return Image.fromarray((acc / n).astype(np.uint8)).resize((w, h), Image.BILINEAR)


def mblur(im: Image.Image, px: float, n: int = 14) -> Image.Image:
    """Horizontal whip blur. px in pixels at the image's own size."""
    w, h = im.size
    sw, sh = max(2, w // 2), max(2, h // 2)
    a = np.asarray(im.resize((sw, sh)), np.float32)
    acc = np.zeros_like(a)
    p = px / 2 / 2  # half-size image, half the spread each side
    for j in range(n):
        acc += np.roll(a, int(p * (j / (n - 1) - 0.5) * 2), 1)
    return Image.fromarray((acc / n).astype(np.uint8)).resize((w, h), Image.BILINEAR)


def shake(im: Image.Image, amp: float, split: float, seed: int) -> Image.Image:
    r = random.Random(seed)
    a = np.asarray(im)
    dx, dy = int(r.uniform(-1, 1) * amp), int(r.uniform(-1, 1) * amp)
    a = np.roll(a, (dy, dx), (0, 1)).copy()
    if split >= 1:
        s = int(split)
        a[:, :, 0] = np.roll(a[:, :, 0], s, 1)
        a[:, :, 2] = np.roll(a[:, :, 2], -s, 1)
    return Image.fromarray(a)


def rgbsplit(im: Image.Image, s: int) -> Image.Image:
    a = np.asarray(im).copy()
    a[:, :, 0] = np.roll(a[:, :, 0], s, 1)
    a[:, :, 2] = np.roll(a[:, :, 2], -s, 1)
    return Image.fromarray(a)


def flash(im: Image.Image, a: float, colour=WHITE) -> Image.Image:
    return Image.blend(im, Image.new("RGB", im.size, colour), max(0.0, min(1.0, a)))


def bw(im: Image.Image) -> Image.Image:
    return ImageOps.autocontrast(ImageOps.grayscale(im), cutoff=0.5).convert("RGB")


@lru_cache(maxsize=4)
def _grids(w: int, h: int) -> tuple[np.ndarray, np.ndarray]:
    return np.linspace(0, 1, w, dtype=np.float32)[None, :], np.linspace(0, 1, h, dtype=np.float32)[:, None]


def burn(im: Image.Image, p: float, cx: float | None = None) -> Image.Image:
    """Warm light-leak sweep across the frame (p goes 0 -> 1)."""
    w, h = im.size
    X, Y = _grids(w, h)
    cx = -0.2 + 1.4 * p if cx is None else cx
    g = np.exp(-(((X - cx) / 0.45) ** 2 + ((Y - 0.5) / 0.8) ** 2)) * min(1.0, 2.2 * math.sin(math.pi * min(1.0, p)) + 0.2)
    col = np.stack([255 * g, 150 * g, 70 * g], -1)
    a = np.asarray(im, np.float32)
    a = 255 - (255 - a) * (255 - col) / 255
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def bloom(im: Image.Image, g: float) -> Image.Image:
    """Overexposed glow (used to swell into white flashes)."""
    w, h = im.size
    a = np.asarray(im, np.float32) * g
    sm = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).resize((max(2, w // 4), max(2, h // 4)))
    sm = sm.filter(ImageFilter.GaussianBlur(max(1, w / 192))).resize((w, h), Image.BILINEAR)
    b = np.asarray(sm, np.float32)
    a = 255 - (255 - np.clip(a, 0, 255)) * (255 - b * min(1.0, g - 1)) / 255
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def glitch(im: Image.Image, j: int, scale: float) -> Image.Image:
    w, h = im.size
    r = random.Random(j * 7)
    a = np.asarray(im, np.float32)
    a = a * np.array([1.0, 0.25, 0.22]) + np.array([90, 0, 0])
    a = np.clip(a * 1.4, 0, 255).astype(np.uint8)
    for _ in range(6):
        y = r.randrange(0, max(1, h - int(80 * scale)))
        hh = r.randrange(max(1, int(20 * scale)), max(2, int(90 * scale)))
        a[y : y + hh] = np.roll(a[y : y + hh], r.randrange(-int(160 * scale) - 1, int(160 * scale) + 1), 1)
    out = rgbsplit(Image.fromarray(a), max(1, int(14 * scale)))
    if j == 2:
        from PIL import ImageDraw

        d = ImageDraw.Draw(out)
        x = r.randrange(int(w * 0.26), int(w * 0.62))
        d.rectangle([x, 0, x + int(170 * scale), h], fill=(40, 220, 225))
    return out


def border(im: Image.Image, j: int, scale: float) -> Image.Image:
    """Red frame that snaps shut over 3 frames."""
    from PIL import ImageDraw

    t = [46, 30, 16][j] * scale if j < 3 else 0
    if t >= 1:
        w, h = im.size
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, w, t], fill=(226, 30, 38))
        d.rectangle([0, h - t, w, h], fill=(226, 30, 38))
        d.rectangle([0, 0, t, h], fill=(226, 30, 38))
        d.rectangle([w - t, 0, w, h], fill=(226, 30, 38))
    return im


class Finisher:
    """Highlight bloom + vignette + film grain: the last step on every graded frame."""

    def __init__(self, w: int, h: int, bloom_amt: float, vignette: float, grain: float, seed: int = 3):
        X, Y = _grids(w, h)
        r = np.sqrt(((X - 0.5) / 0.62) ** 2 + ((Y - 0.5) / 0.62) ** 2)
        self.vig = np.clip(1 - vignette * np.clip(r - 0.55, 0, 1) ** 1.6 * 2.2, 0.55, 1)[..., None].astype(np.float32)
        self.bloom_amt = bloom_amt
        self.grain_amt = grain
        self.grain: list[np.ndarray] = []
        if grain > 0:
            rng = np.random.default_rng(seed)
            gw, gh = max(2, w // 2), max(2, h // 2)
            for _ in range(6):
                g = (rng.normal(0, 1, (gh, gw)) * grain + 128).clip(0, 255).astype(np.uint8)
                self.grain.append((np.asarray(Image.fromarray(g).resize((w, h), Image.BILINEAR), np.float32) - 128))
        self.w, self.h = w, h

    def __call__(self, im: Image.Image, f: int) -> Image.Image:
        a = np.asarray(im, np.float32)
        if self.bloom_amt > 0:
            sw, sh = max(2, self.w // 4), max(2, self.h // 4)
            sm = np.asarray(im.resize((sw, sh)), np.float32)
            hi = np.clip((sm.max(2, keepdims=True) - 170) / 85, 0, 1) * sm
            bl = Image.fromarray(hi.astype(np.uint8)).filter(ImageFilter.GaussianBlur(max(1, self.w / 213)))
            bl = np.asarray(bl.resize((self.w, self.h), Image.BILINEAR), np.float32)
            a = 255 - (255 - a) * (255 - bl * self.bloom_amt) / 255
        a = a * self.vig
        if self.grain:
            a = a + self.grain[f % len(self.grain)][..., None]
        return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def outline_place(canvas: Image.Image, img: Image.Image, mask: Image.Image, x: int, y: int, scale: float, outline: float = 1.0) -> None:
    """Paste a cut-out person with a white sticker outline and a soft drop shadow."""
    k = max(3, int(17 * scale) | 1)
    ol = mask.filter(ImageFilter.MaxFilter(k))
    sh = ol.filter(ImageFilter.GaussianBlur(max(1, 14 * scale))).point(lambda v: int(v * 0.5))
    canvas.paste((0, 0, 0), (x + int(10 * scale), y + int(16 * scale)), sh)
    if outline > 0:
        canvas.paste((255, 255, 255), (x, y), ol.point(lambda v: int(v * outline)))
    canvas.paste(img, (x, y), mask)
