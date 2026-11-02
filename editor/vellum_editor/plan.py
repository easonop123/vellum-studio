"""The edit plan: every segment, which clip and moment it uses, and its effects.

Saved next to the outputs as edit-plan.json so an edit can be re-rendered
after small changes (swap a shot, nudge the drop) without re-planning.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

FPS = 24
W, H = 1920, 1080  # the 16:9 master; everything else is scaled from these coordinates

# Transitions that keep the previous shot on screen (playing on) while the new one comes in:
# the slit reveal (v6) and the polaroid fly-off (v7/v8). Frames past the previous cut's end.
PEEK = {"slit": 6, "shrink": 8}


def peek_frames(seg_after: "Segment | None") -> int:
    """How many frames past its own end a shot stays on screen because the next cut transitions over it."""
    if seg_after is None:
        return 0
    return max((n for key, n in PEEK.items() if seg_after.fx.get(key)), default=0)


@dataclass
class Shot:
    clip: str  # file name, key into EditPlan.clips
    ss: float  # source start, seconds
    speed: float = 1.0
    ramp: list[float] | None = None  # [start speed, end speed] for speed ramps
    box: tuple[int, int] = (W, H)  # target size in master coordinates
    fx: float = 0.5  # crop focus, 0..1
    fy: float = 0.45
    raw: bool = False  # ungraded "straight off the phone" look
    reuse: bool = False  # a second, different moment of a clip that's already in the edit
    at: float = 0.0  # for sub-shots: beats after the segment start when it appears
    id: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["box"] = list(self.box)
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "Shot":
        data = dict(data)
        data["box"] = tuple(data.get("box", (W, H)))
        return cls(**data)


@dataclass
class Segment:
    k0: float
    k1: float
    kind: str = "shot"  # shot | grid9 | tri | film | tmask | spaced | strobe
    shot: Shot | None = None
    subs: list[Shot] = field(default_factory=list)
    fx: dict = field(default_factory=dict)
    big: str | None = None  # name of the big effect, if this is one
    label: str = ""  # file-name label on raw intro clips
    id: str = ""

    def all_shots(self) -> list[Shot]:
        return ([self.shot] if self.shot else []) + list(self.subs)

    def to_dict(self) -> dict:
        return {
            "k0": self.k0,
            "k1": self.k1,
            "kind": self.kind,
            "shot": self.shot.to_dict() if self.shot else None,
            "subs": [s.to_dict() for s in self.subs],
            "fx": self.fx,
            "big": self.big,
            "label": self.label,
            "id": self.id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Segment":
        return cls(
            k0=data["k0"],
            k1=data["k1"],
            kind=data.get("kind", "shot"),
            shot=Shot.from_dict(data["shot"]) if data.get("shot") else None,
            subs=[Shot.from_dict(s) for s in data.get("subs", [])],
            fx=data.get("fx", {}),
            big=data.get("big"),
            label=data.get("label", ""),
            id=data.get("id", ""),
        )


@dataclass
class EditPlan:
    title: str
    length: str  # "short" | "long"
    look: str
    seed: int
    song: dict  # path, bpm, beat (grid beat), drop (song time), offset (song time at edit start), duration
    end_k: float  # last beat of the edit before the end card
    total_k: float  # end of the end card
    clips: dict[str, dict]  # name -> ClipAnalysis.to_dict()
    rejected: list[dict]
    segments: list[Segment]
    whites: list[float] = field(default_factory=list)  # beats with a white flash frame
    blooms: list[float] = field(default_factory=list)  # beats with a bloom swell
    settings: dict = field(default_factory=dict)
    title_layout: dict | None = None
    notes: list[str] = field(default_factory=list)
    version: int = 1

    # ---- timing (cuts land on frame(k) = round((DROP + k*BEAT) * 24)) ----
    @property
    def beat(self) -> float:
        return float(self.song["beat"])

    @property
    def drop_edit(self) -> float:
        """Seconds from the start of the edit to the drop."""
        return float(self.song["drop"]) - float(self.song["offset"])

    def F(self, k: float) -> int:
        return max(0, int(round((self.drop_edit + k * self.beat) * FPS)))

    @property
    def total_frames(self) -> int:
        return self.F(self.total_k)

    @property
    def end_frame(self) -> int:
        return self.F(self.end_k)

    def frames_of(self, seg: Segment) -> tuple[int, int]:
        f0 = 0 if seg is self.segments[0] else self.F(seg.k0)
        return f0, self.F(seg.k1)

    def segment_at(self, frame: int) -> Segment | None:
        for seg in self.segments:
            f0, f1 = self.frames_of(seg)
            if f0 <= frame < f1:
                return seg
        return None

    def big_effects(self) -> list[str]:
        return [s.big for s in self.segments if s.big]

    def assign_ids(self) -> None:
        n = 0
        for i, seg in enumerate(self.segments):
            seg.id = f"s{i:02d}"
            for shot in seg.all_shots():
                shot.id = f"u{n:03d}"
                n += 1

    # ---- io ----
    def to_dict(self) -> dict:
        d = {k: v for k, v in asdict(self).items() if k != "segments"}
        d["segments"] = [s.to_dict() for s in self.segments]
        return d

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=1))

    @classmethod
    def from_dict(cls, data: dict) -> "EditPlan":
        data = dict(data)
        data["segments"] = [Segment.from_dict(s) for s in data["segments"]]
        return cls(**data)

    @classmethod
    def load(cls, path: str | Path) -> "EditPlan":
        return cls.from_dict(json.loads(Path(path).read_text()))
