"""Sound effects, made from scratch with maths (no samples, so no licences).

Every sound can be replaced: point Settings > Sound effects folder at a folder
with files named like the keys below (click.wav, shutter1.wav, riser.wav ...,
any format ffmpeg reads). Anything missing falls back to the built-in sound.
"""
from __future__ import annotations

import re
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

def _shape(x: np.ndarray, peaks: list[tuple[float, float, float]], lo: float = 0.0, hi: float = SR / 2,
           floor: float = 0.12) -> np.ndarray:
    """FFT filter whose response is a few broad bumps (centre Hz, width in octaves, gain) over a floor.
    Broad bumps ring for well under a millisecond, so the result is a snap, never a note."""
    n = len(x)
    size = 1 << int(np.ceil(np.log2(max(2, n))))
    f = np.fft.rfftfreq(size, 1 / SR)
    lf = np.log2(np.maximum(f, 1.0))
    resp = np.full(len(f), floor)
    for fc, width, gain in peaks:
        resp += gain * np.exp(-0.5 * ((lf - np.log2(fc)) / (width / 2.355)) ** 2)
    if lo > 0:
        resp *= np.clip((lf - np.log2(lo)) / 0.5 + 0.5, 0, 1)
    if hi < SR / 2:
        resp *= np.clip(0.5 - (lf - np.log2(hi)) / 0.5, 0, 1)
    return np.fft.irfft(np.fft.rfft(x, size) * resp, size)[:n]


def _snap(n: int, seed: int, tau: float, peaks: list[tuple[float, float, float]], lo: float = 400, hi: float = 15000,
          bounces: tuple[tuple[float, float], ...] = (), body: float = 0.0, body_tau: float = 0.006,
          body_hz: float = 260) -> np.ndarray:
    """One mechanical hit: a noise impulse through broad metal resonances, tiny re-hits as parts settle,
    and an optional low knock from the camera body. No sine tones, so nothing rings like a bar."""
    t = np.arange(n) / SR
    rng = np.random.default_rng(seed)
    x = rng.normal(0, 1, n) * (1 - np.exp(-t / 0.00015)) * np.exp(-t / tau)
    for delay, gain in bounces:
        d = int(delay * SR)
        if d < n:
            x[d:] += rng.normal(0, 1, n - d) * gain * np.exp(-t[: n - d] / (tau * 0.5))
    x = _shape(x, peaks, lo, hi) * (1 - np.exp(-t / 0.0002))  # a clean onset, no digital tick
    if body > 0:
        knock = rng.normal(0, 1, n) * (1 - np.exp(-t / 0.0004)) * np.exp(-t / body_tau)
        x += _shape(knock, [(body_hz, 1.4, 1.0)], 60, 1800, floor=0.0) * body
    return x


def _at(x: np.ndarray, seconds: float, n: int) -> np.ndarray:
    d = int(seconds * SR)
    return np.concatenate([np.zeros(d), x])[:n]


def _peak1(x: np.ndarray) -> np.ndarray:
    return x / (np.abs(x).max() + 1e-12)


def _dense(x: np.ndarray, target_db: float) -> np.ndarray:
    """Soft-saturate a short hit until its loudest 50 ms reaches target_db (at a 0.9 peak), like a
    recorded and limited sample. Without it, clean noise hits sound much quieter than they peak."""
    w = int(0.05 * SR)

    def loudest(y: np.ndarray) -> float:
        m = y.mean(axis=1) if y.ndim == 2 else y
        m = m / (np.abs(m).max() + 1e-12) * 0.9
        return 10 * np.log10(np.convolve(m ** 2, np.ones(w) / w, "same").max() + 1e-12)

    for drive in (1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0):
        y = np.tanh(x / (np.abs(x).max() + 1e-12) * drive)
        if loudest(y) >= target_db:
            return y
    return y


def click() -> np.ndarray:
    """A small, dry button click: press and a softer release a few ms later."""
    n = int(0.04 * SR)
    press = _snap(n, 1, 0.0011, [(3400, 1.2, 1.0), (7200, 1.0, 0.6)], lo=1200, bounces=((0.0009, 0.3),), body=0.25,
                  body_tau=0.002, body_hz=700)
    release = _snap(n, 2, 0.0008, [(4600, 1.0, 1.0)], lo=1800) * 0.35
    return _normalise(_fade(_stereo(_dense(_peak1(press) + _at(_peak1(release), 0.007, n) * 0.35, -21))))


def click_loud() -> np.ndarray:
    """A hard snap with a little weight: a big camera button or a typewriter key."""
    n = int(0.09 * SR)
    x = _snap(n, 3, 0.002, [(2200, 1.0, 1.0), (4800, 1.0, 0.8), (9000, 1.0, 0.35)], lo=600,
              bounces=((0.0013, 0.3), (0.0029, 0.15)), body=0.9, body_tau=0.006, body_hz=330)
    return _normalise(_fade(_stereo(_reverb(_dense(_peak1(x), -18), 0.12, 0.07, bright=7000)[:n], 0.2)))


def shutter(variant: int) -> np.ndarray:
    """Four camera shutters, each the classic two-part "ka-chik" (first curtain, then second
    curtain and mirror), in the same order as the reference scripts' shutter sounds."""
    if variant == 1:  # everyday camera shutter
        n = int(0.2 * SR)
        a = _snap(n, 11, 0.004, [(1800, 1.2, 0.8), (3600, 1.0, 1.0), (6500, 1.0, 0.6)], lo=500,
                  bounces=((0.0011, 0.45), (0.0024, 0.25), (0.0041, 0.12)), body=0.5)
        b = _snap(n, 12, 0.006, [(1400, 1.2, 1.0), (2800, 1.0, 0.8), (5200, 1.0, 0.4)], lo=400,
                  bounces=((0.0015, 0.4), (0.0032, 0.2)), body=0.7, body_hz=220)
        x = _dense(_peak1(a) + _at(_peak1(b), 0.058, n) * 0.85, -17)
        return _normalise(_fade(_stereo(_reverb(x, 0.15, 0.08, bright=7000)[:n], 0.4)))
    if variant == 2:  # crisp DSLR, then the motor winding on
        n = int(0.19 * SR)
        a = _snap(n, 21, 0.003, [(2500, 1.0, 1.0), (5000, 1.0, 0.9), (9000, 1.0, 0.5)], lo=700,
                  bounces=((0.0008, 0.35), (0.0019, 0.15)), body=0.35, body_hz=300)
        b = _snap(n, 22, 0.0045, [(2000, 1.0, 1.0), (4200, 1.0, 0.7)], lo=600,
                  bounces=((0.0012, 0.3),), body=0.5, body_hz=260)
        x = _peak1(a) + _at(_peak1(b), 0.034, n) * 0.9
        rng = np.random.default_rng(23)
        motor = np.zeros(n)
        t0, t1 = 0.062, 0.135
        k = t0
        while k < t1:  # the wind-on ratchet: a fast train of tiny ticks
            i = int(k * SR)
            m = min(n - i, int(0.003 * SR))
            p = (k - t0) / (t1 - t0)
            motor[i:i + m] += rng.normal(0, 1, m) * np.exp(-np.arange(m) / SR / 0.0004) * np.sin(np.pi * p) ** 0.7
            k += 1 / rng.uniform(380, 460)
        buzz = rng.normal(0, 1, n) * np.clip(np.sin(np.pi * np.clip((np.arange(n) / SR - t0) / (t1 - t0), 0, 1)), 0, 1)
        motor = _shape(motor, [(3000, 1.4, 1.0)], 1200, 9000) + _shape(buzz, [(1800, 1.0, 1.0)], 900, 4000) * 0.08
        x += _peak1(motor) * 0.22
        return _normalise(_fade(_stereo(_dense(x, -17), 0.3)))
    if variant == 3:  # heavy film SLR: big mirror slap, then the clack back
        n = int(0.3 * SR)
        a = _snap(n, 31, 0.007, [(900, 1.2, 1.0), (2000, 1.0, 0.9), (4000, 1.0, 0.5)], lo=200,
                  bounces=((0.002, 0.5), (0.0045, 0.3), (0.008, 0.15)), body=0.9, body_tau=0.012, body_hz=180)
        b = _snap(n, 32, 0.009, [(800, 1.2, 1.0), (1700, 1.0, 0.8), (3500, 1.0, 0.4)], lo=180,
                  bounces=((0.0025, 0.4), (0.006, 0.2)), body=1.0, body_tau=0.014, body_hz=160)
        x = _dense(_peak1(a) + _at(_peak1(b), 0.085, n) * 0.95, -14)
        return _normalise(_fade(_stereo(_reverb(x, 0.3, 0.12, bright=5000)[:n], 0.6)))
    # phone: two bright, airy snaps ("ch-chk")
    n = int(0.16 * SR)
    a = _snap(n, 41, 0.0035, [(5500, 1.4, 1.0), (9500, 1.0, 0.6)], lo=2000, hi=16000)
    a += _shape(np.random.default_rng(43).normal(0, 1, n) * np.exp(-np.arange(n) / SR / 0.012), [(6000, 2.0, 1.0)], 3000, 12000) * 0.25
    b = _snap(n, 42, 0.005, [(4200, 1.3, 1.0), (8000, 1.0, 0.5)], lo=1500, hi=16000)
    b += _shape(np.random.default_rng(44).normal(0, 1, n) * np.exp(-np.arange(n) / SR / 0.018), [(5000, 2.0, 1.0)], 2500, 11000) * 0.3
    x = _dense(_peak1(a) + _at(_peak1(b), 0.068, n) * 0.85, -18)
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


# The reference scripts' own sample names (sfx17_dslr.wav ...), so that folder works as it is.
# The four shutters keep the scripts' rotation order: shutterT, dslr, shutter_loud, phone.
ALIASES = {
    "shuttert": "shutter1", "shutter": "shutter1", "dslr": "shutter2", "shutter_loud": "shutter3", "phone": "shutter4",
}


def _sound_name(stem: str) -> str | None:
    """'Shutter1' -> shutter1, 'sfx17_dslr' -> shutter2, 'sfx15_click_loud' -> click_loud."""
    key = stem.lower().strip()
    if key in NAMES:
        return key
    key = re.sub(r"^sfx\d*[_ -]+", "", key).replace(" ", "_").replace("-", "_")
    if key in NAMES:
        return key
    return ALIASES.get(key)


def load_bank(custom_folder: str | None = None) -> dict[str, np.ndarray]:
    """Built-in sounds, with any matching files from the custom folder swapped in.
    A file named exactly like a sound (shutter1.wav) wins over one matched by its old name."""
    bank = dict(builtin_bank())
    if custom_folder and Path(custom_folder).is_dir():
        from .ffmpeg import read_audio

        files: dict[str, Path] = {}
        exact: set[str] = set()
        for f in sorted(Path(custom_folder).iterdir()):
            if not f.is_file() or f.name.startswith("."):
                continue
            name = _sound_name(f.stem)
            if name is None or name in exact:
                continue
            files[name] = f
            if f.stem.lower() == name:
                exact.add(name)
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
