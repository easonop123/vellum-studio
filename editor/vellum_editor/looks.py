"""Colour: HDR to SDR, optional LUT for log footage, the raw intro look, and the grades.

The Darkroom grade is the house grade from the reference scripts:
contrast 1.10, saturation 1.14, gamma 0.97, teal shadows / warm highlights,
lifted blacks; then bloom, vignette and grain are added per frame in Python.
"""
from __future__ import annotations

from dataclasses import dataclass

from .ffmpeg import has_filter
from .probe import ClipInfo

RAW_LOOK = "eq=saturation=0.62:contrast=0.82:brightness=0.035"


@dataclass(frozen=True)
class Look:
    key: str
    name: str
    grade: str  # ffmpeg filter chain
    night: str  # variant for orange street-light night shots: pull orange down, never add more
    bloom: float  # highlight bloom strength (0..1)
    vignette: float  # vignette depth
    grain: float  # grain amplitude in 0..255 levels


DARKROOM_GRADE = (
    "eq=contrast=1.10:saturation=1.14:gamma=0.97,"
    "colorbalance=rs=-0.07:gs=-0.01:bs=0.09:rm=-0.01:gm=0:bm=0.03:rh=0.09:gh=0.03:bh=-0.07,"
    "curves=all='0/0.035 0.25/0.22 0.75/0.79 1/0.97'"
)
# Night version: same contrast and lifted blacks, but highlights pushed cool and
# oranges desaturated, because sodium street light is already very orange.
DARKROOM_NIGHT = (
    "eq=contrast=1.12:saturation=1.02:gamma=0.97,"
    "colorbalance=rs=-0.07:gs=-0.01:bs=0.10:rm=-0.04:gm=0:bm=0.05:rh=-0.03:gh=0.0:bh=0.04,"
    "selectivecolor=reds='0 0.04 0.10 0':yellows='0.06 0.02 0.18 0',"
    "curves=all='0/0.035 0.25/0.21 0.75/0.79 1/0.97'"
)

LOOKS: dict[str, Look] = {
    "darkroom": Look("darkroom", "Darkroom", DARKROOM_GRADE, DARKROOM_NIGHT, bloom=0.45, vignette=0.38, grain=9.0),
    "warm_film": Look(
        "warm_film",
        "Warm Film",
        "eq=contrast=1.05:saturation=0.96:gamma=1.0,"
        "colorbalance=rs=0.02:gs=0.0:bs=-0.03:rm=0.04:gm=0.01:bm=-0.03:rh=0.06:gh=0.03:bh=-0.07,"
        "curves=all='0/0.06 0.3/0.30 0.7/0.73 1/0.94'",
        "eq=contrast=1.06:saturation=0.9:gamma=1.0,"
        "colorbalance=rs=-0.02:gs=0.0:bs=0.04:rm=0.0:gm=0:bm=0.02:rh=-0.02:gh=0.0:bh=0.02,"
        "selectivecolor=yellows='0.04 0.02 0.12 0',"
        "curves=all='0/0.06 0.3/0.30 0.7/0.73 1/0.94'",
        bloom=0.35,
        vignette=0.30,
        grain=13.0,
    ),
    "neon_night": Look(
        "neon_night",
        "Neon Night",
        "eq=contrast=1.14:saturation=1.28:gamma=0.95,"
        "colorbalance=rs=-0.03:gs=-0.06:bs=0.12:rm=0.06:gm=-0.05:bm=0.08:rh=0.03:gh=-0.03:bh=0.04,"
        "curves=all='0/0.02 0.25/0.19 0.75/0.80 1/0.98'",
        "eq=contrast=1.14:saturation=1.12:gamma=0.95,"
        "colorbalance=rs=-0.05:gs=-0.06:bs=0.14:rm=0.03:gm=-0.05:bm=0.10:rh=-0.03:gh=-0.03:bh=0.06,"
        "selectivecolor=reds='0 0.05 0.12 0':yellows='0.08 0.03 0.22 0',"
        "curves=all='0/0.02 0.25/0.19 0.75/0.80 1/0.98'",
        bloom=0.6,
        vignette=0.42,
        grain=8.0,
    ),
    "clean": Look(
        "clean",
        "Clean",
        "eq=contrast=1.05:saturation=1.06:gamma=0.99",
        "eq=contrast=1.05:saturation=0.98:gamma=0.99,selectivecolor=yellows='0.04 0.02 0.10 0'",
        bloom=0.15,
        vignette=0.18,
        grain=0.0,
    ),
}
DEFAULT_LOOK = "darkroom"


def get_look(key: str) -> Look:
    return LOOKS.get(key, LOOKS[DEFAULT_LOOK])


def tonemap_filter(info: ClipInfo) -> str:
    """HDR (iPhone HLG / Dolby Vision 8.4, PQ) to normal SDR Rec.709. Empty for SDR clips."""
    if info.kind != "video" or not (info.hdr or info.dolby_vision):
        return ""
    tin = info.transfer or ("arib-std-b67" if info.dolby_vision else "smpte2084")
    pin = info.primaries or "bt2020"
    if has_filter("zscale") and has_filter("tonemap"):
        return (
            f"zscale=tin={tin}:pin={pin}:min=bt2020nc:t=linear:npl=100,format=gbrpf32le,"
            "zscale=p=bt709,tonemap=tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p"
        )
    # Rough fallback for ffmpeg builds without zscale: HDR played as SDR looks flat and washed out.
    return "format=yuv420p,eq=contrast=1.22:saturation=1.3:gamma=0.88"


def lut_filter(info: ClipInfo, lut_path: str | None, apply_to: str) -> str:
    """Optional .cube LUT for log footage (e.g. DJI D-Log M). apply_to: 'off' | 'dji' | 'all'."""
    if not lut_path or apply_to == "off" or info.kind != "video":
        return ""
    if apply_to == "dji" and not info.is_dji:
        return ""
    escaped = lut_path.replace("\\", "/").replace(":", "\\:").replace("'", "\\'")
    return f"lut3d=file='{escaped}'"


def grade_filter(look: Look, raw: bool, night_orange: bool) -> str:
    if raw:
        return RAW_LOOK
    return look.night if night_orange else look.grade
