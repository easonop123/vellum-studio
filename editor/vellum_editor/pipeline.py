"""The whole job: song -> clips -> plan -> frames -> masks -> render -> sound -> files.

Used by the app window and the command line. Reports progress with an
estimated time left, can be cancelled, and always cleans up its temp folder.
"""
from __future__ import annotations

import json
import re
import shutil
import tempfile
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable

import numpy as np

from . import __version__
from . import masks as masks_mod
from .analyze import ClipAnalysis, analyse_folder, judge
from .audio import SongAnalysis, analyze_song
from .encode import mux, render_video
from .extract import EXTRA_FRAMES, compute_masks, extract_all, load_mask
from .ffmpeg import write_wav
from .mix import render_audio
from .plan import FPS, EditPlan
from .planner import make_plan
from .review import write_review
from .text import layout_title

ProgressFn = Callable[[float, str, str, float | None], None]  # (fraction 0..1, stage, message, seconds left)

STAGES = [
    ("song", 0.03, "reading the song"),
    ("clips", 0.16, "checking your clips"),
    ("plan", 0.01, "planning the edit"),
    ("frames", 0.2, "pulling frames"),
    ("masks", 0.07, "finding people"),
    ("render", 0.45, "rendering"),
    ("sound", 0.03, "sound design"),
    ("files", 0.05, "writing files"),
]


@dataclass
class EditSettings:
    clips_dir: str
    song: str
    title: str
    length: str = "short"  # short (30 s) | long (60 s)
    look: str = "darkroom"
    bpm: float | None = None  # override the detected tempo
    drop: float | None = None  # override the detected drop (seconds into the song)
    song_start: float = 0.0  # only look for the drop after this point
    scale: float = 1.0  # 1.0 = 1920x1080 and 1080x1920
    lut_path: str | None = None
    lut_apply: str = "off"  # off | dji | all
    sfx_folder: str | None = None
    use_masks: bool = True
    strict: bool = False  # never use a clip twice, even at a different moment
    workers: int | None = None
    crf: int = 17
    preset: str = "medium"
    out_dir: str | None = None
    keep_work: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class EditResult:
    out_dir: Path
    files: dict[str, Path]
    plan: EditPlan
    seconds: float
    song: SongAnalysis | None = None
    rejected: list[dict] = field(default_factory=list)


class Cancelled(Exception):
    pass


class Progress:
    def __init__(self, cb: ProgressFn | None, stages=STAGES):
        self.cb = cb
        self.start = time.time()
        self.order = [s[0] for s in stages]
        self.weight = {s[0]: s[1] for s in stages}
        self.label = {s[0]: s[2] for s in stages}
        total = sum(self.weight.values())
        self.weight = {k: v / total for k, v in self.weight.items()}
        self.last = 0.0

    def __call__(self, stage: str, frac: float, message: str = "") -> None:
        before = sum(self.weight[s] for s in self.order[: self.order.index(stage)])
        total = min(1.0, before + self.weight[stage] * max(0.0, min(1.0, frac)))
        self.last = max(self.last, total)
        elapsed = time.time() - self.start
        eta = elapsed * (1 - self.last) / self.last if self.last > 0.06 else None
        if self.cb:
            self.cb(self.last, stage, message or self.label[stage], eta)


def safe_title(title: str) -> str:
    t = re.sub(r'[\\/:*?"<>|]+', " ", title).strip()
    return re.sub(r"\s+", " ", t) or "Untitled"


def default_out_dir(clips_dir: str, title: str) -> Path:
    return Path(clips_dir) / f"Vellum Edit - {safe_title(title)}"


def output_names(title: str) -> dict[str, str]:
    t = safe_title(title)
    return {
        "vertical_post": f"{t} - vertical (post this).mp4",
        "vertical_preview": f"{t} - vertical (preview with song).mp4",
        "wide_post": f"{t} - 16x9 (post this).mp4",
        "wide_preview": f"{t} - 16x9 (preview with song).mp4",
        "plan": "edit-plan.json",
        "review": "review.html",
    }


# ---------------------------------------------------------------------------- song + clips

def analyse_song_with_overrides(settings: EditSettings) -> SongAnalysis:
    song = analyze_song(settings.song, search_from=settings.song_start)
    if settings.bpm:
        song = song.with_bpm(float(settings.bpm))
    if settings.drop is not None:
        song = song.with_drop(float(settings.drop))
    return song


CACHE_NAME = "analysis-cache.json"


def analyse_clips_cached(settings: EditSettings, out_dir: Path, progress: Callable[[float, str], None] | None = None) -> list[ClipAnalysis]:
    """Clip scores are cached next to the outputs so re-runs (new BPM, new drop, new title) skip this step."""
    from .looks import lut_filter  # noqa: F401  (kept for parity with analyse_folder)
    from .probe import list_media

    cache_path = out_dir / CACHE_NAME
    cache: dict = {}
    key = f"{__version__}|masks={settings.use_masks and masks_mod.available()}|lut={settings.lut_path}|{settings.lut_apply}"
    if cache_path.exists():
        try:
            data = json.loads(cache_path.read_text())
            if data.get("key") == key:
                cache = data.get("clips", {})
        except Exception:
            cache = {}
    files = list_media(settings.clips_dir)
    fresh_needed = []
    results: dict[str, ClipAnalysis] = {}
    for p in files:
        st = p.stat()
        c = cache.get(p.name)
        if c and c.get("size") == st.st_size and abs(c.get("mtime", 0) - st.st_mtime) < 1e-3:
            a = ClipAnalysis.from_dict(c["analysis"])
            a.info.path = str(p)
            results[p.name] = a
        else:
            fresh_needed.append(p)
    if fresh_needed:
        tmp = Path(tempfile.mkdtemp(prefix="vellum-scan-"))
        try:
            # analyse only the new files, via links in a scratch folder
            for p in fresh_needed:
                link = tmp / p.name
                try:
                    link.symlink_to(p)
                except OSError:
                    shutil.copy2(p, link)
            fresh = analyse_folder(tmp, lut=settings.lut_path or "", lut_apply=settings.lut_apply,
                                   use_masks=settings.use_masks, progress=progress)
            for a in fresh:
                a.info.path = str(Path(settings.clips_dir) / a.name)
                results[a.name] = a
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    out = [results[p.name] for p in files if p.name in results]
    # re-judge as a batch (thresholds are relative to the whole set)
    for a in out:
        if a.reason.startswith("kept (") or a.reason in ("blurry", "too shaky", "blown out", "too dark", "too short"):
            a.usable, a.reason = True, ""
    judge(out)
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps({
            "key": key,
            "clips": {a.name: {"size": Path(a.info.path).stat().st_size if Path(a.info.path).exists() else 0,
                               "mtime": Path(a.info.path).stat().st_mtime if Path(a.info.path).exists() else 0,
                               "analysis": a.to_dict()} for a in out},
        }))
    except OSError:
        pass
    return out


# ---------------------------------------------------------------------------- title layout

def hero_occupancy(plan: EditPlan, work: Path) -> np.ndarray | None:
    hero = next((s for s in plan.segments if s.fx.get("hero") and s.shot), None)
    if hero is None:
        return None
    f0, f1 = plan.frames_of(hero)
    acc, n = None, 0
    for i in range(2, f1 - f0):
        m = load_mask(work, hero.shot.id, i)
        if m is None:
            continue
        a = (np.asarray(m.resize((480, 270)), np.float32) / 255.0 > 0.5).astype(np.float32)
        acc = a if acc is None else acc + a
        n += 1
    return None if acc is None else acc / n


# ---------------------------------------------------------------------------- render an existing plan

def render_plan(plan: EditPlan, settings: EditSettings, out_dir: Path, progress: Progress,
                cancel: threading.Event | None = None) -> dict[str, Path]:
    def check():
        if cancel is not None and cancel.is_set():
            raise Cancelled()

    work = Path(tempfile.mkdtemp(prefix="vellum-"))
    try:
        extract_all(plan, work, settings.scale, lut_path=settings.lut_path, lut_apply=settings.lut_apply,
                    progress=lambda p: progress("frames", p), workers=settings.workers)
        check()
        if settings.use_masks and masks_mod.available():
            compute_masks(plan, work, progress=lambda p: progress("masks", p))
        progress("masks", 1.0)
        check()
        plan.title_layout = layout_title(plan.title, hero_occupancy(plan, work)).to_dict()
        plan.settings["render"] = {k: v for k, v in settings.to_dict().items() if k not in ("keep_work",)}
        plan_path = work / "plan.json"
        plan.save(plan_path)
        h, v = work / "wide.mp4", work / "vertical.mp4"
        render_video(plan, plan_path, work, settings.scale, h, v, workers=settings.workers, crf=settings.crf,
                     preset=settings.preset, progress=lambda p: progress("render", p), cancel=cancel)
        check()
        progress("sound", 0.1)
        sfx, preview = render_audio(plan, custom_sfx=settings.sfx_folder)
        write_wav(work / "sfx.wav", sfx)
        write_wav(work / "preview.wav", preview)
        progress("sound", 1.0)
        out_dir.mkdir(parents=True, exist_ok=True)
        names = output_names(plan.title)
        files = {
            "vertical_post": out_dir / names["vertical_post"],
            "vertical_preview": out_dir / names["vertical_preview"],
            "wide_post": out_dir / names["wide_post"],
            "wide_preview": out_dir / names["wide_preview"],
            "plan": out_dir / names["plan"],
            "review": out_dir / names["review"],
        }
        mux(v, work / "sfx.wav", files["vertical_post"])
        progress("files", 0.25)
        mux(v, work / "preview.wav", files["vertical_preview"])
        progress("files", 0.5)
        mux(h, work / "sfx.wav", files["wide_post"])
        progress("files", 0.7)
        mux(h, work / "preview.wav", files["wide_preview"])
        plan.save(files["plan"])
        write_review(plan, work, files["review"], [names[k] for k in ("vertical_post", "vertical_preview", "wide_post", "wide_preview")])
        progress("files", 1.0, "done")
        return files
    finally:
        if settings.keep_work:
            print(f"kept work folder: {work}")
        else:
            shutil.rmtree(work, ignore_errors=True)


# ---------------------------------------------------------------------------- the full job

def make_edit(settings: EditSettings, on_progress: ProgressFn | None = None, cancel: threading.Event | None = None,
              song: SongAnalysis | None = None) -> EditResult:
    t0 = time.time()
    progress = Progress(on_progress)
    out_dir = Path(settings.out_dir) if settings.out_dir else default_out_dir(settings.clips_dir, settings.title)

    progress("song", 0.1)
    song = song or analyse_song_with_overrides(settings)
    progress("song", 1.0, f"{song.bpm:.1f} bpm, drop at {song.drop:.2f}s")
    if cancel is not None and cancel.is_set():
        raise Cancelled()

    clips = analyse_clips_cached(settings, out_dir, progress=lambda p, name: progress("clips", p, f"checking {name}"))
    usable = [c for c in clips if c.usable]
    if len(usable) < 2:
        raise ValueError(f"only {len(usable)} usable clips in that folder: an edit needs at least 2")
    if cancel is not None and cancel.is_set():
        raise Cancelled()

    plan = make_plan(clips, song, title=settings.title, length=settings.length, look=settings.look,
                     masks_ok=settings.use_masks and masks_mod.available(), strict=settings.strict,
                     settings={"clips_dir": settings.clips_dir})
    progress("plan", 1.0, f"{len(plan.segments)} cuts")
    files = render_plan(plan, settings, out_dir, progress, cancel)
    return EditResult(out_dir=out_dir, files=files, plan=plan, seconds=time.time() - t0, song=song,
                      rejected=plan.rejected)


def rerender(plan_path: str | Path, on_progress: ProgressFn | None = None, cancel: threading.Event | None = None,
             overrides: dict | None = None) -> EditResult:
    """Render an edit-plan.json again (after swapping a shot, changing the look, ...)."""
    t0 = time.time()
    plan = EditPlan.load(plan_path)
    stored = dict(plan.settings.get("render") or {})
    stored.update(overrides or {})
    settings = EditSettings(**{k: v for k, v in stored.items() if k in EditSettings.__dataclass_fields__})
    if "look" in (overrides or {}):
        plan.look = overrides["look"]
    progress = Progress(on_progress, stages=[s for s in STAGES if s[0] not in ("song", "clips", "plan")])
    files = render_plan(plan, settings, Path(plan_path).parent, progress, cancel)
    return EditResult(out_dir=Path(plan_path).parent, files=files, plan=plan, seconds=time.time() - t0, rejected=plan.rejected)


def swap_shot(plan: EditPlan, segment_number: int, clip_name: str) -> str:
    """Put a different clip into one segment (segment numbers start at 1, as in review.html). Returns a note."""
    from .analyze import ClipAnalysis as CA

    seg = plan.segments[segment_number - 1]
    shot = seg.shot or (seg.subs[0] if seg.subs else None)
    if shot is None:
        raise ValueError("that segment has no footage to swap")
    if clip_name not in plan.clips:
        raise ValueError(f"{clip_name} isn't one of the usable clips")
    a = CA.from_dict(plan.clips[clip_name])
    f0, f1 = plan.frames_of(seg)
    speed = shot.speed if (shot.speed >= 1 or a.info.high_fps) else 1.0
    need = (f1 - f0 + EXTRA_FRAMES) * speed / FPS + 0.1
    shot.clip = clip_name
    shot.speed = speed
    shot.ramp = shot.ramp if a.info.kind == "video" else None
    shot.ss = round(a.window_start(need), 3)
    shot.fx, shot.fy = round(a.focus[0], 3), round(a.focus[1], 3)
    shot.reuse = False
    used_elsewhere = [i + 1 for i, s in enumerate(plan.segments) if s is not seg and any(sh.clip == clip_name for sh in s.all_shots())]
    plan.assign_ids()
    if used_elsewhere:
        return f"{clip_name} is also in segment {', '.join(map(str, used_elsewhere))}"
    return ""
