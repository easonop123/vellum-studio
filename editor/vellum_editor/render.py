"""Draws every frame of the edit: the 16:9 master, then the vertical version around it.

A port of the reference scripts' render()/wrapv(): same effects, timings and
layout, written in 1920x1080 master units and scaled to the render size.
"""
from __future__ import annotations

import json
import random
from collections import OrderedDict
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps

from . import fx
from .extract import EXTRA_FRAMES
from .looks import finish_amounts, get_look
from .plan import FPS, PEEK, EditPlan, Segment, Shot
from .text import TitleLayout, anton, center_text, draw_title, grotesk, mono, tiktok


def even(v: float) -> int:
    return max(2, int(round(v / 2)) * 2)


class Renderer:
    def __init__(self, plan: EditPlan, work: Path, scale: float = 1.0):
        self.plan = plan
        self.work = Path(work)
        self.S = scale
        self.W, self.H = even(1920 * scale), even(1080 * scale)
        self.VW, self.VH = even(1080 * scale), even(1920 * scale)
        self.VY, self.VHt = int(656 * scale), even(608 * scale)
        self.look = get_look(plan.look)
        texture = bool((plan.settings.get("render") or {}).get("texture", True))
        self.finish = fx.Finisher(self.W, self.H, *finish_amounts(self.look, texture))
        self.segs = plan.segments
        self.ranges = [plan.frames_of(s) for s in self.segs]
        self.end = plan.end_frame
        self.total = plan.total_frames
        self.title = (plan.title or "VELLUM").upper()
        self.layout = TitleLayout.from_dict(plan.title_layout) if plan.title_layout else None
        self.year = plan.settings.get("year", 2026)
        self.clip_durations = {name: d["info"]["duration"] for name, d in plan.clips.items()}
        self._meta: dict[str, dict] = {}
        self._files: dict[str, list[Path]] = {}
        self._cache: OrderedDict[tuple[str, int], Image.Image] = OrderedDict()
        self._mask_cache: OrderedDict[tuple[str, int], Image.Image | None] = OrderedDict()
        self._pop_hues: dict[str, int] = {}
        self.whites = {plan.F(k) for k in plan.whites}
        self.blooms = [plan.F(k) for k in plan.blooms]
        self.drop = plan.F(0)
        self.ending_start = plan.F(plan.end_k - 3)
        s = scale
        self.f_label = mono(30 * s)
        self.f_corner_s = anton(30 * s)
        self.f_corner_l = anton(40 * s)
        self.T1, self.T2, self.T3 = tiktok(62 * s, "Bold"), tiktok(34 * s, "Medium"), tiktok(30 * s, "SemiBold")
        self.T_cta = tiktok(56 * s, "Bold")

    # ------------------------------------------------------------------ frames
    def F(self, k: float) -> int:
        return self.plan.F(k)

    def _shot_meta(self, sid: str) -> dict | None:
        if sid not in self._meta:
            d = self.work / "frames" / sid
            p = d / "meta.json"
            if not p.exists():
                self._meta[sid] = {}
                self._files[sid] = []
            else:
                self._meta[sid] = json.loads(p.read_text())
                self._files[sid] = sorted(d.glob("*.jpg"))
        return self._meta[sid] or None

    def sframe(self, shot: Shot, i: int) -> Image.Image:
        """Frame i (0 = when the shot starts) of a shot, at its box size."""
        bw, bh = even(shot.box[0] * self.S), even(shot.box[1] * self.S)
        meta = self._shot_meta(shot.id)
        files = self._files.get(shot.id) or []
        if not meta or not files:
            return Image.new("RGB", (bw, bh), (12, 12, 14))
        m = meta["map"]
        j = m[max(0, min(i, len(m) - 1))]
        j = max(0, min(j, len(files) - 1))
        key = (shot.id, j)
        im = self._cache.get(key)
        if im is None:
            im = Image.open(files[j]).convert("RGB")
            if im.size != (bw, bh):
                im = im.resize((bw, bh), Image.BILINEAR)
            self._cache[key] = im
            if len(self._cache) > 20:  # ~120 MB per worker at full size
                self._cache.popitem(last=False)
        else:
            self._cache.move_to_end(key)
        return im.copy()

    def mask(self, shot: Shot, i: int, size: tuple[int, int] | None = None) -> Image.Image | None:
        key = (shot.id, i)
        if key not in self._mask_cache:
            p = self.work / "masks" / shot.id / f"{i:04d}.png"
            self._mask_cache[key] = Image.open(p).convert("L") if p.exists() else None
            if len(self._mask_cache) > 24:
                self._mask_cache.popitem(last=False)
        m = self._mask_cache[key]
        if m is None:
            return None
        size = size or (self.W, self.H)
        return m.resize(size, Image.BILINEAR) if m.size != size else m

    def base(self, seg: Segment, i: int) -> Image.Image:
        f0, f1 = self.ranges[self.segs.index(seg)]
        n = max(1, f1 - f0)
        im = self.sframe(seg.shot, i) if seg.shot else Image.new("RGB", (self.W, self.H), (12, 12, 14))
        if im.size != (self.W, self.H):
            im = im.resize((self.W, self.H), Image.BILINEAR)
        creep = seg.fx.get("creep")
        if creep:
            im = fx.scale_c(im, 1 + creep * i / n)
        if seg.fx.get("punch") and i < 4:
            im = fx.scale_c(im, 1 + 0.16 * (1 - i / 4) ** 2)
        return im

    # ------------------------------------------------------------------ 16:9
    def render(self, f: int) -> Image.Image:
        if f >= self.end:
            return self.endcard(f)
        k = self._seg_index(f)
        s = self.segs[k]
        f0, f1 = self.ranges[k]
        i, n = f - f0, f1 - f0
        nxt = self.segs[k + 1] if k + 1 < len(self.segs) else None
        prev = self.segs[k - 1] if k > 0 else None
        S = self.S

        if s.kind == "grid9":
            im = self.grid9(s, i, n, f0)
        elif s.kind == "tri":
            im = self.tri(s, k, i, n, f0)
        elif s.kind == "film":
            im = self.film(s, i, n)
        elif s.kind == "cutout":
            im = self.cutout(s, i, n)
        elif s.kind == "tmask":
            im = self.tmask(s, i, n)
        else:
            im = self.base(s, i)
            if s.fx.get("raw"):
                im = self.raw_overlay(im, s, i)
                if s.fx.get("prebloom") and i >= n - 3:
                    im = fx.bloom(im, 1.6 + 0.6 * (i - (n - 3)))
                if nxt and nxt.fx.get("whip") and i >= n - 3:
                    im = fx.mblur(im, [140, 380, 700][i - (n - 3)] * S)
                return im
            if s.fx.get("hero"):
                im = self.hero_title(im, s, i)
            if s.fx.get("bw") and i < int(s.fx["bw"]):
                im = fx.bw(im)
            if s.fx.get("cpop") and i >= 2:
                im = self.cpop(im, s)
            if s.fx.get("rgb") and i < 3:
                im = fx.rgbsplit(im, max(1, int(14 * S)))
            if s.fx.get("sil") and i >= n - int(s.fx["sil"]):
                im = self.silflash(im, s, i, n)
            if s.fx.get("spaced"):
                im = self.spaced(im, i, n)

        # transitions
        if prev is not None and s.fx.get("slit") and i < PEEK["slit"]:
            im = self.slit_in(im, self.peek(k - 1, i), i)
        elif prev is not None and s.fx.get("strips") and i < PEEK["strips"]:
            im = self.strips_in(im, self.peek(k - 1, i), i)
        elif prev is not None and s.fx.get("shrink") and i < PEEK["shrink"]:
            im = self.shrink_over(im, self.peek(k - 1, i), i)
        if s.fx.get("burn") and i < 6:  # light-leak burn across the cut (v4/v6)
            im = fx.burn(im, 0.45 + i * 0.1)
        if nxt and nxt.fx.get("burn") and i >= n - 4:
            im = fx.burn(im, (i - (n - 4)) * 0.12 + 0.05)
        if s.fx.get("whip") and i < 3:
            im = fx.mblur(im, [700, 380, 140][i] * S)
        if nxt and nxt.fx.get("whip") and i >= n - 3:
            im = fx.mblur(im, [140, 380, 700][i - (n - 3)] * S)
        zt = int(s.fx.get("zt") or 0)
        if zt and i >= n - zt:
            p = (i - (n - zt) + 1) / zt
            im = fx.zoomblur(fx.scale_c(im, 1 + 0.9 * p * p), 0.7 * p)
        if s.fx.get("leak"):
            a = max(0, n // 2 - 4) if s.fx.get("boom") else max(0, n // 4)
            if a <= i < a + 9:
                im = fx.burn(im, (i - a) / 9)
        if s.fx.get("boom") or s.fx.get("hero"):
            if i in (1, 2):
                im = fx.zoomblur(im, 1.0 if i == 1 else 0.5)
            if 1 <= i <= 10:
                im = fx.shake(im, 28 * S * 0.72 ** (i - 1), 6 * S * (1 - (i - 1) / 10), f)
        if s.fx.get("pips"):
            im = self.pips(im, s, i, f0)
        if s.fx.get("ending"):
            im = self.ending_title(im, i, n)

        im = self.finish(im, f)
        if s.fx.get("border") and i < 3:
            im = fx.border(im, i, S)
        if s.fx.get("flash") and i < 2:
            im = fx.flash(im, [0.85, 0.45][i])
        if s.fx.get("dark") and i < 2:  # black flash
            im = fx.flash(im, [0.85, 0.4][i], (0, 0, 0))
        if s.fx.get("flicker") and i < 6:
            im = Image.eval(im, lambda v, g=[1.0, 0.45, 1.25, 0.6, 1.12, 0.85][i]: min(255, int(v * g)))
        if s.fx.get("glitch") and i < 3:
            im = fx.glitch(im, i, S)
        im = self.labels(im, f)
        if s.fx.get("ending"):
            im = self.letterbox(im, i, n)
            if i >= n - 3 and len(self.title) <= 12:
                im = fx.glitch(im, i - (n - 3), S)
        for b in self.blooms:
            if b - 2 <= f < b:
                im = fx.bloom(im, [1.5, 2.3][f - (b - 2)])
            elif b <= f < b + 3:
                im = fx.bloom(im, [2.6, 1.9, 1.35][f - b])
        if f in self.whites:
            im = Image.new("RGB", (self.W, self.H), (255, 255, 255))
        elif f - 1 in self.whites:
            im = fx.flash(im, 0.45)
        return im

    def _seg_index(self, f: int) -> int:
        for k, (a, b) in enumerate(self.ranges):
            if a <= f < b:
                return k
        return len(self.segs) - 1

    # ------------------------------------------------------------------ pieces
    def peek(self, kp: int, i: int) -> Image.Image:
        """Segment kp's shot carrying on i frames past its end (the planner reserved that footage)."""
        prev = self.segs[kp]
        if prev.kind != "shot" or prev.shot is None:
            return Image.new("RGB", (self.W, self.H), (8, 8, 8))
        f0, f1 = self.ranges[kp]
        return self.base(prev, f1 - f0 + i)

    def slit_in(self, cur: Image.Image, prev: Image.Image, i: int) -> Image.Image:
        """Slit reveal (v6): the new shot opens from a centre slit with thin white edges."""
        t = fx.ease((i + 1) / 5)
        w = int(self.W * t)
        x = (self.W - w) // 2
        out = prev.copy()
        if w > 0:
            out.paste(cur.crop((x, 0, x + w, self.H)), (x, 0))
            e = max(1, round(3 * self.S))
            d = ImageDraw.Draw(out)
            d.rectangle([x - e, 0, x, self.H], fill=(255, 255, 255))
            d.rectangle([x + w, 0, x + w + e, self.H], fill=(255, 255, 255))
        return out

    def strips_in(self, cur: Image.Image, prev: Image.Image, i: int) -> Image.Image:
        """Sliding strips (v6): the new shot comes in as three bands from alternate sides."""
        out = prev.copy()
        bh = self.H // 3
        for j in range(3):
            t = fx.ease((i - j * 0.8 + 1) / 4)
            if t <= 0:
                continue
            y0, y1 = j * bh, (self.H if j == 2 else (j + 1) * bh)
            dx = int((1 - t) * self.W * (1 if j % 2 == 0 else -1))
            out.paste(cur.crop((0, y0, self.W, y1)), (dx, y0))
        return out

    def shrink_over(self, im: Image.Image, prev: Image.Image, i: int, n: int = PEEK["shrink"]) -> Image.Image:
        """Polaroid fly-off (v7/v8): the last shot shrinks into a white-bordered print and flies off right."""
        S = self.S
        t = fx.ease((i + 1) / n)
        sc = 1 - 0.62 * t
        w, h = max(2, int(self.W * sc)), max(2, int(self.H * sc))
        b = max(2, round(10 * S))
        frame = Image.new("RGB", (w + 2 * b, h + 2 * b), (250, 248, 244))
        frame.paste(prev.resize((w, h), Image.BILINEAR), (b, b))
        x = int((self.W - frame.size[0]) / 2 + t * t * self.W * 0.9)
        y = int((self.H - frame.size[1]) / 2)
        out = im.copy()
        out.paste((0, 0, 0), (x + round(12 * S), y + round(16 * S)), Image.new("L", frame.size, 140))  # drop shadow
        out.paste(frame, (x, y))
        return out

    def pop_hue(self, s: Segment) -> int:
        """The colour a colour pop keeps: the shot's strongest saturated hue that isn't the whole frame.
        v8 popped the yellow of New York taxis; that yellow is the fallback."""
        key = s.id or f"{s.k0}"
        if key not in self._pop_hues:
            hsv = np.asarray(self.base(s, 2).convert("HSV"))
            strong = (hsv[..., 1] > 110) & (hsv[..., 2] > 60)
            hist = np.bincount(hsv[..., 0][strong].ravel(), minlength=256).astype(np.float64)
            window = np.convolve(np.concatenate([hist[-12:], hist, hist[:12]]), np.ones(25), "valid")  # +-12, wraps
            hue = 34
            for c in np.argsort(-window):
                share = window[c] / hsv[..., 0].size
                if share < 0.004:
                    break
                if share <= 0.4:
                    hue = int(c)
                    break
            self._pop_hues[key] = hue
        return self._pop_hues[key]

    def cpop(self, im: Image.Image, s: Segment) -> Image.Image:
        """Colour pop (v8): black and white with punchy contrast, except one colour."""
        hue = self.pop_hue(s)
        hsv = np.asarray(im.convert("HSV"))
        dh = np.abs(((hsv[..., 0].astype(np.int16) - hue + 128) % 256) - 128)
        keep = Image.fromarray(((dh < 12) & (hsv[..., 1] > 110)).astype(np.uint8) * 255)
        keep = keep.filter(ImageFilter.GaussianBlur(max(1.0, 2 * self.S)))
        out = ImageOps.autocontrast(ImageOps.grayscale(im), cutoff=1).convert("RGB")
        out.paste(im, (0, 0), keep)
        return out

    def raw_overlay(self, im: Image.Image, s: Segment, i: int) -> Image.Image:
        """Camera-roll look: the file name bottom left, the clip's length top right."""
        d = ImageDraw.Draw(im)
        S = self.S
        d.text((40 * S, self.H - 70 * S), s.label or "IMG_4821.MOV", font=self.f_label, fill=(255, 255, 255))
        secs = self.clip_durations.get(s.shot.clip if s.shot else "", 3.0)
        d.text((self.W - 140 * S, 40 * S), f"0:{min(59, max(1, round(secs))):02d}", font=self.f_label, fill=(255, 255, 255))
        return im

    def hero_title(self, im: Image.Image, s: Segment, i: int) -> Image.Image:
        """Title in hero red, typed on two frames per letter, behind the person."""
        L = self.layout
        if L is None or i < 2:
            return im
        letters = (i - 2) // 2 + 1
        layer = Image.new("L", (self.W, self.H), 0)
        draw_title(ImageDraw.Draw(layer), L, self.S, letters, 255)
        out = im.copy()
        out.paste(fx.RED, (0, 0), layer)
        if L.behind and s.shot is not None:
            m = self.mask(s.shot, i)
            if m is not None:
                out.paste(im, (0, 0), m)
        return out

    def labels(self, im: Image.Image, f: int) -> Image.Image:
        """Flickering red corner labels through the main section."""
        if f < self.drop or f >= self.ending_start:
            return im
        e = f - self.drop
        beat_frames = self.plan.beat * FPS
        ph = (e / beat_frames) % 8
        if (ph >= 7.0 and e % 2 == 0) or (ph < 0.4 and e % 2 == 1):
            return im
        S = self.S
        d = ImageDraw.Draw(im)
        c = (226, 30, 38)
        d.text((70 * S, 60 * S), "MOMENTS IN", font=self.f_corner_s, fill=c)
        d.text((70 * S, 92 * S), f"{self.title} {self.year}", font=self.f_corner_l, fill=c)
        t1, t2 = "EDITED BY", "VELLUM STUDIO"
        d.text((self.W - 70 * S - self.f_corner_s.getlength(t1), 60 * S), t1, font=self.f_corner_s, fill=c)
        d.text((self.W - 70 * S - self.f_corner_l.getlength(t2), 92 * S), t2, font=self.f_corner_l, fill=c)
        return im

    def silflash(self, im: Image.Image, s: Segment, i: int, n: int) -> Image.Image:
        """White silhouette flash of the person on a hit."""
        j = i - (n - int(s.fx["sil"]))
        m = self.mask(s.shot, i) if s.shot else None
        if m is None:
            return fx.flash(im, 0.25 + 0.1 * j)
        m = m.point(lambda v: 255 if v > 100 else 0)
        dark = Image.blend(im, Image.new("RGB", im.size), 0.25 + 0.12 * j)
        k = max(3, int(15 * self.S) | 1)
        glow = m.filter(ImageFilter.MaxFilter(k)).filter(ImageFilter.GaussianBlur(max(1, 22 * self.S)))
        dark.paste((255, 250, 240), (0, 0), glow.point(lambda v: int(v * 0.8)))
        dark.paste((255, 255, 255), (0, 0), m)
        return dark

    def spaced(self, im: Image.Image, i: int, n: int) -> Image.Image:
        """Spaced, glowing title letters fading in one by one (v6)."""
        word = self.title.replace(" ", "")[:9]
        if not word:
            return im
        f = grotesk(190 * self.S, "Bold")
        lay = Image.new("L", im.size, 0)
        d = ImageDraw.Draw(lay)
        k = len(word)
        span = self.W * 0.74
        x0 = (self.W - span) / 2
        order = random.Random(11).sample(range(k), k)
        alphas = [0.0] * k
        for r, j in enumerate(order):
            alphas[j] = max(0.0, min(1.0, (i - 3 - r * 1.5) / 3))
        if i > n - 5:
            alphas = [a * max(0.0, (n - i) / 5) for a in alphas]
        for j, ch in enumerate(word):
            if alphas[j] <= 0:
                continue
            cx = x0 + (span * j / (k - 1) if k > 1 else span / 2)
            w = d.textlength(ch, font=f)
            y = self.H * 0.44 - int(18 * self.S * (1 - alphas[j]))
            d.text((cx - w / 2, y - 95 * self.S), ch, font=f, fill=int(255 * alphas[j]))
        glow = lay.filter(ImageFilter.GaussianBlur(max(1, 18 * self.S)))
        a = np.asarray(im, np.float32)
        g = np.asarray(glow, np.float32)[..., None] / 255 * 0.9
        t = np.asarray(lay, np.float32)[..., None] / 255
        a = 255 - (255 - a) * (1 - g)
        a = a * (1 - t) + 255 * t
        return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))

    def tmask(self, s: Segment, i: int, n: int) -> Image.Image:
        """Giant title letters as windows onto the footage, typed in on the beat."""
        frame = self.base(s, i)
        word = self.title
        f = anton(min(760 * self.S, 99999))
        bb = f.getbbox(word)
        if bb[2] - bb[0] > self.W * 0.92:
            f = anton(760 * self.S * self.W * 0.92 / (bb[2] - bb[0]))
            bb = f.getbbox(word)
        shown = word[: min(len(word), i // 4 + 1)]
        m = Image.new("L", (self.W, self.H), 0)
        tw = f.getlength(word)
        ImageDraw.Draw(m).text(((self.W - tw) / 2, self.H / 2 - (bb[1] + bb[3]) / 2), shown, font=f, fill=255)
        out = Image.new("RGB", (self.W, self.H), (6, 6, 6))
        out.paste(frame, (0, 0), m)
        return out

    def grid9(self, s: Segment, i: int, n: int, f0: int) -> Image.Image:
        """3x3 grid that builds tile by tile (flash only on the newest), then zooms into the centre."""
        S = self.S
        can = Image.new("RGB", (self.W, self.H), (8, 8, 8))
        tw, th = even(640 * S), even(360 * S)
        newest = -1
        for j, sub in enumerate(s.subs[:9]):
            a = self.F(s.k0 + sub.at) - f0
            if i >= a:
                p = self.sframe(sub, i - a)
                if p.size != (tw, th):
                    p = p.resize((tw, th))
                if i - a < 3:
                    p = fx.scale_c(p, 1 + 0.25 * (1 - (i - a) / 3) ** 2)
                if i == a:
                    p = fx.flash(p, 0.45)
                    newest = j
                can.paste(p, ((j % 3) * tw, (j // 3) * th))
        d = ImageDraw.Draw(can)
        lw = max(1, int(3 * S))
        for x in (tw, 2 * tw):
            d.rectangle([x - lw, 0, x + lw, self.H], fill=(8, 8, 8))
        for y in (th, 2 * th):
            d.rectangle([0, y - lw, self.W, y + lw], fill=(8, 8, 8))
        z = max(2, self.F(s.k1) - self.F(s.k1 - float(s.fx.get("zoom", 0.25))))
        if i >= n - z:
            t = fx.ease((i - (n - z) + 1) / z)
            can = fx.scale_c(can, 1 + 2 * t)
            if t > 0.5:
                can = fx.zoomblur(can, 0.5 * t)
        return can

    def tri(self, s: Segment, k: int, i: int, n: int, f0: int) -> Image.Image:
        """Triple frame: three panels drop in on the beat, then the next clip's person pops out as a sticker."""
        S = self.S
        can = Image.new("RGB", (self.W, self.H), (8, 8, 8))
        pw = even(640 * S)
        for j, sub in enumerate(s.subs[:3]):
            a = self.F(s.k0 + sub.at) - f0
            if i >= a:
                p = self.sframe(sub, i - a)
                if p.size != (pw, self.H):
                    p = p.resize((pw, self.H))
                can.paste(p, (j * pw, int(70 * S * (1 - fx.ease((i - a + 1) / 3)))))
                if i == a:
                    can = fx.flash(can, 0.35)
        d = ImageDraw.Draw(can)
        for x in (pw, 2 * pw):
            d.rectangle([x - 4 * S, 0, x + 4 * S, self.H], fill=(8, 8, 8))
        nxt = self.segs[k + 1] if k + 1 < len(self.segs) else None
        stick = self.F(s.k0 + float(s.fx.get("stick", 1.25))) - f0
        trans = self.F(s.k0 + float(s.fx.get("trans", 1.5))) - f0
        if nxt is None or nxt.shot is None or i < stick:
            return can
        full = self.sframe(nxt.shot, 0).resize((self.W, self.H))
        m = self.mask(nxt.shot, 0)
        if m is None:
            # no person found: just push into the next clip
            if i >= trans:
                return Image.blend(can, full, fx.ease((i - trans + 1) / max(1, n - trans)))
            return can
        m = m.point(lambda v: 255 if v > 110 else 0).filter(ImageFilter.GaussianBlur(max(0.5, S)))
        bx = m.getbbox() or (0, 0, self.W, self.H)
        nat = ((bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2)

        def place(sc: float, ctr: tuple[float, float], olw: float):
            w, h = int(self.W * sc), int(self.H * sc)
            x, y = int(ctr[0] - nat[0] * sc), int(ctr[1] - nat[1] * sc)
            fx.outline_place(can, full.resize((w, h), Image.BILINEAR), m.resize((w, h)), x, y, S, olw)

        if i < trans:
            can = Image.blend(can, Image.new("RGB", can.size), 0.35)
            p = min(1.0, (i - stick + 1) / 3)
            place(0.62 * (1 + 0.14 * (1 - p) ** 2), (self.W / 2, self.H / 2 + 30 * S), 1.0)
            if i == stick:
                can = fx.flash(can, 0.3)
        else:
            t = fx.ease((i - trans + 1) / max(1, n - trans))
            sc = 0.62 + 0.38 * t
            ctr = ((1 - t) * self.W / 2 + t * nat[0], (1 - t) * (self.H / 2 + 30 * S) + t * nat[1])
            can = Image.blend(Image.blend(can, Image.new("RGB", can.size), 0.35), full, t)
            place(sc, ctr, 1 - t)
        return can

    def film(self, s: Segment, i: int, n: int) -> Image.Image:
        """Film strip of four clips scrolling past over a blurred background."""
        S = self.S
        bg = self.base(s, i).resize((max(2, self.W // 4), max(2, self.H // 4))).filter(ImageFilter.GaussianBlur(max(1, 8 * S / 2)))
        can = Image.blend(bg.resize((self.W, self.H), Image.BILINEAR), Image.new("RGB", (self.W, self.H)), 0.45)
        d = ImageDraw.Draw(can)
        cards = s.subs[:4] or ([s.shot] if s.shot else [])
        if not cards:
            return can
        step = 640 * S
        off = (i * 26 * S) % step
        cw, chh = even(560 * S), even(690 * S)
        for kk in range(-1, 5):
            x = kk * step - off + 20 * S
            d.rectangle([x, 140 * S, x + 620 * S, 940 * S], fill=(14, 14, 14))
            for h in range(8):
                d.rectangle([x + (20 + h * 75) * S, 158 * S, x + (60 + h * 75) * S, 182 * S], fill=(230, 230, 226))
                d.rectangle([x + (20 + h * 75) * S, 898 * S, x + (60 + h * 75) * S, 922 * S], fill=(230, 230, 226))
            c = cards[(kk + int((i * 26 * S) // step)) % len(cards)]
            card = self.sframe(c, i)
            can.paste(card.resize((cw, chh)) if card.size != (cw, chh) else card, (int(x + 30 * S), int(205 * S)))
        return can

    def cutout(self, s: Segment, i: int, n: int) -> Image.Image:
        """The person from one clip cut out as a sticker and slid over another clip."""
        S = self.S
        bg = self.base(s, i)
        can = Image.blend(bg, Image.new("RGB", (self.W, self.H)), 0.15)
        if not s.subs:
            return can
        fg = self.sframe(s.subs[0], i).resize((self.W, self.H))
        m = self.mask(s.subs[0], i)
        if m is None:
            return can
        m = m.point(lambda v: 255 if v > 110 else 0).filter(ImageFilter.GaussianBlur(max(0.5, S)))
        sc = 0.82
        w, h = int(self.W * sc), int(self.H * sc)
        t = fx.ease((i + 1) / 6)
        x = int((self.W - w) / 2 + 120 * S + (1 - t) * self.W * 0.7)
        y = int(self.H - h + 40 * S)
        fx.outline_place(can, fg.resize((w, h), Image.BILINEAR), m.resize((w, h)), x, y, S)
        return can

    def pips(self, im: Image.Image, s: Segment, i: int, f0: int) -> Image.Image:
        """Picture-in-picture inserts with white frames (climax)."""
        S = self.S
        positions = ["tl", "br"]
        for slot, idx in enumerate(s.fx.get("pips", [])):
            if idx >= len(s.subs):
                continue
            sub = s.subs[idx]
            a = self.F(s.k0 + sub.at) - f0
            if i < a:
                continue
            pp = fx.ease((i - a + 1) / 4)
            sc = 0.30 * (0.7 + 0.3 * pp)
            w, h = int(self.W * sc), int(self.H * sc)
            ins = self.sframe(sub, i - a).resize((w, h))
            b = max(1, int(8 * S))
            fr = Image.new("RGB", (w + 2 * b, h + 2 * b), (250, 250, 246))
            fr.paste(ins, (b, b))
            pos = positions[slot % 2]
            xy = (int(70 * S), int(170 * S)) if pos == "tl" else (self.W - int(70 * S) - fr.size[0], self.H - int(70 * S) - fr.size[1])
            im.paste(fr, xy)
            if i == a:
                im = fx.flash(im, 0.35)
        return im

    def ending_title(self, im: Image.Image, i: int, n: int) -> Image.Image:
        """Title typed in white, then EDITED BY VELLUM spaced underneath (v8 ending)."""
        S = self.S
        f = anton(170 * S)
        word = self.title
        tw = f.getlength(word)
        if tw > self.W * 0.86:
            f = anton(170 * S * self.W * 0.86 / tw)
            tw = f.getlength(word)
        shown = word[: min(len(word), max(0, i - 2) + 1)] if i >= 2 else ""
        d = ImageDraw.Draw(im)
        d.text(((self.W - tw) / 2, self.H * 0.36), shown, font=f, fill=fx.BONE)
        if i >= len(word) + 8:
            fs = mono(32 * S)
            sub = "E D I T E D   B Y   V E L L U M"
            d.text(((self.W - fs.getlength(sub)) / 2, self.H * 0.36 + f.size * 1.25), sub, font=fs, fill=fx.BONE)
        return im

    def letterbox(self, im: Image.Image, i: int, n: int) -> Image.Image:
        S = self.S
        b0 = int(n * 0.5)
        if i >= b0:
            bh = int(130 * S + (self.H / 2 - 130 * S) * fx.ease((i - b0) / max(1, n - b0)) ** 2.2)
        else:
            bh = int(130 * S * min(1, (i + 1) / 5))
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, self.W, bh], fill=(0, 0, 0))
        d.rectangle([0, self.H - bh, self.W, self.H], fill=(0, 0, 0))
        return im

    # ------------------------------------------------------------------ end card
    def _endcard(self, w: int, h: int, f: int, vertical: bool) -> Image.Image:
        i = f - self.end
        if i == 0:
            return Image.new("RGB", (w, h), (255, 255, 255))
        S = self.S
        im = Image.new("RGB", (w, h), fx.BLACK)
        d = ImageDraw.Draw(im)
        big = grotesk((190 if vertical else 170) * S, "Bold")
        mid = mono((40 if vertical else 36) * S, "Medium")
        x = (170 if vertical else 550) * S
        y = (690 if vertical else 300) * S
        if (i // 12) % 2 == 0:
            r = 17 * S
            d.ellipse([x, y + 4 * S, x + 2 * r, y + 4 * S + 2 * r], fill=fx.BRED)
        d.text((x + 48 * S, y), f"00:00:{f // FPS:02d}:{f % FPS:02d}", font=mono(32 * S), fill=fx.GREY)
        y1 = y + 50 * S
        d.text((x, y1), "VELLUM"[: min(6, i // 2 + 1)], font=big, fill=fx.BONE)
        if i >= 8:
            d.text((x + 6 * S, y1 + big.size * 1.02), "/ STUDIO", font=big, fill=fx.BRED)
        if i >= 13:
            d.text((x + 8 * S, y1 + big.size * 2.25), "DM your clips", font=mid, fill=fx.BONE)
        if i >= 17:
            d.text((x + 8 * S, y1 + big.size * 2.25 + mid.size * 1.6), "@vellumstudio.edits", font=mid, fill=fx.GREY)
        return im

    def endcard(self, f: int) -> Image.Image:
        return self._endcard(self.W, self.H, f, False)

    def endcard_v(self, f: int) -> Image.Image:
        return self._endcard(self.VW, self.VH, f, True)

    # ------------------------------------------------------------------ vertical
    def vertical(self, im: Image.Image, f: int) -> Image.Image:
        """The house vertical: picture band in the middle, TikTok Sans text above and below."""
        if f >= self.end:
            return self.endcard_v(f)
        S = self.S
        v = Image.new("RGB", (self.VW, self.VH), (0, 0, 0))
        v.paste(im.resize((self.VW, self.VHt), Image.LANCZOS), (0, self.VY))
        d = ImageDraw.Draw(v)
        if f < self.drop:
            center_text(d, self.VW, 500 * S, "the clips they sent me", self.T1, (255, 255, 255))
            center_text(d, self.VW, self.VY + self.VHt + 40 * S, "no edit, no grade", self.T2, (170, 170, 170))
        elif f < self.ending_start:
            center_text(d, self.VW, 500 * S, "what i made with them", self.T1, (255, 255, 255))
        else:
            center_text(d, self.VW, 500 * S, "want yours like this?", self.T1, (255, 255, 255))
        if f >= self.drop:
            y = self.VY + self.VHt + 34 * S
            d.text((44 * S, y), "@vellumstudio.edits", font=self.T3, fill=(200, 200, 200))
            e = f - self.drop
            if (e // 12) % 2 == 0:
                d.ellipse([self.VW - 300 * S, y + 10 * S, self.VW - 280 * S, y + 30 * S], fill=fx.BRED)
            d.text((self.VW - 268 * S, y), f"REC {e // FPS // 60:02d}:{e // FPS % 60:02d}", font=self.T3, fill=(230, 230, 230))
        if f >= self.F(self.plan.end_k - 8):
            center_text(d, self.VW, 1450 * S, "dm me your clips", self.T_cta, (255, 255, 255))
        return v
