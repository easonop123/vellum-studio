"""Work out what each customer file actually is: size, rotation, fps, HDR, camera."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from fractions import Fraction
from pathlib import Path

from .ffmpeg import FFmpegError, probe_json

VIDEO_EXT = {".mov", ".mp4", ".m4v", ".avi", ".mkv", ".mts", ".m2ts", ".3gp", ".webm"}
PHOTO_EXT = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp", ".tif", ".tiff"}
# GoPro/DJI side-car proxies and thumbnails duplicate the real clips.
SKIP_EXT = {".lrv", ".thm", ".srt", ".aae", ".xmp", ".lrf"}


class ClipError(Exception):
    """A file we can't use. The message is shown in review.html."""


@dataclass
class ClipInfo:
    path: str
    name: str
    kind: str  # "video" | "photo"
    width: int  # as displayed (after rotation)
    height: int
    fps: float
    duration: float
    rotation: int = 0
    codec: str = ""
    pix_fmt: str = ""
    transfer: str = ""
    primaries: str = ""
    hdr: str = ""  # "", "pq" or "hlg"
    dolby_vision: bool = False
    is_dji: bool = False
    is_gopro: bool = False
    has_audio: bool = False
    bit_depth: int = 8
    extra: dict = field(default_factory=dict)

    @property
    def vertical(self) -> bool:
        return self.height > self.width

    @property
    def high_fps(self) -> bool:
        """Real slow motion is possible (50+ fps)."""
        return self.kind == "video" and self.fps >= 47.0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ClipInfo":
        return cls(**data)


def list_media(folder: str | Path) -> list[Path]:
    """Top-level video and photo files in the folder, in name order. Ignores our own output folder."""
    folder = Path(folder)
    out = []
    for p in sorted(folder.iterdir(), key=lambda x: x.name.lower()):
        if p.name.startswith(".") or not p.is_file():
            continue
        ext = p.suffix.lower()
        if ext in SKIP_EXT:
            continue
        if ext in VIDEO_EXT or ext in PHOTO_EXT:
            out.append(p)
    return out


def _rate(text: str | None) -> float:
    if not text or text in ("0/0", "0"):
        return 0.0
    try:
        return float(Fraction(text))
    except (ValueError, ZeroDivisionError):
        return 0.0


def _rotation(stream: dict) -> int:
    for side in stream.get("side_data_list", []) or []:
        if "rotation" in side:
            try:
                return int(round(float(side["rotation"])))
            except (TypeError, ValueError):
                pass
    tag = (stream.get("tags") or {}).get("rotate")
    if tag:
        try:
            return -int(tag)  # old-style tag is clockwise; display matrix is counter-clockwise
        except ValueError:
            pass
    return 0


def _all_tags(data: dict) -> str:
    parts = []
    for tags in [data.get("format", {}).get("tags", {})] + [s.get("tags", {}) for s in data.get("streams", [])]:
        for k, v in (tags or {}).items():
            parts.append(f"{k}={v}")
    return " ".join(parts).lower()


def probe_photo(path: Path) -> ClipInfo:
    from PIL import Image, ImageOps

    if path.suffix.lower() in (".heic", ".heif"):
        try:
            import pillow_heif

            pillow_heif.register_heif_opener()
        except ImportError as exc:  # pragma: no cover - only without pillow-heif
            raise ClipError("can't read HEIC photos on this machine") from exc
    try:
        with Image.open(path) as im:
            im = ImageOps.exif_transpose(im)
            w, h = im.size
    except Exception as exc:
        raise ClipError("photo is damaged or not a real image") from exc
    if w < 64 or h < 64:
        raise ClipError("photo is too small")
    return ClipInfo(path=str(path), name=path.name, kind="photo", width=w, height=h, fps=0.0, duration=6.0)


def probe(path: str | Path) -> ClipInfo:
    path = Path(path)
    ext = path.suffix.lower()
    if ext in PHOTO_EXT:
        return probe_photo(path)
    if path.stat().st_size < 1024:
        raise ClipError("file is empty or broken")
    try:
        data = probe_json(path)
    except FFmpegError as exc:
        raise ClipError("file is damaged or not a video ffmpeg can read") from exc
    except Exception as exc:  # timeouts and the like
        raise ClipError(f"couldn't read file ({exc.__class__.__name__})") from exc

    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video" and not (s.get("disposition") or {}).get("attached_pic")), None)
    if video is None:
        raise ClipError("no video in this file")
    width, height = int(video.get("width") or 0), int(video.get("height") or 0)
    if width < 32 or height < 32:
        raise ClipError("video has no picture size (damaged?)")
    rotation = _rotation(video)
    if abs(rotation) % 180 == 90:
        width, height = height, width
    fps = _rate(video.get("avg_frame_rate")) or _rate(video.get("r_frame_rate"))
    if fps <= 1 or fps > 1000:
        fps = _rate(video.get("r_frame_rate"))
    if fps <= 1 or fps > 1000:
        raise ClipError("video has no usable frame rate (damaged?)")
    duration = 0.0
    for candidate in (video.get("duration"), data.get("format", {}).get("duration")):
        try:
            duration = float(candidate)
            if duration > 0:
                break
        except (TypeError, ValueError):
            continue
    if duration <= 0.2:
        raise ClipError("clip is too short or damaged")

    transfer = video.get("color_transfer", "") or ""
    hdr = "pq" if transfer == "smpte2084" else "hlg" if transfer == "arib-std-b67" else ""
    side_types = " ".join(str(sd.get("side_data_type", "")) for sd in video.get("side_data_list", []) or []).lower()
    codec_tag = str(video.get("codec_tag_string", "")).lower()
    dolby = "dovi" in side_types or "dolby vision" in side_types or codec_tag in ("dvh1", "dvhe", "dva1", "dvav")
    tags = _all_tags(data)
    pix_fmt = video.get("pix_fmt", "") or ""
    depth = 10 if ("10" in pix_fmt or "12" in pix_fmt) else 8
    return ClipInfo(
        path=str(path),
        name=path.name,
        kind="video",
        width=width,
        height=height,
        fps=round(fps, 3),
        duration=duration,
        rotation=rotation,
        codec=video.get("codec_name", "") or "",
        pix_fmt=pix_fmt,
        transfer=transfer,
        primaries=video.get("color_primaries", "") or "",
        hdr=hdr,
        dolby_vision=dolby,
        is_dji="dji" in tags,
        is_gopro="gopro" in tags,
        has_audio=any(s.get("codec_type") == "audio" for s in streams),
        bit_depth=depth,
    )
