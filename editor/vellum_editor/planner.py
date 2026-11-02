"""Turn scored clips + a beat grid into an edit plan in the Vellum house style.

Structure (from the reference scripts):
  intro   raw "camera roll", 4-8 ungraded clips with file-name labels, up to the drop
  drop    white flash, the best clip, hero title behind the person
  body    graded beat cuts: mostly 8th notes, some 1-beat holds, quarter-beat bursts;
          small effects everywhere, at most 2 big effects, the second-best clip at the climax
  ending  "want yours like this?", title typed in, letterbox closes
  card    VELLUM / STUDIO end card

Never repeats footage: every clip is used once before any clip is used again,
and a second use is always a different moment, never next to the first.
"""
from __future__ import annotations

import datetime
import hashlib
import math
import random
from dataclasses import dataclass, field

from .analyze import ClipAnalysis, similarity
from .audio import SongAnalysis
from .plan import FPS, PEEK, H, W, EditPlan, Segment, Shot, peek_frames

LENGTHS = {"short": 30.0, "long": 60.0}
END_CARD_BEATS = 4
HERO_BEATS = 3
ENDING_BEATS = 3
TILE = (640, 360)

# One bar = 4 beats. (beats, effects) per cut.
PATTERNS: dict[str, list[tuple[float, dict]]] = {
    "eighths": [(0.5, {"punch": 1})] * 3 + [(0.5, {"punch": 1, "border": 1})] + [(0.5, {"punch": 1}), (0.5, {"punch": 1, "flicker": 1})] + [(0.5, {"punch": 1})] * 2,
    "mixed_a": [(1, {"creep": 0.04}), (0.5, {"punch": 1}), (0.5, {"punch": 1}), (1, {"whip": 1}), (0.5, {"punch": 1}), (0.5, {"punch": 1, "border": 1})],
    "mixed_b": [(0.5, {"punch": 1}), (0.5, {"whip": 1}), (1, {"creep": 0.05}), (0.5, {"punch": 1, "bw": 2}), (0.5, {"punch": 1, "dark": 1}), (1, {"punch": 1})],
    "burst": [(1, {"creep": 0.04}), (0.25, {"punch": 1, "rgb": 1}), (0.25, {"punch": 1}), (0.25, {"punch": 1, "rgb": 1}), (0.25, {"punch": 1}), (1, {"whip": 1}), (1, {"punch": 1})],
    "flash": [(1, {"punch": 1, "flash": 1}), (0.5, {"punch": 1}), (0.5, {"punch": 1, "glitch": 1}), (0.5, {"punch": 1, "bw": 2}), (0.5, {"punch": 1}), (1, {"creep": 0.04})],
    "holds": [(1, {"creep": 0.04}), (1, {"slit": 1}), (1, {"whip": 1}), (1, {"creep": 0.03, "cpop": 1})],
    "long": [(2, {"creep": 0.06, "leak": 1, "shrink": 1}), (1, {"punch": 1}), (1, {"whip": 1})],
}
REGULAR = ["eighths", "mixed_a", "mixed_b", "burst", "flash", "holds", "long"]

# Big effects: how many extra clips each needs, and whether it needs a person mask.
BIG = {
    "tmask": {"shots": 1, "mask": False, "weight": 2},
    "spaced": {"shots": 1, "mask": False, "weight": 2},
    "film": {"shots": 5, "mask": False, "weight": 3},
    "tri": {"shots": 4, "mask": False, "weight": 3},
    "grid9": {"shots": 9, "mask": False, "weight": 2},
    "cutout": {"shots": 2, "mask": True, "weight": 2},
    "silflash": {"shots": 1, "mask": True, "weight": 2},
}


@dataclass
class Slot:
    k0: float
    k1: float
    fx: dict
    role: str = "cut"  # intro | hero | climax | ending | cut | pip | tile | panel | card | bg | into
    kind: str = "shot"
    big: str | None = None
    box: tuple[int, int] = (W, H)
    speed: float = 1.0
    ramp: list[float] | None = None
    raw: bool = False
    parent: int | None = None  # index of the slot this sub-shot belongs to
    at: float = 0.0
    shot: Shot | None = None
    continues: int | None = None  # continue the clip of this slot (no new footage)
    peek: int = 0  # frames past the end still on screen (the next cut slits or flies in over it)


@dataclass
class Pool:
    """Hands out clip moments without ever repeating footage."""

    clips: list[ClipAnalysis]
    rng: random.Random
    used_ranges: dict[str, list[tuple[float, float]]] = field(default_factory=dict)
    last_used_at: dict[str, int] = field(default_factory=dict)
    order: int = 0

    def fresh(self) -> list[ClipAnalysis]:
        return [c for c in self.clips if c.name not in self.used_ranges]

    def _free(self, clip: ClipAnalysis, start: float, need: float) -> bool:
        for a, b in self.used_ranges.get(clip.name, []):
            if start < b + 0.25 and start + need > a - 0.25:
                return False
        return True

    def extend(self, clip: ClipAnalysis, start: float, old_end: float, new_end: float) -> bool:
        """Grow the range that starts at `start` to `new_end`, if no other use of the clip is in the way."""
        ranges = self.used_ranges.get(clip.name, [])
        own = min(ranges, key=lambda r: abs(r[0] - start), default=None)
        # shots store their start rounded to the millisecond; uses of a clip are always >0.25 s apart
        if own is None or abs(own[0] - start) > 1e-3 or new_end > clip.info.duration - 0.02:
            return False
        for a, b in ranges:
            if (a, b) is own or (a, b) == own:
                continue
            if old_end < b + 0.25 and new_end > a - 0.25:
                return False
        ranges[ranges.index(own)] = (own[0], max(own[1], new_end))
        return True

    def take(self, clip: ClipAnalysis, need: float, prefer: float | None = None) -> float | None:
        """Reserve `need` seconds of `clip`; returns the start time, or None if no free stretch is left."""
        dur = clip.info.duration
        if clip.info.kind == "photo":
            if clip.name in self.used_ranges:
                return None
            self.used_ranges[clip.name] = [(0.0, dur)]
            self.last_used_at[clip.name] = self.order
            return 0.0
        if need > dur - 0.02:
            return None
        candidates: list[float] = []
        if prefer is not None:
            candidates.append(prefer)
        if clip.name not in self.used_ranges:
            candidates.append(clip.window_start(need))
        candidates += clip.moments + [clip.best_start]
        candidates += [i * 0.25 for i in range(int((dur - need) / 0.25) + 1)]
        for start in candidates:
            start = max(0.0, min(start, dur - need - 0.02))
            if self._free(clip, start, need):
                self.used_ranges.setdefault(clip.name, []).append((start, start + need))
                self.last_used_at[clip.name] = self.order
                return start
        return None


def _seed_for(title: str, clips: list[ClipAnalysis]) -> int:
    h = hashlib.sha256((title.lower() + "|" + "|".join(sorted(c.name for c in clips))).encode()).hexdigest()
    return int(h[:8], 16)


def _label_for(name: str, i: int) -> str:
    stem = name.rsplit(".", 1)[0]
    upper = name.upper()
    if upper.startswith(("IMG_", "DJI_", "GX", "GH", "GOPR", "VID_", "PXL_", "MVI_", "DSC", "C0")):
        return upper
    return f"IMG_{4821 + i * 7}.MOV" if not stem else f"IMG_{4821 + i * 7}.MOV"


def grid_beat(song: SongAnalysis) -> float:
    """Half-time for very fast songs, double-time for very slow ones, so cuts stay around 4-8 per second."""
    if song.bpm > 150:
        return song.beat * 2
    if song.bpm < 72:
        return song.beat / 2
    return song.beat


def make_plan(
    analyses: list[ClipAnalysis],
    song: SongAnalysis,
    *,
    title: str,
    length: str = "short",
    look: str = "darkroom",
    masks_ok: bool = True,
    seed: int | None = None,
    settings: dict | None = None,
    strict: bool = False,
    max_end_k: int | None = None,
) -> EditPlan:
    """strict=True: a clip is never used twice, even at a different moment (fewer cuts if clips run out).

    The package length is a maximum: if the clips can't fill it without repeating
    footage, the edit ends earlier instead of holding one shot for ages.
    """
    call_args = dict(title=title, length=length, look=look, masks_ok=masks_ok, seed=seed, settings=settings, strict=strict)
    usable = [a for a in analyses if a.usable]
    if len(usable) < 2:
        raise ValueError("need at least 2 usable clips to make an edit")
    rng = random.Random(seed if seed is not None else _seed_for(title, usable))
    beat = grid_beat(song)
    notes: list[str] = []

    # ---- timeline -----------------------------------------------------------------
    max_total = LENGTHS.get(length, 30.0)
    intro_beats = 8.0
    if song.drop < intro_beats * beat:
        intro_beats = max(2.0, math.floor(song.drop / beat))
    offset = max(0.0, song.drop - intro_beats * beat)
    drop_edit = song.drop - offset
    avail = min(max_total, song.duration - offset - 0.05)
    end_k = int(math.floor((avail - drop_edit + 0.5 / FPS) / beat)) - END_CARD_BEATS
    end_k = max(8, end_k - end_k % 4)
    while end_k > 8 and drop_edit + (end_k + END_CARD_BEATS) * beat > avail + 0.5 / FPS:
        end_k -= 4
    if max_end_k is not None:
        end_k = max(12, min(end_k, max_end_k))
    total_k = end_k + END_CARD_BEATS

    vids = sorted([a for a in usable if a.info.kind == "video"], key=lambda a: -a.score)
    photos = [a for a in usable if a.info.kind == "photo"]

    def hero_rank(a: ClipAnalysis) -> float:
        return a.score + (0.12 if a.person > 0.04 else 0) + (0.05 if a.info.high_fps else 0) + (0.04 if a.info.duration >= 3 else -0.1)

    hero_clip = max(vids or usable, key=hero_rank)
    rest = [a for a in vids if a is not hero_clip]
    climax_clip = rest[0] if rest else hero_clip
    rest = rest[1:]
    ending_clip = rest[0] if len(rest) > 6 else None
    if ending_clip:
        rest = rest[1:]

    n_total = len(usable)
    n_intro = int(max(4, min(8, round(n_total * 0.22))))
    intro_clips = sorted(rest, key=lambda a: a.score)[: min(n_intro, max(2, len(rest) - 4))]
    for c in intro_clips:
        rest.remove(c)
    spare = len(rest) + len(photos)

    # ---- big effects (at most 2) ----------------------------------------------------
    has_person = masks_ok and any(a.person > 0.05 for a in usable)
    # Effects that eat lots of clips only when there are clips to spare.
    eligible = [
        k for k, v in BIG.items()
        if (not v["mask"] or has_person)
        and (v["shots"] <= 2 or (v["shots"] <= 5 and spare >= 24) or spare >= 34)
    ]
    big_count = 2 if spare >= 14 else 1 if spare >= 8 else 0
    if length == "short" and end_k < 24:
        big_count = min(big_count, 1)
    bigs: list[str] = []
    while eligible and len(bigs) < big_count:
        pick = rng.choices(eligible, weights=[BIG[k]["weight"] for k in eligible])[0]
        bigs.append(pick)
        eligible.remove(pick)
        spare -= BIG[pick]["shots"]

    # ---- slots ------------------------------------------------------------------------
    slots: list[Slot] = []

    # intro: 8 beats split over the intro clips; the last one swells to white
    n_i = max(1, len(intro_clips))
    patterns = {1: [8], 2: [4, 4], 3: [3, 3, 2], 4: [2, 2, 2, 2], 5: [2, 2, 1, 1, 2], 6: [1, 1, 1, 1, 2, 2], 7: [1, 1, 1, 1, 1, 1, 2], 8: [1] * 8}
    durs = [d * intro_beats / 8 for d in patterns[min(8, n_i)]]
    k = -intro_beats
    for d in durs:
        slots.append(Slot(k, k + d, {"raw": 1}, role="intro", raw=True))
        k += d
    slots[-1].fx["prebloom"] = 1

    # drop: hero
    hero_speed = 0.5 if hero_clip.info.high_fps else 1.0
    slots.append(Slot(0, HERO_BEATS, {"hero": 1, "creep": 0.05}, role="hero", speed=hero_speed))
    slots.append(Slot(HERO_BEATS, 4, {"punch": 1}, role="cut"))

    n_bars = int((end_k - ENDING_BEATS - 4) // 4)
    tail = (end_k - ENDING_BEATS) - (4 + n_bars * 4)  # 0..3 beats before the ending
    climax_bar = max(1, min(n_bars - 1, round(n_bars * 0.65))) if n_bars >= 3 else None
    big_bars: list[int] = []
    if bigs:
        spots = [round(n_bars * 0.3), round(n_bars * 0.82) if n_bars >= 6 else round(n_bars * 0.45)]
        for i, kind in enumerate(bigs):
            bar = max(0, min(n_bars - 1, spots[i]))
            while bar in big_bars or bar == climax_bar or (climax_bar is not None and bar == climax_bar - 1):
                bar = (bar + 1) % max(1, n_bars)
                if n_bars <= 2:
                    break
            big_bars.append(bar)
    big_at = dict(zip(big_bars, bigs))

    def capacity(c: ClipAnalysis) -> int:
        """Distinct moments a clip can give (never the same footage twice): longer clips give more."""
        if strict or c.info.kind == "photo":
            return 1
        cap = 3 if c.info.duration >= 12 else 2
        return max(1, min(cap, 1 + int((c.info.duration - 0.8) // 2.0)))

    # moments left for ordinary cuts (after big effects, climax inserts, the 1-beat cut after the hero and the tail)
    budget = sum(capacity(c) for c in rest if c.info.kind == "video") + len(photos)
    budget -= sum(BIG[b]["shots"] for b in bigs) + 2 + 1 + 3
    regular_bars = [b for b in range(n_bars) if b not in big_at and b != climax_bar]
    prev_pattern = None
    for b in range(n_bars):
        k0 = 4 + b * 4
        if b == climax_bar:
            pips = 2 if spare >= 10 else 0
            parent = len(slots)
            slots.append(Slot(k0, k0 + 4, {"boom": 1, "creep": 0.08, "leak": 1}, role="climax",
                              speed=0.45 if climax_clip.info.high_fps else 1.0))
            for j in range(pips):
                slots.append(Slot(k0, k0 + 4, {}, role="pip", parent=parent, at=2.5 + j * 0.5, box=(576, 324),
                                  speed=0.7 if j == 0 else 1.0))
            continue
        if b in big_at:
            k = big_at[b]
            k0_slots = _big_effect_slots(k, k0, slots, rng)
            slots.extend(k0_slots)
            continue
        bars_left = max(1, sum(1 for x in regular_bars if x >= b))
        per_bar = budget / bars_left
        target = max(3.0 if strict else 4.5, min(7.5, per_bar))
        choices = [p for p in REGULAR if p != prev_pattern]

        def cost(p: str) -> float:
            n = len(PATTERNS[p])
            c = abs(n - target) + rng.random() * 1.2
            if n > target + 1.5:
                c += 2.0  # more cuts than the footage can feed
            if p in ("holds", "long"):
                c += 0.9  # the house style is mostly 8th notes
            return c

        if climax_bar is not None and b == climax_bar - 1:
            name = "zoomthru"
            pattern = [(1, {"punch": 1}), (1, {"creep": 0.04}), (2, {"zt": 5})]
        else:
            name = min(choices, key=cost)
            pattern = PATTERNS[name]
        prev_pattern = name
        k = k0
        for d, fx in pattern:
            fx = dict(fx)
            slot = Slot(k, k + d, fx)
            if fx.get("zt"):
                slot.ramp = [0.7, 3.2]
            slots.append(slot)
            k += d
        budget -= len(pattern)

    k = 4 + n_bars * 4
    while k < end_k - ENDING_BEATS - 1e-6:
        d = min(1.0, end_k - ENDING_BEATS - k)
        slots.append(Slot(k, k + d, {"punch": 1, "rgb": 1} if d <= 0.5 else {"creep": 0.03}))
        k += d
    slots.append(Slot(end_k - ENDING_BEATS, end_k, {"ending": 1, "creep": 0.07}, role="ending"))

    # silhouette flash rides on a normal 1-beat cut
    if "silflash" in bigs:
        target = next((s for s in slots if s.role == "silflash"), None)
        if target is None:
            holds = [s for s in slots if s.role == "cut" and s.k1 - s.k0 >= 1 and s.k0 >= 6 and not s.fx.get("zt")]
            if holds:
                target = holds[len(holds) // 2]
                target.role = "silflash"
        if target:
            target.fx["sil"] = 5
            target.big = "silflash"

    # The slit reveal and the polaroid fly-off keep the previous cut playing on screen for a
    # few frames, so it has to be a plain cut, and it reserves that much more of its clip.
    mains = [s for s in slots if s.parent is None]
    for a, b in zip(mains, mains[1:]):
        for key, frames in PEEK.items():
            if not b.fx.get(key):
                continue
            plain = (a.role == "cut" and a.kind == "shot" and a.big is None and a.continues is None
                     and not a.ramp and not a.fx.get("zt") and abs(a.k1 - b.k0) < 1e-9)
            if plain:
                a.peek = max(a.peek, frames)
            else:
                b.fx.pop(key)

    # ---- assign footage ---------------------------------------------------------------
    pool = Pool(usable, rng)
    beat_s = beat
    plan_slots_frames = lambda s: max(1, int(round((drop_edit + s.k1 * beat_s) * FPS)) - int(round((drop_edit + s.k0 * beat_s) * FPS)))

    def need_seconds(s: Slot) -> float:
        n = plan_slots_frames(s) + 1 + s.peek
        if s.ramp:
            avg = sum(s.ramp) / 2 + 0.4
            return n * avg / FPS + 0.12
        return n * s.speed / FPS + 0.05

    def assign(s: Slot, clip: ClipAnalysis, reuse: bool = False) -> bool:
        need = need_seconds(s)
        start = pool.take(clip, need)
        if start is None and s.speed < 1.0:
            s.speed = 1.0
            need = need_seconds(s)
            start = pool.take(clip, need)
        if start is None:
            return False
        s.shot = Shot(clip=clip.name, ss=round(start, 3), speed=s.speed, ramp=s.ramp, box=s.box,
                      fx=round(clip.focus[0], 3), fy=round(clip.focus[1], 3), raw=s.raw, reuse=reuse)
        if clip.info.kind == "photo":
            s.fx["creep"] = max(float(s.fx.get("creep") or 0), 0.1)  # photos always get a slow zoom
            s.fx.pop("punch", None)
        return True

    # fixed roles first
    hero_slot = next(s for s in slots if s.role == "hero")
    assign(hero_slot, hero_clip)
    climax_slot = next((s for s in slots if s.role == "climax"), None)
    if climax_slot is not None:
        assign(climax_slot, climax_clip)
    ending_slot = next(s for s in slots if s.role == "ending")
    if ending_clip is not None:
        assign(ending_slot, ending_clip)
    intro_slots = [s for s in slots if s.role == "intro"]
    for s, c in zip(intro_slots, intro_clips):
        assign(s, c)

    # everything else in time order, choosing for variety
    prev_sig: list[list[float]] = [hero_clip.signature]
    for idx, s in enumerate(slots):
        pool.order = idx
        if s.shot is not None:
            prev_sig = (prev_sig + [pool_clip(usable, s.shot.clip).signature])[-2:]
            continue
        if s.role in ("grid", "tri"):
            continue  # composites: only their tiles/panels carry footage
        if s.continues is not None:
            src = slots[s.continues].shot
            if src is not None:
                # same clip, carrying straight on from where the tile left off (not a repeat)
                clip = pool_clip(usable, src.clip)
                start = src.ss + need_seconds(slots[s.continues]) - 0.1
                need = need_seconds(s)
                if start + need < clip.info.duration - 0.02:
                    pool.used_ranges.setdefault(clip.name, []).append((start, start + need))
                    s.shot = Shot(clip=clip.name, ss=round(start, 3), speed=s.speed, box=s.box, fx=src.fx, fy=src.fy)
                    s.fx["continues"] = 1
                    continue
        need = need_seconds(s)
        long_slot = (s.k1 - s.k0) >= 1 or s.role in ("bg", "climax", "silflash", "cutout_fg")
        wants_person = s.role in ("silflash", "cutout_fg") or s.fx.get("sil")

        def fit(c: ClipAnalysis, reuse: bool, min_gap: int = 4) -> float:
            if c.info.kind == "photo" and not (long_slot and s.role == "cut"):
                return -1e9
            if c.info.kind == "video" and c.info.duration < need + 0.05:
                return -1e9
            if wants_person and c.person < 0.05:
                return -1e9
            sim = max((similarity(c.signature, p) for p in prev_sig), default=0.0)
            v = c.score - 0.55 * max(0.0, sim - 0.55)
            if long_slot:
                v += 0.15 * min(1.0, c.person / 0.1)
            if s.box[0] < s.box[1] and c.info.vertical:  # tall panels love vertical clips
                v += 0.1
            if reuse:
                gap = idx - pool.last_used_at.get(c.name, -99)
                if gap < min_gap:
                    return -1e9  # never side by side with its other moment
                v -= 0.3 + 0.1 * len(pool.used_ranges.get(c.name, []))
            return v + rng.random() * 0.12

        # Tiers: an unused clip first; then a second moment of a clip; only if the footage
        # really runs out, a third or later moment. Footage itself is never repeated
        # (the pool refuses overlapping time ranges) and a clip never sits next to itself.
        tiers = [(0, 0)] if strict else [(0, 0), (2, 4), (3, 3), (4, 2)]
        placed = False
        for max_uses, min_gap in tiers:
            if max_uses == 0:
                cands = pool.fresh()
            else:
                cands = [
                    c for c in usable
                    if c.name in pool.used_ranges
                    and len(pool.used_ranges[c.name]) < (max(max_uses, 3) if (max_uses == 2 and c.info.duration >= 12) else max_uses)
                ]
            reuse = max_uses > 0
            ranked = sorted(cands, key=lambda c: fit(c, reuse, min_gap), reverse=True)
            for c in ranked:
                if fit(c, reuse, min_gap) < -1e8:
                    break
                if assign(s, c, reuse=reuse):
                    placed = True
                    break
            if placed:
                break
        if placed and s.shot:
            prev_sig = (prev_sig + [pool_clip(usable, s.shot.clip).signature])[-2:]

    # ---- footage ran out? end the edit earlier rather than hold one shot for ages ------
    empty_beats = sum(sl.k1 - sl.k0 for sl in slots if sl.shot is None and sl.parent is None and sl.kind == "shot")
    if empty_beats > 2 and end_k > 12:
        shorter = int(end_k - max(4, 4 * math.ceil((empty_beats - 1) / 4)))
        return make_plan(analyses, song, max_end_k=max(12, shorter), **call_args)

    # ---- build segments -------------------------------------------------------------
    segments: list[Segment] = []
    owner: dict[int, Segment] = {}
    for idx, s in enumerate(slots):
        if s.parent is not None:
            parent = owner.get(s.parent)
            if parent is not None and s.shot is not None:
                s.shot.at = s.at
                if s.role == "pip":
                    parent.fx.setdefault("pips", []).append(len(parent.subs))
                parent.subs.append(s.shot)
            continue
        seg = Segment(k0=s.k0, k1=s.k1, kind=s.kind, shot=s.shot, fx=dict(s.fx), big=s.big)
        if s.role == "intro" and s.shot:
            seg.label = _label_for(s.shot.clip, len(segments))
        owner[idx] = seg
        segments.append(seg)

    # Slots that got no footage: stretch the cut before them. The stretched cut must not run
    # into footage used elsewhere, so either reserve more of its clip or slow it down to fit.
    def nframes(k0: float, k1: float) -> int:
        return int(round((drop_edit + k1 * beat) * FPS)) - int(round((drop_edit + k0 * beat) * FPS))

    cleaned: list[Segment] = []
    for seg in segments:
        if seg.shot is None and seg.kind == "shot":
            if cleaned:
                prev = cleaned[-1]
                sh = prev.shot
                if sh is not None and prev.kind == "shot" and not sh.ramp:
                    clip = pool_clip(usable, sh.clip)
                    old_n, new_n = nframes(prev.k0, prev.k1), nframes(prev.k0, seg.k1)
                    old_end = sh.ss + (old_n + 1) * sh.speed / FPS + 0.05
                    new_end = sh.ss + (new_n + 1) * sh.speed / FPS + 0.05
                    if clip.info.kind == "video" and not pool.extend(clip, sh.ss, old_end, new_end):
                        sh.speed = round(max(0.2, sh.speed * old_n / max(1, new_n)), 4)
                    prev.fx["creep"] = max(float(prev.fx.get("creep") or 0), 0.05)
                prev.k1 = seg.k1
            continue
        cleaned.append(seg)
    segments = cleaned

    # A cut that a slit or polaroid plays on over must own those extra frames too (a stretched
    # cut may now sit in front of one): reserve them, or drop the transition if they're taken.
    for a, b in zip(segments, segments[1:]):
        peek = peek_frames(b)
        if not peek:
            continue
        sh = a.shot
        ok = (a.kind == "shot" and sh is not None and not sh.ramp
              and not any(a.fx.get(key) for key in ("raw", "hero", "boom", "zt", "sil", "spaced", "continues", "ending")))
        if ok and sh is not None:
            clip = pool_clip(usable, sh.clip)
            if clip.info.kind == "video":
                n = nframes(a.k0, a.k1)
                own_end = sh.ss + (n + 1) * sh.speed / FPS + 0.05
                ok = pool.extend(clip, sh.ss, own_end, sh.ss + (n + 1 + peek) * sh.speed / FPS + 0.05)
        if not ok:
            for key in PEEK:
                b.fx.pop(key, None)

    # flashes and blooms on structural beats
    whites = [0.0]
    blooms = [0.0, float(end_k)]
    if climax_slot is not None:
        whites.append(climax_slot.k0)
        blooms.append(climax_slot.k0)
    for b, kind in big_at.items():
        blooms.append(4 + b * 4)

    reused = sorted({sh.clip for seg in segments for sh in seg.all_shots() if sh.reuse})
    if reused:
        notes.append(
            f"only {len(usable)} usable clips for a {length} edit, so {len(reused)} long clips appear twice "
            "(different moments, never side by side). more clips would make it snappier."
        )

    plan = EditPlan(
        title=title.strip() or "Untitled",
        length=length,
        look=look,
        seed=rng.randrange(1 << 30),
        song={
            "path": song.path, "bpm": song.bpm, "beat": beat, "song_beat": song.beat, "drop": song.drop,
            "offset": offset, "duration": song.duration,
        },
        end_k=float(end_k),
        total_k=float(total_k),
        clips={a.name: a.to_dict() for a in analyses if a.usable},
        rejected=[{"name": a.name, "reason": a.reason, "thumb": a.thumb} for a in analyses if not a.usable],
        segments=segments,
        whites=sorted(set(whites)),
        blooms=sorted(set(blooms)),
        settings={**(settings or {}), "year": datetime.date.today().year, "masks": masks_ok, "strict": strict},
        notes=notes,
    )
    plan.assign_ids()
    return plan


def pool_clip(clips: list[ClipAnalysis], name: str) -> ClipAnalysis:
    return next(c for c in clips if c.name == name)


def _big_effect_slots(kind: str, k0: float, slots: list[Slot], rng: random.Random) -> list[Slot]:
    """The slots for one bar that holds a big effect."""
    out: list[Slot] = []
    base = len(slots)
    if kind == "grid9":
        out.append(Slot(k0, k0 + 2.5, {"zoom": 0.25}, kind="grid9", big="grid9", role="grid"))
        appear = [0.0, 0.25, 0.5, 0.75, 1.5, 1.0, 1.25, 1.75, 2.0]
        for i in range(9):
            out.append(Slot(k0, k0 + 2.5, {}, role="tile", parent=base, at=appear[i], box=TILE))
        # the grid zooms into the centre tile, and the next cut carries on with that clip
        out.append(Slot(k0 + 2.5, k0 + 3.5, {"creep": 0.04}, continues=base + 1 + 4))
        out.append(Slot(k0 + 3.5, k0 + 4, {"punch": 1}))
    elif kind == "tri":
        out.append(Slot(k0, k0 + 2, {"stick": 1.25, "trans": 1.5}, kind="tri", big="tri", role="tri"))
        for i in range(3):
            out.append(Slot(k0, k0 + 2, {}, role="panel", parent=base, at=i * 0.5, box=(640, 1080)))
        out.append(Slot(k0 + 2, k0 + 3, {"creep": 0.03, "into": 1}, role="into"))
        out.append(Slot(k0 + 3, k0 + 4, {"punch": 1}))
    elif kind == "film":
        out.append(Slot(k0, k0 + 2, {}, kind="film", big="film", role="bg"))
        for i in range(4):
            out.append(Slot(k0, k0 + 2, {}, role="card", parent=base, at=0.0, box=(560, 690)))
        out.append(Slot(k0 + 2, k0 + 3, {"punch": 1}))
        out.append(Slot(k0 + 3, k0 + 4, {"whip": 1}))
    elif kind == "tmask":
        out.append(Slot(k0, k0 + 2, {"creep": 0.05}, kind="tmask", big="tmask"))
        out.append(Slot(k0 + 2, k0 + 3, {"punch": 1, "flash": 1}))
        out.append(Slot(k0 + 3, k0 + 4, {"whip": 1}))
    elif kind == "spaced":
        out.append(Slot(k0, k0 + 2, {"creep": 0.1, "spaced": 1}, big="spaced"))
        out.append(Slot(k0 + 2, k0 + 3, {"punch": 1}))
        out.append(Slot(k0 + 3, k0 + 4, {"whip": 1}))
    elif kind == "cutout":
        out.append(Slot(k0, k0 + 1.5, {"creep": 0.04}, kind="cutout", big="cutout", role="bg"))
        out.append(Slot(k0, k0 + 1.5, {}, role="cutout_fg", parent=base, at=0.0))
        out.append(Slot(k0 + 1.5, k0 + 2, {"punch": 1}))
        out.append(Slot(k0 + 2, k0 + 3, {"whip": 1}))
        out.append(Slot(k0 + 3, k0 + 4, {"creep": 0.04}))
    elif kind == "silflash":
        out.append(Slot(k0, k0 + 1, {"creep": 0.04}, role="silflash"))
        for i in range(4):
            out.append(Slot(k0 + 1 + i * 0.25, k0 + 1.25 + i * 0.25, {"punch": 1, "rgb": 1 if i % 2 == 0 else 0}))
        out.append(Slot(k0 + 2, k0 + 3, {"whip": 1}))
        out.append(Slot(k0 + 3, k0 + 4, {"punch": 1}))
    return out
