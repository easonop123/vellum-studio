"""Pull exactly the frames each shot needs out of the source clips.

Never decodes a whole 4K clip to disk: each shot seeks to its start, takes only
its frames, crops to the target shape around the subject, scales down (never
above 1920 wide), converts HDR to SDR, applies the LUT and grade, and writes
small JPEGs. Many shots run at once to use every CPU core.
"""
from __future__ import annotations

import json
import math
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np
from PIL import Image

from . import masks as masks_mod
from .analyze import ClipAnalysis, load_photo
from .ffmpeg import run
from .looks import get_look, grade_filter, lut_filter, tonemap_filter
from .plan import FPS, EditPlan, Segment, Shot
from .probe import ClipInfo

EXTRA_FRAMES = 16  # frames past a segment's end, for transitions that peek ahead


@dataclass
class Job:
    shot: Shot
    frames: int  # output frames needed
    ramp_total: int | None = None  # native frames to pull for speed ramps


def even(v: float) -> int:
    return max(2, int(round(v / 2)) * 2)


def box_px(shot: Shot, scale: float) -> tuple[int, int]:
    return even(shot.box[0] * scale), even(shot.box[1] * scale)


def crop_rect(info: ClipInfo, shot: Shot) -> tuple[int, int, int, int]:
    """(w, h, x, y) of the crop in display pixels, centred on the shot's focus."""
    w, h = info.width, info.height
    target = shot.box[0] / shot.box[1]
    if w / h > target:
        cw, ch = int(h * target) // 2 * 2, h // 2 * 2
        x = int(min(max(0, shot.fx * w - cw / 2), w - cw)) // 2 * 2
        return cw, ch, x, 0
    cw, ch = w // 2 * 2, int(w / target) // 2 * 2
    y = int(min(max(0, shot.fy * h - ch / 2), h - ch)) // 2 * 2
    return cw, ch, 0, y


def speed_at(shot: Shot, j: int, n: int) -> float:
    if shot.ramp:
        p = j / max(1, n - 1)
        return shot.ramp[0] + (shot.ramp[1] - shot.ramp[0]) * p * p
    return shot.speed


def ramp_index_map(shot: Shot, n: int, src_fps: float) -> tuple[list[int], int]:
    """Output frame -> extracted native frame, for speed ramps."""
    idx, acc = [], 0.0
    for j in range(n + EXTRA_FRAMES):
        idx.append(int(acc))
        acc += speed_at(shot, min(j, n - 1), n) * src_fps / FPS
    return idx, int(math.ceil(acc)) + 3


def shot_frame_counts(plan: EditPlan) -> dict[str, int]:
    """How many output frames each shot needs (its time on screen, plus transition headroom)."""
    out: dict[str, int] = {}
    for seg in plan.segments:
        f0, f1 = plan.frames_of(seg)
        n = f1 - f0
        if seg.shot:
            out[seg.shot.id] = n + EXTRA_FRAMES
        for sub in seg.subs:
            appear = plan.F(seg.k0 + sub.at) - f0
            out[sub.id] = max(1, n - appear) + EXTRA_FRAMES
    return out


def extract_shot(job: Job, info: ClipInfo, analysis: ClipAnalysis, out_dir: Path, scale: float, look_key: str,
                 lut_path: str | None, lut_apply: str, texture: bool = True) -> dict:
    shot = job.shot
    d = out_dir / shot.id
    d.mkdir(parents=True, exist_ok=True)
    bw, bh = box_px(shot, min(scale, 1.0))
    look = get_look(look_key)
    grade = grade_filter(look, shot.raw, analysis.night_orange, texture)
    meta = {"w": bw, "h": bh, "map": None}

    if info.kind == "photo":
        im = load_photo(info.path)
        cw, ch, x, y = crop_rect(ClipInfo(**{**info.to_dict(), "width": im.width, "height": im.height}), shot)
        im = im.crop((x, y, x + cw, y + ch)).resize((bw, bh), Image.LANCZOS)
        src = d / "src.png"
        im.save(src)
        run(["-i", str(src), "-vf", grade, "-frames:v", "1", "-q:v", "2", str(d / "0001.jpg")])
        src.unlink(missing_ok=True)
        meta["map"] = [0] * job.frames
        (d / "meta.json").write_text(json.dumps(meta))
        return meta

    cw, ch, x, y = crop_rect(info, shot)
    chain: list[str] = []
    n = job.frames
    if shot.ramp:
        idx, native = ramp_index_map(shot, n - EXTRA_FRAMES, info.fps)
        meta["map"] = idx
        count = native
    else:
        chain.append(f"fps={FPS / max(0.05, shot.speed):.6f}")
        count = n
    chain += [f"crop={cw}:{ch}:{x}:{y}", f"scale={bw}:{bh}:flags=lanczos"]
    tm = tonemap_filter(info)
    if tm:
        chain.append(tm)
    lut = lut_filter(info, lut_path, lut_apply)
    if lut:
        chain.append(lut)
    chain.append(grade)
    run([
        "-ss", f"{max(0.0, shot.ss):.4f}", "-i", info.path, "-an", "-sn", "-dn",
        "-vf", ",".join(chain), "-frames:v", str(count), "-q:v", "3", "-threads", "2",
        str(d / "%04d.jpg"),
    ])
    files = sorted(d.glob("*.jpg"))
    if not files:
        # Very end of a clip: grab the last frames instead.
        run(["-sseof", "-1", "-i", info.path, "-an", "-vf", ",".join(chain[1:] if not shot.ramp else chain),
             "-frames:v", "1", "-q:v", "3", str(d / "%04d.jpg")])
        files = sorted(d.glob("*.jpg"))
    meta["count"] = len(files)
    if meta["map"] is None:
        meta["map"] = list(range(n))
    (d / "meta.json").write_text(json.dumps(meta))
    return meta


def extract_all(plan: EditPlan, work: Path, scale: float, *, lut_path: str | None = None, lut_apply: str = "off",
                texture: bool = True,
                progress: Callable[[float], None] | None = None, workers: int | None = None) -> None:
    frames_dir = work / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    counts = shot_frame_counts(plan)
    jobs: list[Job] = []
    for seg in plan.segments:
        for shot in seg.all_shots():
            jobs.append(Job(shot=shot, frames=counts.get(shot.id, 24)))
    analyses = {name: ClipAnalysis.from_dict(d) for name, d in plan.clips.items()}
    done = [0]

    def one(job: Job):
        a = analyses[job.shot.clip]
        extract_shot(job, a.info, a, frames_dir, scale, plan.look, lut_path, lut_apply, texture)
        done[0] += 1
        if progress:
            progress(done[0] / max(1, len(jobs)))

    # Big shots first so the pool doesn't end on a long straggler.
    jobs.sort(key=lambda j: -j.frames)
    with ThreadPoolExecutor(max_workers=workers or max(2, (os.cpu_count() or 2))) as pool:
        for _ in pool.map(one, jobs):
            pass


# ---------------------------------------------------------------------------- masks

def mask_requests(plan: EditPlan) -> dict[str, list[int]]:
    """Which shot frames need a person mask: hero (all), silhouette flash (last 5), cut-out (all), tri sticker (first)."""
    need: dict[str, list[int]] = {}
    for i, seg in enumerate(plan.segments):
        f0, f1 = plan.frames_of(seg)
        n = f1 - f0
        if seg.shot and seg.fx.get("hero"):
            need[seg.shot.id] = list(range(n))
        if seg.shot and seg.fx.get("sil"):
            need.setdefault(seg.shot.id, [])
            need[seg.shot.id] += list(range(max(0, n - int(seg.fx["sil"])), n))
        if seg.kind == "cutout":
            for sub in seg.subs:
                need[sub.id] = list(range(n))
        if seg.kind == "tri" and i + 1 < len(plan.segments) and plan.segments[i + 1].shot:
            need.setdefault(plan.segments[i + 1].shot.id, []).append(0)
    return need


def load_frame(work: Path, shot_id: str, i: int) -> Image.Image | None:
    d = work / "frames" / shot_id
    meta_path = d / "meta.json"
    if not meta_path.exists():
        return None
    meta = json.loads(meta_path.read_text())
    m = meta["map"]
    j = m[max(0, min(i, len(m) - 1))]
    files = sorted(d.glob("*.jpg"))
    if not files:
        return None
    return Image.open(files[max(0, min(j, len(files) - 1))]).convert("RGB")


def compute_masks(plan: EditPlan, work: Path, progress: Callable[[float], None] | None = None) -> int:
    masker = masks_mod.get_masker()
    if masker is None:
        return 0
    need = mask_requests(plan)
    total = sum(len(v) for v in need.values())
    done = 0
    for shot_id, frames in need.items():
        out = work / "masks" / shot_id
        out.mkdir(parents=True, exist_ok=True)
        raw: list[tuple[int, np.ndarray]] = []
        for i in sorted(set(frames)):
            im = load_frame(work, shot_id, i)
            if im is None:
                continue
            raw.append((i, masker.predict(im)))
            done += 1
            if progress:
                progress(done / max(1, total))
        smoothed = masks_mod.smooth_masks([m for _, m in raw]) if len(raw) > 2 else [m for _, m in raw]
        for (i, _), m in zip(raw, smoothed):
            Image.fromarray((np.clip(m, 0, 1) * 255).astype(np.uint8)).save(out / f"{i:04d}.png")
    return total


def load_mask(work: Path, shot_id: str, i: int) -> Image.Image | None:
    p = work / "masks" / shot_id / f"{i:04d}.png"
    return Image.open(p).convert("L") if p.exists() else None
