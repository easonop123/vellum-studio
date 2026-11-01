"""Sound effects, made from scratch with maths (no samples, so no licences).

Every sound can be replaced: point Settings > Sound effects folder at a folder
with files named like the keys below (click.wav, shutter1.wav, riser.wav ...,
any format ffmpeg reads). Anything missing falls back to the built-in sound.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import numpy as np

SR = 48000

NAMES = ["click", "click_loud", "shutter1", "shutter2", "shutter3", "shutter4", "riser", "whoosh", "impact", "flash", "ring", "glitch"]
SHUTTERS = ["shutter1", "shutter2", "shutter3", "shutter4"]


# ---------------------------------------------------------------------------- building blocks

def _t(seconds: float) -> np.ndarray:
    return np.arange(int(seconds * SR)) / SR


def _noise(n: int, seed: int) -> np.ndarray:
    return np.random.default_rng(seed).normal(0, 1, n)


def _band(x: np.ndarray, lo: float, hi: float, soft: float = 0.15) -> np.ndarray:
    """FFT band-pass with soft edges (fine for short one-shot sounds)."""
    n = len(x)
    size = 1 << int(np.ceil(np.log2(max(2, n))))
    spec = np.fft.rfft(x, size)
    f = np.fft.rfftfreq(size, 1 / SR)
    lo_w = np.clip((np.log2(np.maximum(f, 1) / max(lo, 1)) / soft) + 0.5, 0, 1) if lo > 0 else 1.0
    hi_w = np.clip(0.5 - (np.log2(np.maximum(f, 1) / hi) / soft), 0, 1) if hi < SR / 2 else 1.0
    return np.fft.irfft(spec * lo_w * hi_w, size)[:n]


def _sweep_band(x: np.ndarray, f_start: float, f_end: float, q: float = 1.2, chunk: int = 2048) -> np.ndarray:
    """Band-pass whose centre glides from f_start to f_end (overlap-add)."""
    out = np.zeros(len(x))
    win = np.hanning(chunk)
    hop = chunk // 2
    n_chunks = max(1, (len(x) - chunk) // hop + 1)
    for c in range(n_chunks):
        a = c * hop
        seg = x[a : a + chunk]
        if len(seg) < chunk:
            break
        p = c / max(1, n_chunks - 1)
        fc = f_start * (f_end / f_start) ** p
        out[a : a + chunk] += _band(seg * win, fc / (1 + 1 / q), fc * (1 + 1 / q), soft=0.25)
    return out


def _decay(n: int, tau: float) -> np.ndarray:
    return np.exp(-np.arange(n) / SR / tau)


def _tone(freq, seconds: float, phase: float = 0.0) -> np.ndarray:
    freq = np.broadcast_to(np.asarray(freq, np.float64), (int(seconds * SR),))
    return np.sin(2 * np.pi * np.cumsum(freq) / SR + phase)


def _reverb(x: np.ndarray, seconds: float = 0.6, mix: float = 0.18, seed: int = 9, bright: float = 6000) -> np.ndarray:
    """Small room: convolve with decaying filtered noise."""
    ir = _band(_noise(int(seconds * SR), seed), 200, bright) * _decay(int(seconds * SR), seconds / 5)
    ir /= np.abs(ir).sum() / 4 + 1e-9
    size = 1 << int(np.ceil(np.log2(len(x) + len(ir))))
    wet = np.fft.irfft(np.fft.rfft(x, size) * np.fft.rfft(ir, size), size)[: len(x) + len(ir)]
    dry = np.pad(x, (0, len(ir)))
    return dry * (1 - mix) + wet * mix


def _stereo(x: np.ndarray, width: float = 0.0, seed: int = 0) -> np.ndarray:
    """Mono to stereo; width > 0 decorrelates a little with a tiny delay."""
    if width <= 0:
        return np.stack([x, x], 1)
    d = int(0.0007 * SR * width)
    right = np.concatenate([np.zeros(d), x])[: len(x)]
    return np.stack([x, x * (1 - 0.3 * width) + right * 0.3 * width], 1)


def _normalise(x: np.ndarray, peak: float = 0.9) -> np.ndarray:
    x = x - x.mean(axis=0)
    m = np.abs(x).max()
    return (x / m * peak).astype(np.float32) if m > 0 else x.astype(np.float32)


def _fade(x: np.ndarray, seconds: float = 0.004) -> np.ndarray:
    k = min(len(x), int(seconds * SR))
    if k > 1:
        x[-k:] *= np.linspace(1, 0, k)[:, None] if x.ndim == 2 else np.linspace(1, 0, k)
    return x


# ---------------------------------------------------------------------------- the sounds

def click() -> np.ndarray:
    n = int(0.06 * SR)
    tr = _band(_noise(n, 1), 1500, 12000) * _decay(n, 0.0012)
    body = _tone(4200, 0.06) * _decay(n, 0.008) * 0.5 + _tone(2600, 0.06) * _decay(n, 0.012) * 0.3
    return _normalise(_fade(_stereo(tr + body)))


def click_loud() -> np.ndarray:
    n = int(0.12 * SR)
    tr = _band(_noise(n, 2), 900, 14000) * _decay(n, 0.002)
    body = _tone(2200, 0.12) * _decay(n, 0.018) * 0.6 + _tone(3400, 0.12) * _decay(n, 0.01) * 0.35
    thump = _tone(np.linspace(180, 90, n), 0.12) * _decay(n, 0.02) * 0.7
    return _normalise(_fade(_stereo(_reverb(tr + body + thump, 0.25, 0.12)[:n])))


def _mech_click(n: int, seed: int, bright: float, body_hz: tuple[float, ...], tau: float, thump: float) -> np.ndarray:
    tr = _band(_noise(n, seed), 600, bright) * _decay(n, 0.0025)
    body = sum(_tone(f, n / SR, seed + i) * _decay(n, tau * (1 - 0.15 * i)) * (0.5 / (1 + i)) for i, f in enumerate(body_hz))
    low = _tone(np.linspace(150, 70, n), n / SR) * _decay(n, 0.025) * thump
    return tr + body + low


def shutter(variant: int) -> np.ndarray:
    """Four different camera shutters: SLR, fast DSLR, big mechanical, phone."""
    if variant == 1:  # mechanical SLR: mirror up ... shutter, mirror down
        n = int(0.25 * SR)
        a = _mech_click(n, 11, 9000, (1850, 3100), 0.03, 0.8)
        b = _mech_click(n, 12, 8000, (1500, 2600), 0.04, 1.0) * 0.85
        gap = int(0.072 * SR)
        x = a + np.concatenate([np.zeros(gap), b])[:n]
        return _normalise(_fade(_stereo(_reverb(x, 0.3, 0.1)[:n], 0.4)))
    if variant == 2:  # crisp DSLR with a quick motor ratchet
        n = int(0.22 * SR)
        a = _mech_click(n, 21, 12000, (2400, 4100), 0.018, 0.5)
        b = _mech_click(n, 22, 11000, (2100, 3600), 0.022, 0.6) * 0.9
        x = a + np.concatenate([np.zeros(int(0.045 * SR)), b])[:n]
        for j in range(5):
            x += np.concatenate([np.zeros(int((0.09 + j * 0.006) * SR)), _band(_noise(n, 30 + j), 2500, 9000) * _decay(n, 0.0015) * 0.25])[:n]
        return _normalise(_fade(_stereo(x, 0.3)))
    if variant == 3:  # big, loud mechanical shutter with room
        n = int(0.4 * SR)
        a = _mech_click(n, 31, 7000, (1300, 2200, 3300), 0.045, 1.4)
        b = _mech_click(n, 32, 6500, (1100, 1900), 0.05, 1.6)
        x = a + np.concatenate([np.zeros(int(0.085 * SR)), b])[:n]
        x = np.tanh(x * 1.6)
        return _normalise(_fade(_stereo(_reverb(x, 0.5, 0.2)[:n], 0.6)))
    # phone shutter: two bright snaps
    n = int(0.2 * SR)
    a = _band(_noise(n, 41), 2500, 14000) * _decay(n, 0.006) + _tone(1250, n / SR) * _decay(n, 0.012) * 0.35
    b = _band(_noise(n, 42), 3000, 15000) * _decay(n, 0.009) * 0.8 + _tone(980, n / SR) * _decay(n, 0.015) * 0.3
    x = a + np.concatenate([np.zeros(int(0.06 * SR)), b])[:n]
    return _normalise(_fade(_stereo(x, 0.2)))


def riser(seconds: float = 2.2) -> np.ndarray:
    n = int(seconds * SR)
    t = _t(seconds)
    p = t / seconds
    noise = _sweep_band(_noise(n, 51), 250, 9000, q=1.6)
    tone = _tone(220 * (5.5 ** p) * (1 + 0.012 * np.sin(2 * np.pi * 6 * t)), seconds) * 0.35
    tone2 = _tone(330 * (5.5 ** p), seconds) * 0.18
    env = (p ** 2.2) * (1 - np.exp(-(1 - p) * 120))  # swell, then a hard stop right at the drop
    x = (noise * 1.2 + tone + tone2) * env
    return _normalise(_stereo(x, 1.0))


def whoosh(seconds: float = 0.55) -> np.ndarray:
    n = int(seconds * SR)
    t = _t(seconds)
    p = t / seconds
    up = _sweep_band(_noise(n, 61), 500, 3200, q=1.1)
    down = _sweep_band(_noise(n, 62), 3200, 700, q=1.1)
    x = np.where(p < 0.55, up, down) * np.sin(np.pi * np.clip(p, 0, 1)) ** 1.6
    pan = np.clip(p * 2 - 1, -1, 1) * 0.6
    st = np.stack([x * (1 - pan), x * (1 + pan)], 1)
    return _normalise(st)


def impact(seconds: float = 2.0) -> np.ndarray:
    n = int(seconds * SR)
    t = _t(seconds)
    sub = _tone(38 + 80 * np.exp(-t * 9), seconds) * np.exp(-t / 0.55)
    punch = np.tanh(3 * _tone(70 + 140 * np.exp(-t * 40), seconds) * np.exp(-t / 0.08))
    crack = _band(_noise(n, 71), 200, 5000) * np.exp(-t / 0.03) * 0.6
    rumble = _band(_noise(n, 72), 30, 160) * np.exp(-t / 0.7) * 0.5
    x = sub * 1.0 + punch * 0.8 + crack + rumble
    x = _reverb(x, 1.2, 0.22, bright=3000)[:n]
    return _normalise(_stereo(x, 0.8))


def flash() -> np.ndarray:
    """Camera flash: a bright pop, a fizz, and a faint recharge whine."""
    seconds = 0.7
    n = int(seconds * SR)
    t = _t(seconds)
    pop = _band(_noise(n, 81), 1800, 16000) * np.exp(-t / 0.006)
    fizz = _band(_noise(n, 82), 3500, 12000) * np.exp(-t / 0.09) * 0.35
    whine = _tone(3200 + 2600 * t / seconds, seconds) * 0.05 * np.clip(t / 0.05, 0, 1) * np.exp(-t / 0.35)
    thud = _tone(110, seconds) * np.exp(-t / 0.03) * 0.4
    return _normalise(_fade(_stereo(pop + fizz + whine + thud, 0.5)))


def ring() -> np.ndarray:
    """A bright phone-camera chime: inharmonic bell partials."""
    seconds = 1.4
    t = _t(seconds)
    f0 = 1760.0
    partials = [(1.0, 1.0, 0.9), (2.76, 0.45, 0.5), (5.4, 0.22, 0.28), (8.93, 0.1, 0.16)]
    x = sum(a * _tone(f0 * r, seconds) * np.exp(-t / tau) for r, a, tau in partials)
    x *= np.clip(t / 0.003, 0, 1) * (1 + 0.04 * np.sin(2 * np.pi * 7 * t))
    return _normalise(_fade(_stereo(_reverb(x, 0.8, 0.25)[: len(t)], 0.7), 0.05))


def glitch() -> np.ndarray:
    seconds = 0.4
    n = int(seconds * SR)
    rng = np.random.default_rng(91)
    x = np.zeros(n)
    pos = 0
    while pos < n:
        size = int(rng.uniform(0.012, 0.045) * SR)
        kind = rng.integers(0, 3)
        tt = np.arange(size) / SR
        if kind == 0:
            seg = np.sign(np.sin(2 * np.pi * rng.uniform(200, 2400) * tt)) * 0.5
        elif kind == 1:
            seg = np.round(rng.normal(0, 1, size) * 4) / 4 * 0.6
        else:
            seg = np.zeros(size)
        x[pos : pos + size] = seg[: max(0, min(size, n - pos))]
        pos += size
    x = _band(x, 150, 9000)
    return _normalise(_fade(_stereo(x, 0.5)))


BUILTIN = {
    "click": click,
    "click_loud": click_loud,
    "shutter1": lambda: shutter(1),
    "shutter2": lambda: shutter(2),
    "shutter3": lambda: shutter(3),
    "shutter4": lambda: shutter(4),
    "riser": riser,
    "whoosh": whoosh,
    "impact": impact,
    "flash": flash,
    "ring": ring,
    "glitch": glitch,
}


@lru_cache(maxsize=4)
def builtin_bank() -> dict[str, np.ndarray]:
    return {name: make() for name, make in BUILTIN.items()}


def load_bank(custom_folder: str | None = None) -> dict[str, np.ndarray]:
    """Built-in sounds, with any matching files from the custom folder swapped in."""
    bank = dict(builtin_bank())
    if custom_folder and Path(custom_folder).is_dir():
        from .ffmpeg import read_audio

        files = {p.stem.lower(): p for p in Path(custom_folder).iterdir() if p.is_file() and not p.name.startswith(".")}
        for name in NAMES:
            p = files.get(name)
            if p is None:
                continue
            try:
                audio = read_audio(p, sr=SR, channels=2)
                if len(audio) > 0:
                    bank[name] = _normalise(audio)
            except Exception:
                pass
    return bank
