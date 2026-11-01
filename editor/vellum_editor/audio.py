"""Song analysis: tempo, an exact beat grid, and the drop (first big energy jump).

Everything the edit needs is two numbers: BEAT (seconds per beat) and the time
of the drop in the song. Cuts land on frame(k) = round((DROP + k*BEAT) * 24).

Pop and electronic songs are made on a fixed grid, so instead of tracking
beats one by one we fold the onset strength over candidate periods and pick
the period and phase that line up best. That's accurate to a few milliseconds
over a minute, which is what keeps cuts within one frame of the beat.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np

from .ffmpeg import read_audio

SR = 22050
N_FFT = 1024
HOP = 256
FRAME_RATE = SR / HOP
# A sharp onset shows up strongest when it sits a quarter of the way into the
# analysis window, so this is the time each spectral frame "means".
FRAME_OFFSET = N_FFT / 4 / SR + 0.0224  # measured: percussive onsets peak ~34 ms after the window start
MAX_ANALYSIS_SECONDS = 240.0


@dataclass
class SongAnalysis:
    path: str
    duration: float
    bpm: float
    beat: float  # seconds per beat
    phase: float  # time of one grid beat; the grid is phase + n*beat
    drop: float  # song time of the drop, on the grid
    confidence: float  # 0..1, how clearly the grid fits
    drop_strength: float  # dB jump at the drop
    envelope: list[float] = field(default_factory=list)  # loudness overview for the app (0..1)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "SongAnalysis":
        return cls(**data)

    def with_bpm(self, bpm: float) -> "SongAnalysis":
        """Change tempo but keep the drop where it is (the grid hangs off the drop)."""
        beat = 60.0 / bpm
        return SongAnalysis(**{**asdict(self), "bpm": bpm, "beat": beat, "phase": self.drop % beat})

    def with_drop(self, drop: float) -> "SongAnalysis":
        return SongAnalysis(**{**asdict(self), "drop": max(0.0, drop), "phase": max(0.0, drop) % self.beat})


# ---------------------------------------------------------------------------- spectral features

def _frames(x: np.ndarray, n_fft: int, hop: int) -> np.ndarray:
    n = 1 + max(0, (len(x) - n_fft) // hop)
    shape = (n, n_fft)
    strides = (x.strides[0] * hop, x.strides[0])
    return np.lib.stride_tricks.as_strided(x, shape=shape, strides=strides)


def _band_matrix(n_bins: int, n_bands: int = 48, fmin: float = 30.0, fmax: float = 11000.0) -> np.ndarray:
    freqs = np.linspace(0, SR / 2, n_bins)
    edges = np.geomspace(fmin, fmax, n_bands + 1)
    mat = np.zeros((n_bins, n_bands), np.float32)
    for b in range(n_bands):
        lo, hi = edges[b], edges[b + 1]
        idx = np.where((freqs >= lo) & (freqs < hi))[0]
        if len(idx) == 0:
            idx = np.array([np.argmin(np.abs(freqs - (lo + hi) / 2))])
        mat[idx, b] = 1.0 / len(idx)
    return mat


def onset_features(x: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (onset strength, low-band onset strength, frame times)."""
    window = np.hanning(N_FFT).astype(np.float32)
    frames = _frames(x.astype(np.float32), N_FFT, HOP)
    bands = _band_matrix(N_FFT // 2 + 1)
    low_bands = slice(0, 12)  # ~30-150 Hz: kick and bass
    out = []
    # chunked so a long song doesn't need a huge spectrogram in memory
    for start in range(0, len(frames), 4096):
        spec = np.abs(np.fft.rfft(frames[start : start + 4096] * window, axis=1)).astype(np.float32)
        out.append(np.log1p(100.0 * (spec @ bands)))
    banded = np.concatenate(out) if out else np.zeros((1, bands.shape[1]), np.float32)
    diff = np.maximum(0.0, np.diff(banded, axis=0, prepend=banded[:1]))
    flux = diff.sum(axis=1)
    low = diff[:, low_bands].sum(axis=1)
    times = np.arange(len(flux)) * HOP / SR + FRAME_OFFSET
    return _normalise(flux), _normalise(low), times


def _normalise(env: np.ndarray) -> np.ndarray:
    if len(env) < 4:
        return env
    k = max(1, int(FRAME_RATE * 0.4))
    local = np.convolve(env, np.ones(k) / k, mode="same")
    env = np.maximum(0.0, env - local)
    sd = env.std() or 1.0
    return (env / sd).astype(np.float32)


# ---------------------------------------------------------------------------- tempo

def _autocorr_tempo(onset: np.ndarray) -> list[float]:
    """Rough candidates from autocorrelation, best first (BPM)."""
    o = onset - onset.mean()
    n = len(o)
    size = 1 << int(np.ceil(np.log2(2 * n)))
    spec = np.fft.rfft(o, size)
    ac = np.fft.irfft(spec * np.conj(spec))[:n]
    lags = np.arange(n)
    with np.errstate(divide="ignore"):
        bpm = 60.0 * FRAME_RATE / np.maximum(lags, 1)
    valid = (bpm >= 55) & (bpm <= 215)
    prior = np.exp(-0.5 * (np.log2(np.maximum(bpm, 1) / 118.0) / 0.9) ** 2)
    score = np.where(valid, ac * prior, -np.inf)
    order = np.argsort(score)[::-1]
    out: list[float] = []
    for lag in order[:200]:
        if not np.isfinite(score[lag]):
            break
        # parabolic refinement of the lag
        if 1 <= lag < n - 1:
            a, b, c = ac[lag - 1], ac[lag], ac[lag + 1]
            denom = a - 2 * b + c
            shift = 0.5 * (a - c) / denom if denom != 0 else 0.0
        else:
            shift = 0.0
        cand = 60.0 * FRAME_RATE / (lag + shift)
        if all(abs(cand / c - 1) > 0.04 for c in out):
            out.append(float(cand))
        if len(out) >= 4:
            break
    return out or [120.0]


def _fold_strength(times: np.ndarray, weights: np.ndarray, period: float, bins: int = 96) -> tuple[float, float]:
    """How sharply onsets pile up at one phase of this period. Returns (strength, phase in seconds)."""
    idx = np.floor(np.mod(times, period) / period * bins).astype(np.int64) % bins
    hist = np.bincount(idx, weights=weights, minlength=bins)
    # light circular smoothing
    hist = (np.roll(hist, 1) + 2 * hist + np.roll(hist, -1)) / 4.0
    peak = int(np.argmax(hist))
    a, b, c = hist[(peak - 1) % bins], hist[peak], hist[(peak + 1) % bins]
    denom = a - 2 * b + c
    shift = 0.5 * (a - c) / denom if denom != 0 else 0.0
    phase = ((peak + 0.5 + shift) / bins) * period
    strength = float(b / (hist.mean() + 1e-9))
    return strength, float(phase % period)


def refine_grid(times: np.ndarray, onset: np.ndarray, bpm_guess: float, spread: float = 0.025) -> tuple[float, float, float]:
    """Fine search for the exact period and phase near a tempo guess. Returns (bpm, phase, strength)."""
    keep = onset > np.percentile(onset, 70)  # only the clear onsets
    t, w = times[keep], onset[keep]
    best = (0.0, bpm_guess, 0.0)
    p0 = 60.0 / bpm_guess
    # coarse then fine
    for span, steps in ((spread, 241), (spread / 20, 201)):
        centre = 60.0 / best[1] if best[0] > 0 else p0
        for period in centre * (1 + np.linspace(-span, span, steps)):
            strength, phase = _fold_strength(t, w, period)
            if strength > best[0]:
                best = (strength, 60.0 / period, phase)
    strength, bpm, phase = best
    return bpm, phase, strength


def estimate_grid(times: np.ndarray, onset: np.ndarray) -> tuple[float, float, float]:
    candidates = _autocorr_tempo(onset)
    scored = []
    for c in candidates[:3]:
        for mult in (1.0, 2.0, 0.5):
            bpm = c * mult
            if 55 <= bpm <= 215:
                b, phase, strength = refine_grid(times, onset, bpm)
                scored.append((strength, b, phase))
    if not scored:
        return 120.0, 0.0, 0.0
    scored.sort(reverse=True)
    best_strength = scored[0][0]
    # Among near-equal fits prefer an editable tempo (75-160 BPM).
    for strength, bpm, phase in scored:
        if strength >= best_strength * 0.9 and 75 <= bpm <= 160:
            return bpm, phase, strength
    return scored[0][1], scored[0][2], scored[0][0]


# ---------------------------------------------------------------------------- drop

def _beat_energy_db(x: np.ndarray, sr: int, grid: np.ndarray) -> np.ndarray:
    out = np.full(len(grid) - 1, -120.0)
    for i in range(len(grid) - 1):
        a, b = int(grid[i] * sr), int(grid[i + 1] * sr)
        if b <= a or a >= len(x):
            continue
        seg = x[a : min(b, len(x))]
        out[i] = 10 * np.log10(np.mean(seg.astype(np.float64) ** 2) + 1e-12)
    return out


def find_drop(x: np.ndarray, sr: int, beat: float, phase: float, low_onset: np.ndarray, times: np.ndarray,
              search_from: float = 0.0, window: int = 8) -> tuple[float, float]:
    """The first big energy jump, on the beat grid. Returns (song time, jump in dB)."""
    duration = len(x) / sr
    grid = np.arange(phase, duration, beat)
    if len(grid) < 2 * window + 2:
        return float(grid[min(len(grid) - 1, 8)] if len(grid) else 0.0), 0.0
    energy = _beat_energy_db(x, sr, grid)
    # low-end (kick/bass) presence per beat
    low = np.zeros(len(grid) - 1)
    for i in range(len(grid) - 1):
        m = (times >= grid[i]) & (times < grid[i + 1])
        low[i] = float(low_onset[m].sum()) if m.any() else 0.0
    loud = np.percentile(energy[energy > -100], 80) if np.any(energy > -100) else 0.0
    top = energy.max()
    best_n, best_score, first_n = None, -np.inf, None
    for n in range(4, len(energy) - 4):
        if grid[n] < search_from:
            continue
        prev = energy[max(0, n - window) : n]
        nxt = energy[n : n + window]
        if prev.mean() < top - 45:  # coming out of silence: that's the song starting, not a drop
            continue
        jump = float(nxt.mean() - prev.mean())
        low_prev = low[max(0, n - window) : n].mean()
        low_next = low[n : n + window].mean()
        low_jump = 10 * np.log10((low_next + 1e-3) / (low_prev + 1e-3))
        level_ok = nxt.mean() >= loud - 4.0
        score = jump + 0.35 * low_jump
        if level_ok and score > best_score:
            best_n, best_score = n, score
        if first_n is None and level_ok and jump >= 4.5:
            first_n = n
    if first_n is not None:
        # nudge to the strongest beat within one beat either side of the threshold crossing
        candidates = [m for m in (first_n - 1, first_n, first_n + 1) if 4 <= m < len(energy) - 4]
        def jump_at(m: int) -> float:
            return float(energy[m : m + window].mean() - energy[max(0, m - window) : m].mean())
        n = max(candidates, key=jump_at)
        return float(grid[n]), jump_at(n)
    if best_n is not None and best_score > 1.5:
        return float(grid[best_n]), float(best_score)
    n = min(len(grid) - 1, max(8, int(np.ceil((search_from - phase) / beat)) if search_from > 0 else 8))
    return float(grid[n]), 0.0


# ---------------------------------------------------------------------------- public

def analyze_song(path: str, search_from: float = 0.0) -> SongAnalysis:
    x = read_audio(path, sr=SR, channels=1)[:, 0]
    duration = len(x) / SR
    if duration < 5:
        raise ValueError("song is shorter than 5 seconds")
    xa = x[: int(MAX_ANALYSIS_SECONDS * SR)]
    onset, low, times = onset_features(xa)
    bpm, phase, strength = estimate_grid(times, onset)
    beat = 60.0 / bpm
    drop, jump = find_drop(xa, SR, beat, phase, low, times, search_from=search_from)
    # loudness overview for the app's waveform strip
    hop = max(1, len(x) // 600)
    env = np.sqrt(np.convolve(x.astype(np.float64) ** 2, np.ones(hop) / hop, mode="same")[::hop])
    env = (env / (env.max() + 1e-9)).round(3).tolist()
    confidence = float(np.clip((strength - 1.5) / 3.0, 0, 1))
    return SongAnalysis(
        path=str(path), duration=duration, bpm=round(bpm, 3), beat=beat, phase=phase,
        drop=drop, confidence=round(confidence, 3), drop_strength=round(jump, 2), envelope=env,
    )
