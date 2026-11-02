"""Fonts, and the hero title that sits behind the person.

The title must always stay readable: we measure how much of every letter the
person's mask covers across the hero shot, and try (in order of size) the
title centred, beside the person, split left and right of them, or above
them. If none of those keep the letters clear, it goes in front of the person.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from . import paths

MW, MH = 1920, 1080  # master frame


@lru_cache(maxsize=128)
def font(path: str, size: int, variation: str | None = None) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(path), max(4, int(size)))
    if variation:
        try:
            f.set_variation_by_name(variation)
        except Exception:
            pass
    return f


def anton(size: float) -> ImageFont.FreeTypeFont:
    return font(str(paths.ANTON), int(size))


def tiktok(size: float, weight: str = "Bold") -> ImageFont.FreeTypeFont:
    return font(str(paths.TIKTOK), int(size), weight)


def grotesk(size: float, weight: str = "Bold") -> ImageFont.FreeTypeFont:
    return font(str(paths.GROTESK), int(size), weight)


def mono(size: float, weight: str = "Medium") -> ImageFont.FreeTypeFont:
    return font(str(paths.JETBRAINS), int(size), weight)


def fit_font(path, text: str, max_w: float, start: int, variation: str | None = None, min_size: int = 6) -> ImageFont.FreeTypeFont:
    size = int(start)
    while size > min_size:
        f = font(str(path), size, variation)
        if f.getlength(text) <= max_w:
            return f
        size = int(size * 0.96) if size > 40 else size - 1
    return font(str(path), min_size, variation)


def center_text(d: ImageDraw.ImageDraw, width: int, y: float, text: str, f: ImageFont.FreeTypeFont, fill) -> None:
    d.text(((width - d.textlength(text, font=f)) / 2, y), text, font=f, fill=fill)


# ---------------------------------------------------------------------------- hero title layout

@dataclass
class TitleLayout:
    mode: str  # centre | left | right | split | top | front
    size: int  # Anton size in master pixels
    parts: list[dict] = field(default_factory=list)  # [{"text", "x", "y"}] in master pixels (x, y = text origin)
    visible: float = 1.0  # share of the title's ink not covered by the person (average over the shot)
    worst_letter: float = 1.0  # the most-covered letter's visible share
    behind: bool = True

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "TitleLayout":
        return cls(**d)


A = 0.25  # analysis resolution: 480x270
MIN_VISIBLE = 0.78
MIN_LETTER = 0.6


def _part_origin_y(f: ImageFont.FreeTypeFont, text: str, centre_y: float) -> float:
    bb = f.getbbox(text or "A")
    return centre_y - (bb[1] + bb[3]) / 2


def _letters_mask(parts: list[dict], size: int) -> list[np.ndarray]:
    """One mask per letter at analysis resolution."""
    f = anton(size * A)
    out = []
    for p in parts:
        x = p["x"] * A
        for ch in p["text"]:
            if ch == " ":
                x += f.getlength(" ")
                continue
            im = Image.new("L", (int(MW * A), int(MH * A)), 0)
            ImageDraw.Draw(im).text((x, p["y"] * A), ch, font=f, fill=255)
            out.append(np.asarray(im, np.float32) / 255.0)
            x += f.getlength(ch)
    return out


def _score(parts: list[dict], size: int, occ: np.ndarray) -> tuple[float, float, bool]:
    letters = _letters_mask(parts, size)
    if not letters:
        return 0.0, 0.0, False
    ink = sum(m.sum() for m in letters)
    covered = sum((m * occ).sum() for m in letters)
    visible = 1.0 - covered / max(1e-6, ink)
    worst = min(1.0 - (m * occ).sum() / max(1e-6, m.sum()) for m in letters)
    inside = all(m.sum() > 0 for m in letters)
    return float(visible), float(worst), inside


def _fit_size(text: str, max_w: float, max_h: float, start: int = 760) -> int:
    f = fit_font(str(paths.ANTON), text, max_w, start)
    bb = f.getbbox(text)
    size = f.size
    if bb[3] - bb[1] > max_h:
        size = int(size * max_h / (bb[3] - bb[1]))
    return max(8, size)


def layout_title(title: str, occupancy: np.ndarray | None) -> TitleLayout:
    """occupancy: share of the hero frames where each pixel is person (any size; resampled to 480x270)."""
    text = title.upper().strip() or "VELLUM"
    if occupancy is None or float(occupancy.max(initial=0)) < 0.05:
        occ = np.zeros((int(MH * A), int(MW * A)), np.float32)
    else:
        occ = np.asarray(Image.fromarray((np.clip(occupancy, 0, 1) * 255).astype(np.uint8)).resize((int(MW * A), int(MH * A)), Image.BILINEAR), np.float32) / 255.0

    candidates: list[TitleLayout] = []

    def make(mode: str, size: int, parts: list[dict], behind: bool = True):
        if size < 70 and mode != "front":
            return
        candidates.append(TitleLayout(mode=mode, size=int(size), parts=parts, behind=behind))

    # centred, huge
    size = _fit_size(text, MW * 0.88, MH * 0.5)
    f = anton(size)
    tw = f.getlength(text)
    make("centre", size, [{"text": text, "x": (MW - tw) / 2, "y": _part_origin_y(f, text, MH * 0.42)}])

    person = occ > 0.25
    if person.any():
        ys, xs = np.nonzero(person)
        px0, px1 = xs.min() / A, xs.max() / A
        py0 = ys.min() / A
        margin = 70
        # Negative gaps tuck the letters' inner edges behind the person: that's the
        # "standing in front of the title" look. Scoring below keeps it readable.
        for gap in (-60, -25, 34):
            left_w, right_w = px0 - gap - margin, MW - margin - (px1 + gap)
            # beside the person
            if left_w > 200:
                s = _fit_size(text, left_w, MH * 0.62)
                f = anton(s)
                make("left", s, [{"text": text, "x": px0 - gap - f.getlength(text), "y": _part_origin_y(f, text, MH * 0.47)}])
            if right_w > 200:
                s = _fit_size(text, right_w, MH * 0.62)
                f = anton(s)
                make("right", s, [{"text": text, "x": px1 + gap, "y": _part_origin_y(f, text, MH * 0.47)}])
            # split around the person, preferring a word break (NEW | YORK)
            if left_w > 120 and right_w > 120 and len(text.replace(" ", "")) >= 2:
                splits = [i for i, ch in enumerate(text) if ch == " "] or list(range(1, len(text)))
                for i in splits:
                    lt, rt = text[:i].strip(), text[i:].strip()
                    if not lt or not rt:
                        continue
                    s = min(_fit_size(lt, left_w, MH * 0.62), _fit_size(rt, right_w, MH * 0.62))
                    f = anton(s)
                    cy = MH * 0.45
                    make("split", s, [
                        {"text": lt, "x": px0 - gap - f.getlength(lt), "y": _part_origin_y(f, lt, cy)},
                        {"text": rt, "x": px1 + gap, "y": _part_origin_y(f, rt, cy)},
                    ])
        # above the person's head
        if py0 > MH * 0.3:
            s = _fit_size(text, MW * 0.82, py0 - 80)
            f = anton(s)
            make("top", s, [{"text": text, "x": (MW - f.getlength(text)) / 2, "y": _part_origin_y(f, text, py0 / 2 + 10)}])

    best: TitleLayout | None = None
    best_score = -1.0
    for c in candidates:
        c.visible, c.worst_letter, inside = _score(c.parts, c.size, occ)
        if not inside or c.visible < MIN_VISIBLE or c.worst_letter < MIN_LETTER:
            continue
        score = c.size * (0.5 + 0.5 * c.visible ** 2) * (1.06 if c.mode == "split" and " " in text else 1.0)
        if 0.86 <= c.visible < 0.995:
            score *= 1.12  # a little overlap reads as depth: the person in front of the letters
        if score > best_score:
            best, best_score = c, score
    if best is not None:
        return best
    # nothing keeps the letters clear: put the title in front of the person
    size = _fit_size(text, MW * 0.88, MH * 0.5)
    f = anton(size)
    tw = f.getlength(text)
    return TitleLayout(mode="front", size=size, parts=[{"text": text, "x": (MW - tw) / 2, "y": _part_origin_y(f, text, MH * 0.42)}],
                       visible=1.0, worst_letter=1.0, behind=False)


def draw_title(layer: ImageDraw.ImageDraw, layout: TitleLayout, scale: float, letters: int, fill) -> None:
    """Draw the first `letters` letters of the title (typed on), across all parts in reading order."""
    f = anton(layout.size * scale)
    left = letters
    for p in layout.parts:
        if left <= 0:
            break
        shown = p["text"][: max(0, left)]
        layer.text((p["x"] * scale, p["y"] * scale), shown, font=f, fill=fill)
        left -= len(p["text"].replace(" ", "")) + p["text"].count(" ")
