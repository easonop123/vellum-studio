"""Small helpers around the ffmpeg / ffprobe command line tools."""
from __future__ import annotations

import functools
import subprocess
from pathlib import Path

import numpy as np

from .paths import ffmpeg_path, ffprobe_path

# Keep ffmpeg from ever waiting for keyboard input or opening a console window.
_POPEN = dict(stdin=subprocess.DEVNULL)


class FFmpegError(RuntimeError):
    pass


def run(args: list[str], *, timeout: float | None = None) -> None:
    cmd = [ffmpeg_path(), "-hide_banner", "-nostdin", "-v", "error", "-y", *args]
    proc = subprocess.run(cmd, capture_output=True, timeout=timeout, **_POPEN)
    if proc.returncode != 0:
        raise FFmpegError(proc.stderr.decode("utf-8", "replace").strip()[-2000:] or "ffmpeg failed")


def probe_json(path: str | Path, *, timeout: float = 30) -> dict:
    import json

    cmd = [
        ffprobe_path(), "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", "-show_entries",
        "stream_side_data=rotation,side_data_type,dv_profile",
        str(path),
    ]
    proc = subprocess.run(cmd, capture_output=True, timeout=timeout, **_POPEN)
    if proc.returncode != 0:
        raise FFmpegError(proc.stderr.decode("utf-8", "replace").strip()[-500:] or "ffprobe failed")
    return json.loads(proc.stdout or b"{}")


@functools.lru_cache(maxsize=1)
def filters() -> frozenset[str]:
    """Names of the filters this ffmpeg build has (zscale for HDR tone mapping isn't in every build)."""
    import re

    proc = subprocess.run([ffmpeg_path(), "-hide_banner", "-filters"], capture_output=True, **_POPEN)
    names = set()
    for line in proc.stdout.decode("utf-8", "replace").splitlines():
        parts = line.split()
        # e.g. " TSC colorbalance      V->V       Adjust the color balance."
        if len(parts) >= 3 and re.fullmatch(r"[TSC.|]{2,4}", parts[0]):
            names.add(parts[1])
    return frozenset(names)


def has_filter(name: str) -> bool:
    return name in filters()


def read_frames(args: list[str], width: int, height: int, *, max_frames: int | None = None, timeout: float = 300) -> np.ndarray:
    """Run ffmpeg with rawvideo rgb24 output on stdout and return frames as (n, h, w, 3) uint8."""
    cmd = [ffmpeg_path(), "-hide_banner", "-nostdin", "-v", "error", *args, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    proc = subprocess.run(cmd, capture_output=True, timeout=timeout, **_POPEN)
    if proc.returncode != 0 and not proc.stdout:
        raise FFmpegError(proc.stderr.decode("utf-8", "replace").strip()[-800:] or "ffmpeg failed")
    frame_bytes = width * height * 3
    n = len(proc.stdout) // frame_bytes
    if max_frames is not None:
        n = min(n, max_frames)
    if n == 0:
        return np.zeros((0, height, width, 3), np.uint8)
    return np.frombuffer(proc.stdout[: n * frame_bytes], np.uint8).reshape(n, height, width, 3)


def read_audio(path: str | Path, *, sr: int = 48000, channels: int = 2, offset: float = 0.0, duration: float | None = None) -> np.ndarray:
    """Decode audio to float32 (n, channels)."""
    args = [ffmpeg_path(), "-hide_banner", "-nostdin", "-v", "error"]
    if offset > 0:
        args += ["-ss", f"{offset:.4f}"]
    args += ["-i", str(path)]
    if duration is not None:
        args += ["-t", f"{duration:.4f}"]
    args += ["-vn", "-f", "f32le", "-ac", str(channels), "-ar", str(sr), "-"]
    proc = subprocess.run(args, capture_output=True, **_POPEN)
    if proc.returncode != 0 and not proc.stdout:
        raise FFmpegError(proc.stderr.decode("utf-8", "replace").strip()[-800:] or "couldn't read audio")
    data = np.frombuffer(proc.stdout, np.float32)
    return data.reshape(-1, channels).copy()


def write_wav(path: str | Path, audio: np.ndarray, sr: int = 48000) -> None:
    """Write float audio (n, ch) in [-1, 1] as 24-bit PCM WAV via ffmpeg (no extra Python deps)."""
    audio = np.ascontiguousarray(np.clip(audio, -1, 1).astype(np.float32))
    channels = 1 if audio.ndim == 1 else audio.shape[1]
    cmd = [
        ffmpeg_path(), "-hide_banner", "-nostdin", "-v", "error", "-y",
        "-f", "f32le", "-ar", str(sr), "-ac", str(channels), "-i", "-",
        "-c:a", "pcm_s24le", str(path),
    ]
    proc = subprocess.run(cmd, input=audio.tobytes(), capture_output=True)
    if proc.returncode != 0:
        raise FFmpegError(proc.stderr.decode("utf-8", "replace")[-500:])
