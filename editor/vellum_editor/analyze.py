"""Score every clip and find its best moment; throw out the junk.

Each clip is sampled at 4 frames a second at 192 px (fast, and nothing is
written to disk). Per frame: sharpness, exposure, clipping, colour, motion,
and camera shake. Then: is it usable, how good is it, where does it start
looking its best, where should a crop centre, and how big is the person.
"""
from __future__ import annotations

import base64
import io
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np
from PIL import Image, ImageOps

from . import masks
from .ffmpeg import read_frames
from .looks import tonemap_filter
from .probe import ClipError, ClipInfo, list_media, probe

SAMPLE_FPS = 4.0
SAMPLE_LONG = 192


@dataclass
class ClipAnalysis:
    info: ClipInfo
    usable: bool = True
    reason: str = ""
    score: float = 0.0
    sharpness: float = 0.0
    exposure: float = 0.0
    clipped_hi: float = 0.0
    clipped_lo: float = 0.0
    motion: float = 0.0
    shake: float = 0.0
    colorfulness: float = 0.0
    person: float = 0.0
    best_start: float = 0.0
    moments: list[float] = field(default_factory=list)  # other good start times, best first
    quality: list[float] = field(default_factory=list)  # per-sample quality (4/s), for picking windows later
    focus: tuple[float, float] = (0.5, 0.45)
    night_orange: bool = False
    signature: list[float] = field(default_factory=list)  # colour + layout fingerprint for "too similar" checks
    thumb: str = ""  # small JPEG, base64, for review.html

    @property
    def name(self) -> str:
        return self.info.name

    def to_dict(self) -> dict:
        d = asdict(self)
        d["info"] = self.info.to_dict()
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "ClipAnalysis":
        data = dict(data)
        data["info"] = ClipInfo.from_dict(data["info"])
        data["focus"] = tuple(data.get("focus", (0.5, 0.45)))
        return cls(**data)

    def window_start(self, needed: float) -> float:
        """Start time of the best `needed`-second stretch, using the per-sample quality curve."""
        dur = self.info.duration
        if self.info.kind == "photo" or needed >= dur - 0.05 or not self.quality:
            return 0.0 if self.info.kind == "photo" else max(0.0, min(self.best_start, dur - needed - 0.02))
        q = np.asarray(self.quality, np.float64)
        n = max(1, int(round(needed * SAMPLE_FPS)))
        if n >= len(q):
            return 0.0
        means = np.convolve(q, np.ones(n) / n, mode="valid")
        start = int(np.argmax(means)) / SAMPLE_FPS
        return float(max(0.0, min(start, dur - needed - 0.02)))


def sample_size(info: ClipInfo) -> tuple[int, int]:
    if info.width >= info.height:
        w = SAMPLE_LONG
        h = max(2, int(round(SAMPLE_LONG * info.height / info.width / 2)) * 2)
    else:
        h = SAMPLE_LONG
        w = max(2, int(round(SAMPLE_LONG * info.width / info.height / 2)) * 2)
    return w, h


def sample_frames(info: ClipInfo, lut: str = "") -> np.ndarray:
    w, h = sample_size(info)
    if info.kind == "photo":
        im = load_photo(info.path).resize((w, h), Image.BILINEAR)
        return np.asarray(im, np.uint8)[None]
    chain = [f"fps={SAMPLE_FPS}", f"scale={w}:{h}:flags=bilinear"]
    tm = tonemap_filter(info)
    if tm:
        chain.append(tm)
    if lut:
        chain.append(lut)
    max_frames = int(min(info.duration, 180) * SAMPLE_FPS) + 2
    return read_frames(["-i", info.path, "-t", "180", "-an", "-vf", ",".join(chain)], w, h, max_frames=max_frames)


def load_photo(path: str) -> Image.Image:
    if path.lower().endswith((".heic", ".heif")):
        import pillow_heif

        pillow_heif.register_heif_opener()
    im = Image.open(path)
    return ImageOps.exif_transpose(im).convert("RGB")


# ---------------------------------------------------------------------------- per-frame metrics

def _luma(frames: np.ndarray) -> np.ndarray:
    f = frames.astype(np.float32) / 255.0
    return 0.299 * f[..., 0] + 0.587 * f[..., 1] + 0.114 * f[..., 2]


def _sharpness(y: np.ndarray) -> np.ndarray:
    """Variance of the Laplacian, per frame."""
    lap = -4 * y[:, 1:-1, 1:-1] + y[:, :-2, 1:-1] + y[:, 2:, 1:-1] + y[:, 1:-1, :-2] + y[:, 1:-1, 2:]
    return lap.reshape(len(y), -1).var(axis=1) * 1000.0


def _colorfulness(frames: np.ndarray) -> np.ndarray:
    f = frames.astype(np.float32) / 255.0
    rg = f[..., 0] - f[..., 1]
    yb = 0.5 * (f[..., 0] + f[..., 1]) - f[..., 2]
    n = len(f)
    rg, yb = rg.reshape(n, -1), yb.reshape(n, -1)
    return np.sqrt(rg.std(1) ** 2 + yb.std(1) ** 2) + 0.3 * np.sqrt(rg.mean(1) ** 2 + yb.mean(1) ** 2)


def _shift(a: np.ndarray, b: np.ndarray) -> tuple[float, float]:
    """Global translation between two luma frames by phase correlation."""
    fa, fb = np.fft.fft2(a - a.mean()), np.fft.fft2(b - b.mean())
    r = fa * np.conj(fb)
    r /= np.abs(r) + 1e-9
    c = np.abs(np.fft.ifft2(r))
    dy, dx = np.unravel_index(int(np.argmax(c)), c.shape)
    h, w = a.shape
    if dy > h // 2:
        dy -= h
    if dx > w // 2:
        dx -= w
    return float(dx), float(dy)


def _shake(y: np.ndarray) -> float:
    """Jitter in the camera path (motion minus its smooth trend), as a fraction of frame width."""
    if len(y) < 4:
        return 0.0
    path = np.cumsum([(0.0, 0.0)] + [_shift(y[i], y[i - 1]) for i in range(1, len(y))], axis=0)
    k = 5
    pad = np.pad(path, ((k // 2, k // 2), (0, 0)), mode="edge")
    smooth = np.stack([np.convolve(pad[:, j], np.ones(k) / k, mode="valid") for j in range(2)], axis=1)
    jitter = np.abs(path - smooth).mean()
    return float(jitter / y.shape[2])


def _focus(frame: np.ndarray) -> tuple[float, float]:
    """Where the detail is (gradient energy), used to aim crops when no person is found."""
    y = _luma(frame[None])[0]
    gx = np.abs(np.diff(y, axis=1))[:-1]
    gy = np.abs(np.diff(y, axis=0))[:, :-1]
    g = gx + gy
    g = g - np.percentile(g, 60)
    g = np.clip(g, 0, None)
    total = g.sum()
    if total <= 0:
        return 0.5, 0.45
    ys, xs = np.mgrid[0 : g.shape[0], 0 : g.shape[1]]
    fx = float((g * xs).sum() / total / g.shape[1])
    fy = float((g * ys).sum() / total / g.shape[0])
    # pull toward the centre so crops don't swing around
    return 0.5 + 0.6 * (fx - 0.5), 0.45 + 0.6 * (fy - 0.45)


def _signature(frame: np.ndarray) -> list[float]:
    small = np.asarray(Image.fromarray(frame).resize((8, 8), Image.BILINEAR), np.float32) / 255.0
    hist = np.histogramdd(frame.reshape(-1, 3), bins=(4, 4, 4), range=((0, 256),) * 3)[0].ravel()
    hist = hist / (hist.sum() + 1e-9)
    return [round(float(v), 4) for v in np.concatenate([hist, small.mean(axis=2).ravel()])]


def similarity(a: list[float], b: list[float]) -> float:
    """0 = nothing alike, 1 = same look and layout."""
    if not a or not b:
        return 0.0
    va, vb = np.asarray(a), np.asarray(b)
    hist = float(np.minimum(va[:64], vb[:64]).sum())
    lay = 1.0 - float(np.abs(va[64:] - vb[64:]).mean()) * 2.5
    return 0.6 * hist + 0.4 * max(0.0, lay)


def _is_night_orange(frame: np.ndarray) -> bool:
    hsv = np.asarray(Image.fromarray(frame).convert("HSV"), np.float32)
    h, s, v = hsv[..., 0] * 360 / 255, hsv[..., 1] / 255, hsv[..., 2] / 255
    night = v.mean() < 0.3
    bright = v > 0.45
    if not night or bright.sum() < 20:
        return False
    orange = (h >= 12) & (h <= 48) & (s > 0.35) & bright
    return float(orange.sum() / bright.sum()) > 0.3


def _thumb(frame: np.ndarray) -> str:
    buf = io.BytesIO()
    Image.fromarray(frame).save(buf, "JPEG", quality=72)
    return base64.b64encode(buf.getvalue()).decode("ascii")


# ---------------------------------------------------------------------------- one clip

def analyse_clip(info: ClipInfo, *, lut: str = "", use_masks: bool = True) -> ClipAnalysis:
    frames = sample_frames(info, lut)
    if len(frames) == 0:
        raise ClipError("couldn't decode any frames (damaged?)")
    y = _luma(frames)
    exposure = y.reshape(len(y), -1).mean(1)
    hi = (y > 0.96).reshape(len(y), -1).mean(1)
    lo = (y < 0.04).reshape(len(y), -1).mean(1)
    sharp = _sharpness(y)
    color = _colorfulness(frames)
    motion = np.concatenate([[0.0], np.abs(np.diff(y, axis=0)).reshape(len(y) - 1, -1).mean(1)]) if len(y) > 1 else np.zeros(1)
    shake = _shake(y) if info.kind == "video" else 0.0

    # per-sample quality: sharp, well exposed, some motion but not chaos
    exp_ok = np.clip(1.0 - np.abs(exposure - 0.45) / 0.45, 0, 1)
    clip_pen = np.clip(1.0 - 2.0 * hi - 1.5 * lo, 0, 1)
    sharp_n = np.clip(np.log1p(sharp) / np.log1p(40.0), 0, 1)
    motion_ok = np.clip(0.5 + 8.0 * motion, 0.5, 1.0) * np.clip(1.4 - 6.0 * motion, 0.3, 1.0)
    quality = sharp_n * (0.4 + 0.6 * exp_ok) * clip_pen * motion_ok

    a = ClipAnalysis(info=info)
    a.sharpness = float(np.median(sharp))
    a.exposure = float(np.median(exposure))
    a.clipped_hi = float(np.median(hi))
    a.clipped_lo = float(np.median(lo))
    a.motion = float(np.median(motion))
    a.shake = shake
    a.colorfulness = float(np.median(color))
    a.quality = [round(float(q), 4) for q in quality]

    # best moment and a few alternatives at least 2.5 s apart (for re-using long clips)
    win = max(1, int(round(1.5 * SAMPLE_FPS)))
    means = np.convolve(quality, np.ones(win) / win, mode="valid") if len(quality) >= win else quality
    order = np.argsort(means)[::-1]
    picks: list[float] = []
    for idx in order:
        t = float(idx) / SAMPLE_FPS
        if all(abs(t - p) >= 2.5 for p in picks):
            picks.append(t)
        if len(picks) >= 6:
            break
    a.best_start = picks[0] if picks else 0.0
    a.moments = picks[1:]
    best_idx = min(len(frames) - 1, int(round(a.best_start * SAMPLE_FPS + win / 2)))
    best = frames[best_idx]

    a.focus = _focus(best)
    a.night_orange = _is_night_orange(best)
    a.signature = _signature(best)
    a.thumb = _thumb(best)

    masker = masks.get_masker() if use_masks else None
    if masker is not None:
        mask = masker.predict(best)
        area, cx, cy, _ = masks.person_stats(mask)
        a.person = area
        if area > 0.02:
            a.focus = (0.5 + 0.8 * (cx - 0.5), cy)
    return a


# ---------------------------------------------------------------------------- the whole folder

def judge(analyses: list[ClipAnalysis]) -> None:
    """Throw out junk and give every keeper a 0..1 score. Thresholds are relative to the batch, with hard floors."""
    vids = [a for a in analyses if a.usable]
    if not vids:
        return
    med_sharp = float(np.median([a.sharpness for a in vids])) or 1.0
    for a in vids:
        if a.exposure < 0.07 or a.clipped_lo > 0.85:
            a.usable, a.reason = False, "too dark"
        elif a.clipped_hi > 0.4 or a.exposure > 0.93:
            a.usable, a.reason = False, "blown out"
        elif a.sharpness < 0.25 * med_sharp or a.sharpness < 0.12:
            a.usable, a.reason = False, "blurry"
        elif a.shake > 0.035:
            a.usable, a.reason = False, "too shaky"
        elif a.info.kind == "video" and a.info.duration < 0.6:
            a.usable, a.reason = False, "too short"
    keep = [a for a in analyses if a.usable]
    # If that leaves almost nothing, take back the least bad (never the broken or black ones).
    if len(keep) < 8:
        maybes = sorted(
            (a for a in analyses if not a.usable and a.reason in ("blurry", "too shaky", "blown out")),
            key=lambda a: a.sharpness,
            reverse=True,
        )
        for a in maybes[: 8 - len(keep)]:
            a.usable, a.reason = True, f"kept (a bit {a.reason.replace('too ', '')})"
        keep = [a for a in analyses if a.usable]

    def ranks(values: list[float]) -> np.ndarray:
        arr = np.asarray(values, np.float64)
        if len(arr) == 1:
            return np.ones(1)
        return arr.argsort().argsort() / (len(arr) - 1)

    if not keep:
        return
    r_sharp = ranks([a.sharpness for a in keep])
    r_color = ranks([a.colorfulness for a in keep])
    for i, a in enumerate(keep):
        exp_ok = max(0.0, 1.0 - abs(a.exposure - 0.45) / 0.45)
        motion_ok = min(1.0, 0.4 + 10 * a.motion) * (1.0 if a.motion < 0.12 else 0.7)
        person = min(1.0, a.person / 0.12) if a.person < 0.5 else 0.7  # close and medium shots win; filling the frame is less nice
        steady = max(0.0, 1.0 - a.shake / 0.035)
        photo = 0.85 if a.info.kind == "photo" else 1.0
        a.score = round(photo * (0.3 * r_sharp[i] + 0.18 * exp_ok + 0.12 * r_color[i] + 0.12 * motion_ok + 0.18 * person + 0.1 * steady), 4)


def analyse_folder(folder: str | Path, *, lut: str = "", lut_apply: str = "off", use_masks: bool = True,
                   progress: Callable[[float, str], None] | None = None, workers: int | None = None) -> list[ClipAnalysis]:
    from .looks import lut_filter

    files = list_media(folder)
    results: list[ClipAnalysis | None] = [None] * len(files)
    done = [0]

    def one(i: int, path: Path) -> None:
        try:
            info = probe(path)
            a = analyse_clip(info, lut=lut_filter(info, lut, lut_apply), use_masks=use_masks)
        except ClipError as exc:
            a = ClipAnalysis(info=ClipInfo(path=str(path), name=path.name, kind="video", width=0, height=0, fps=0, duration=0),
                             usable=False, reason=str(exc))
        except Exception as exc:  # never crash on one bad file
            a = ClipAnalysis(info=ClipInfo(path=str(path), name=path.name, kind="video", width=0, height=0, fps=0, duration=0),
                             usable=False, reason=f"couldn't read ({exc.__class__.__name__})")
        results[i] = a
        done[0] += 1
        if progress:
            progress(done[0] / max(1, len(files)), path.name)

    with ThreadPoolExecutor(max_workers=workers or min(6, os.cpu_count() or 2)) as pool:
        list(pool.map(lambda args: one(*args), enumerate(files)))
    out = [r for r in results if r is not None]
    judge(out)
    return out
