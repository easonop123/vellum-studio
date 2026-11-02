"""Sound design: place the effects on the edit, then mix the two versions.

  sfx-only   the "post this" version: just the sound design (the customer adds the song in TikTok/Instagram)
  preview    the song from the edit's start point, ducked under impacts, plus the sound design

Cue list ported from the reference scripts' audio().
"""
from __future__ import annotations

import random
from dataclasses import dataclass

import numpy as np

from .ffmpeg import read_audio
from .plan import FPS, EditPlan
from .sfx import SHUTTERS, SR, load_bank


@dataclass
class Cue:
    name: str
    frame: float
    db: float
    fade: float = 0.0


def cues(plan: EditPlan) -> list[Cue]:
    F = plan.F
    out: list[Cue] = []
    shutter_i = [0]

    def add(name: str, frame: float, db: float, fade: float = 0.0):
        out.append(Cue(name, frame, db, fade))

    def shut(frame: float, db: float = -8):
        name = SHUTTERS[shutter_i[0] % 4]
        add(name, frame, db + (-3 if name == "shutter3" else 0))
        shutter_i[0] += 1

    beat_frames = plan.beat * FPS
    title_len = len(plan.title.replace(" ", "")) + plan.title.count(" ")
    segs = plan.segments
    for idx, s in enumerate(segs):
        f0, f1 = plan.frames_of(s)
        n = f1 - f0
        fx = s.fx
        if fx.get("raw"):
            add("click", f0, -9)
            if fx.get("prebloom"):
                add("riser", F(0) - 2.0 * FPS, -10, fade=0.8)  # riser 2 s before the drop
            continue
        if s.kind == "grid9":
            for sub in s.subs:
                a = F(s.k0 + sub.at)
                add("click", a, -7)
                shut(a, -11)
            add("whoosh", f1 - max(2, F(s.k1) - F(s.k1 - 0.25)), -6)
            continue
        if s.kind == "tri":
            for sub in s.subs:
                shut(F(s.k0 + sub.at), -6)
            add("click_loud", F(s.k0 + float(fx.get("stick", 1.25))), -5)
            add("ring", F(s.k0 + float(fx.get("stick", 1.25))), -12)
            add("whoosh", F(s.k0 + float(fx.get("trans", 1.5))) - 2, -7)
            continue
        if s.kind == "film":
            for j in range(0, n, 5):
                add("click", f0 + j, -10)
            add("whoosh", f0, -8)
            continue
        if s.kind == "tmask":
            for j in range(min(len(plan.title), max(1, n // 4))):
                add("click_loud", f0 + j * 4, -7)
            continue
        if s.kind == "cutout":
            add("whoosh", f0 - 2, -8)
            shut(f0 + 3, -6)
            continue
        if fx.get("hero") or fx.get("boom"):
            if fx.get("boom"):
                add("riser", f0 - 48, -10, fade=0.8)
            add("whoosh", f0 - 4, -6)
            add("impact", f0, 0)
            add("flash", f0, -4)
            add("click_loud", f0, -6)
            if fx.get("hero"):
                for j in range(8):  # burst of shutter clicks after the hit
                    add("click", f0 + 2 + j * 2, -7)
                add("ring", f0 + 2 + 2 * title_len, -12)  # when the title finishes typing
            for p_idx in fx.get("pips", []):
                if p_idx < len(s.subs):
                    a = F(s.k0 + s.subs[p_idx].at)
                    shut(a, -7)
                    add("flash", a, -10)
        else:
            shut(f0, -7 if (s.k1 - s.k0) <= 0.5 else -9)
        if fx.get("whip"):
            add("whoosh", f0 - 3, -8)
        if fx.get("punch"):
            add("click", f0, -10)
        if fx.get("border"):
            add("click_loud", f0, -7)
        if fx.get("flash"):
            add("flash", f0, -6)
        if fx.get("dark"):
            add("click_loud", f0, -8)
        if fx.get("flicker"):
            for j in range(0, 6, 2):
                add("click", f0 + j, -12)
        if fx.get("glitch"):
            add("glitch", f0, -9)
        if fx.get("cpop"):
            add("click_loud", f0 + 2, -7)  # when the colour drains out
        if fx.get("slit"):
            add("whoosh", f0 - 3, -8)
        if fx.get("shrink"):
            add("whoosh", f0, -9)
        if fx.get("zt"):
            add("whoosh", f1 - 5, -6)
        if fx.get("sil"):
            add("flash", f1 - int(fx["sil"]), -6)
            add("ring", f1 - int(fx["sil"]), -13)
        if fx.get("spaced"):
            for j in range(len(plan.title.replace(" ", "")[:9])):
                add("click", f0 + 3 + int(j * 1.5), -12)
            add("ring", f0 + 8, -13)
        if fx.get("ending"):
            add("whoosh", f0 - 2, -9)
            for j in range(len(plan.title)):
                add("click", f0 + 2 + j, -10)
            add("ring", f0 + 3 + len(plan.title), -12)
            add("glitch", f1 - 3, -8)
    for b in plan.blooms:
        if b != 0:
            add("flash", F(b), -6)
    end = plan.end_frame
    add("flash", end, -5)
    add("impact", end, -8)
    add("ring", end, -12)
    for j in range(6):
        add("click", end + j * 2, -11)
    return out


def _place(mix: np.ndarray, x: np.ndarray, frame: float, gain: float, pan: float, fade: float, duck: list, name: str):
    x = x * gain
    x = x * np.array([1 - pan, 1 + pan], np.float32)
    if fade:
        q = min(len(x), int(fade * SR))
        x[:q] *= np.linspace(0, 1, q)[:, None]
    i = int(round(frame / FPS * SR))
    if i < 0:  # a riser that would start before the edit: keep its tail
        x = x[-i:]
        i = 0
    j = min(len(mix), i + len(x))
    if j > i:
        mix[i:j] += x[: j - i]


def render_audio(plan: EditPlan, *, custom_sfx: str | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Return (sfx-only, preview-with-song), both float32 stereo at 48 kHz."""
    bank = load_bank(custom_sfx)
    n = int(round(plan.total_frames / FPS * SR))
    mix = np.zeros((n + SR * 3, 2), np.float32)
    rnd = random.Random(plan.seed)
    duck: list[tuple[float, float]] = []
    for c in cues(plan):
        snd = bank.get(c.name)
        if snd is None:
            continue
        gain = 10 ** ((c.db + rnd.uniform(-1.2, 1.2)) / 20)
        pan = rnd.uniform(-0.15, 0.15)
        _place(mix, snd.copy(), c.frame, gain, pan, c.fade, duck, c.name)
        if c.name == "impact":
            duck.append((c.frame / FPS, -3.5))
        elif c.name == "flash":
            duck.append((c.frame / FPS, -1.5))
    mix = mix[:n]

    sfx = mix * 10 ** (6 / 20)
    sfx = sfx / max(1.0, float(np.abs(sfx).max()) / 0.89)

    song = read_audio(plan.song["path"], sr=SR, channels=2, offset=float(plan.song["offset"]), duration=n / SR + 0.5)[:n]
    if len(song) < n:
        song = np.pad(song, ((0, n - len(song)), (0, 0)))
    env = np.ones(n, np.float32)
    for t0, db in duck:
        g = 1 - 10 ** (db / 20)
        lo = int(t0 * SR)
        if lo >= n or lo < 0:
            continue
        hi = min(n, lo + int(0.3 * SR))
        tt = np.arange(hi - lo) / SR
        env[lo:hi] -= g * np.clip(tt / 0.006, 0, 1) * np.clip(1 - (tt - 0.035) / 0.22, 0, 1)
    song = song * np.clip(env, 0.3, 1)[:, None] * 10 ** (-2 / 20)
    q = min(n, int(1.0 * SR))
    song[-q:] *= np.linspace(1, 0, q)[:, None]
    preview = song + mix
    preview = preview / max(1.0, float(np.abs(preview).max()) / 0.89)
    return sfx.astype(np.float32), preview.astype(np.float32)
