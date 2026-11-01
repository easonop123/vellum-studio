"""Synthetic test media: a drum track with a known BPM and drop, and fake clips.

Nothing copyrighted: the song is synthesised here, the clips are ffmpeg test
patterns. Used by the automated tests and by the app's self-check.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .ffmpeg import run, write_wav
from .paths import ffmpeg_path

SR = 48000


@dataclass
class SongTruth:
    path: Path
    bpm: float
    first_beat: float
    drop: float


def _kick(sr: int, gain: float = 1.0) -> np.ndarray:
    t = np.arange(int(0.35 * sr)) / sr
    freq = 45 + 110 * np.exp(-t * 28)
    phase = 2 * np.pi * np.cumsum(freq) / sr
    body = np.sin(phase) * np.exp(-t * 9)
    click = np.random.default_rng(1).normal(0, 1, len(t)) * np.exp(-t * 400) * 0.3
    return (body + click) * gain


def _snare(sr: int, gain: float = 0.6) -> np.ndarray:
    t = np.arange(int(0.25 * sr)) / sr
    noise = np.random.default_rng(2).normal(0, 1, len(t))
    noise = noise - np.convolve(noise, np.ones(8) / 8, mode="same")  # crude high-pass
    tone = np.sin(2 * np.pi * 185 * t)
    return (noise * 0.8 + tone * 0.4) * np.exp(-t * 22) * gain


def _hat(sr: int, gain: float = 0.12) -> np.ndarray:
    t = np.arange(int(0.05 * sr)) / sr
    noise = np.random.default_rng(3).normal(0, 1, len(t))
    noise = noise - np.convolve(noise, np.ones(4) / 4, mode="same")
    return noise * np.exp(-t * 90) * gain


def make_song(path: Path, bpm: float = 120.0, lead_in: float = 0.25, intro_beats: int = 16, total: float = 75.0) -> SongTruth:
    """Quiet hats and a soft pad for `intro_beats`, then a loud drop: kick on every beat, snare on 2 and 4, bass."""
    beat = 60.0 / bpm
    n = int(total * SR)
    out = np.zeros(n, np.float64)
    kick, snare, hat = _kick(SR), _snare(SR), _hat(SR)
    drop = lead_in + intro_beats * beat

    def add(sample: np.ndarray, t: float, gain: float = 1.0):
        i = int(round(t * SR))
        if i >= n:
            return
        j = min(n, i + len(sample))
        out[i:j] += sample[: j - i] * gain

    k = 0
    while True:
        t = lead_in + k * beat
        if t >= total:
            break
        if t < drop - 1e-6:
            add(hat, t, 0.8)
            add(hat, t + beat / 2, 0.5)
        else:
            add(kick, t, 1.0)
            if k % 2 == 1:
                add(snare, t)
            add(hat, t + beat / 2, 1.0)
        k += 1
    # soft pad in the intro, bass after the drop
    tt = np.arange(n) / SR
    pad = 0.04 * np.sin(2 * np.pi * 220 * tt) * (tt < drop)
    bass = 0.22 * np.sin(2 * np.pi * 55 * tt) * (tt >= drop) * (0.6 + 0.4 * np.cos(2 * np.pi * tt / beat))
    out += pad + bass
    out /= np.abs(out).max() / 0.9
    stereo = np.stack([out, out], axis=1)
    write_wav(path, stereo, SR)
    return SongTruth(path=path, bpm=bpm, first_beat=lead_in, drop=drop)


# ---------------------------------------------------------------------------- clips

# Detailed, coherently moving patterns (flat colour bars would rightly count as "blurry").
PATTERNS = [
    "testsrc2=size={w}x{h}:rate={fps}",
    "mandelbrot=size={w}x{h}:rate={fps}:start_scale=2.5:end_scale=0.6",
    "testsrc=size={w}x{h}:rate={fps}:decimals=2",
    "life=size={w}x{h}:rate={fps}:mold=10:ratio=0.3:death_color=#202848:life_color=#f0c060",
]


def make_clip(path: Path, *, seconds: float = 3.0, fps: float = 30, w: int = 320, h: int = 180, pattern: int = 0,
              hue: float = 0.0, extra_vf: str = "", codec_args: list[str] | None = None) -> Path:
    """A moving test pattern. Every clip gets its own hue so cuts are easy to see."""
    src = PATTERNS[pattern % len(PATTERNS)].format(w=w, h=h, fps=fps)
    # Scroll the picture so there's real motion, and tint it so each clip looks different.
    vf = f"scroll=horizontal=0.004:vertical=0.002,hue=h={hue}:s=1.4"
    if extra_vf:
        vf += "," + extra_vf
    args = ["-f", "lavfi", "-i", src, "-t", f"{seconds}", "-vf", vf]
    args += codec_args or ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "23", "-pix_fmt", "yuv420p"]
    args += [str(path)]
    run(args)
    return path


def make_test_set(folder: Path, *, count: int = 26) -> dict:
    """The messy set the brief asks the tests to cover. Returns a description of what's where."""
    folder.mkdir(parents=True, exist_ok=True)
    made: dict[str, list[str]] = {"good": [], "vertical": [], "rotated": [], "hdr": [], "high_fps": [], "black": [], "corrupt": [], "blurry": [], "photo": []}
    fps_cycle = [24, 25, 30, 60, 30, 120, 30, 25]
    for i in range(count):
        fps = fps_cycle[i % len(fps_cycle)]
        vertical = i % 5 == 2
        w, h = (180, 320) if vertical else (320, 180)
        name = f"IMG_{4800 + i:04d}.MOV" if i % 3 else f"DJI_{100 + i:04d}.MP4"
        make_clip(folder / name, seconds=2.6 + (i % 4) * 0.7, fps=fps, w=w, h=h, pattern=i, hue=(i * 47) % 360)
        made["good"].append(name)
        if vertical:
            made["vertical"].append(name)
        if fps >= 50:
            made["high_fps"].append(name)
    # rotated: stored sideways with a 90 degree display matrix, like a phone clip
    base = folder / "_rot_src.mp4"
    make_clip(base, seconds=3.0, fps=30, w=320, h=180, pattern=2, hue=200)
    subprocess.run([ffmpeg_path(), "-v", "error", "-y", "-display_rotation", "90", "-i", str(base), "-c", "copy",
                    str(folder / "IMG_9001.MOV")], check=True, stdin=subprocess.DEVNULL)
    base.unlink()
    made["rotated"].append("IMG_9001.MOV")
    # HDR-tagged (HLG, BT.2020, 10-bit), like an iPhone HDR clip
    make_clip(folder / "IMG_9002.MOV", seconds=3.0, fps=30, pattern=0, hue=90,
              codec_args=["-c:v", "libx265", "-preset", "ultrafast", "-x265-params", "log-level=error",
                          "-pix_fmt", "yuv420p10le", "-color_primaries", "bt2020", "-color_trc", "arib-std-b67",
                          "-colorspace", "bt2020nc", "-tag:v", "hvc1"])
    made["hdr"].append("IMG_9002.MOV")
    # a black clip (lens cap) and a blurry one
    run(["-f", "lavfi", "-i", "color=c=black:size=320x180:rate=30", "-t", "3", "-c:v", "libx264", "-preset", "ultrafast",
         "-pix_fmt", "yuv420p", str(folder / "IMG_9003.MOV")])
    made["black"].append("IMG_9003.MOV")
    make_clip(folder / "IMG_9004.MOV", seconds=3.0, fps=30, pattern=0, hue=30, extra_vf="gblur=sigma=14")
    made["blurry"].append("IMG_9004.MOV")
    # corrupt: random bytes with a video name, and a truncated real file
    (folder / "IMG_9005.MOV").write_bytes(np.random.default_rng(5).integers(0, 255, 50_000, dtype=np.uint8).tobytes())
    good = (folder / made["good"][0]).read_bytes()
    (folder / "IMG_9006.MP4").write_bytes(good[: len(good) // 7])
    made["corrupt"] += ["IMG_9005.MOV", "IMG_9006.MP4"]
    # a photo
    run(["-f", "lavfi", "-i", "testsrc2=size=480x360:rate=1", "-frames:v", "1", "-vf", "hue=h=300:s=1.3",
         str(folder / "IMG_9007.JPG")])
    made["photo"].append("IMG_9007.JPG")
    return made
