"""Render frames on every CPU core and encode straight to H.264 (no frame files on disk).

The edit is cut into 2-second chunks. Each worker process renders a chunk and
pipes it into two ffmpeg encoders (16:9 and vertical). The chunks are then
joined without re-encoding, and the audio is muxed in.
"""
from __future__ import annotations

import multiprocessing as mp
import os
import subprocess
import threading
from pathlib import Path
from typing import Callable

from .ffmpeg import run
from .paths import ffmpeg_path
from .plan import FPS, EditPlan

CHUNK = 48  # frames

_worker_state: dict = {}


def _encoder(path: str, w: int, h: int, crf: int, preset: str) -> subprocess.Popen:
    cmd = [
        ffmpeg_path(), "-hide_banner", "-nostdin", "-v", "error", "-y",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(FPS), "-i", "-",
        "-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p",
        # Capped CRF: full quality, but never heavier than social apps can use (grain is expensive to encode).
        "-maxrate", "16M", "-bufsize", "32M",
        "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
        "-threads", "2", "-an", path,
    ]
    return subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)


def _init_worker(plan_path: str, work: str, scale: float) -> None:
    from .plan import EditPlan
    from .render import Renderer

    plan = EditPlan.load(plan_path)
    _worker_state["r"] = Renderer(plan, Path(work), scale)


def _render_chunk(args: tuple[int, int, int, str, int, str]) -> int:
    idx, a, b, chunks_dir, crf, preset = args
    r = _worker_state["r"]
    h = _encoder(os.path.join(chunks_dir, f"h_{idx:04d}.mp4"), r.W, r.H, crf, preset)
    v = _encoder(os.path.join(chunks_dir, f"v_{idx:04d}.mp4"), r.VW, r.VH, crf, preset)
    try:
        for f in range(a, b):
            im = r.render(f)
            h.stdin.write(im.tobytes())
            v.stdin.write(r.vertical(im, f).tobytes())
    finally:
        for p in (h, v):
            p.stdin.close()
        errs = [p.wait() for p in (h, v)]
    if any(errs):
        raise RuntimeError(f"encoder failed on chunk {idx}: " + h.stderr.read().decode()[-300:] + v.stderr.read().decode()[-300:])
    return b - a


def render_video(plan: EditPlan, plan_path: Path, work: Path, scale: float, out_h: Path, out_v: Path, *,
                 workers: int | None = None, crf: int = 17, preset: str = "medium",
                 progress: Callable[[float], None] | None = None, cancel: threading.Event | None = None) -> None:
    total = plan.total_frames
    chunks_dir = work / "chunks"
    chunks_dir.mkdir(parents=True, exist_ok=True)
    tasks = [(i, a, min(total, a + CHUNK), str(chunks_dir), crf, preset) for i, a in enumerate(range(0, total, CHUNK))]
    n_workers = max(1, min(workers or (os.cpu_count() or 2), len(tasks)))
    ctx = mp.get_context("spawn")
    done = 0
    with ctx.Pool(n_workers, initializer=_init_worker, initargs=(str(plan_path), str(work), scale)) as pool:
        for frames in pool.imap_unordered(_render_chunk, tasks):
            done += frames
            if progress:
                progress(done / total)
            if cancel is not None and cancel.is_set():
                pool.terminate()
                raise InterruptedError("cancelled")
    for prefix, out in (("h", out_h), ("v", out_v)):
        listing = chunks_dir / f"{prefix}.txt"
        listing.write_text("".join(f"file '{chunks_dir / f'{prefix}_{i:04d}.mp4'}'\n" for i in range(len(tasks))))
        run(["-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy", str(out)])


def mux(video: Path, audio: Path, out: Path) -> None:
    run([
        "-i", str(video), "-i", str(audio), "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-shortest", "-movflags", "+faststart", str(out),
    ])
