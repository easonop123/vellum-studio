"""Where bundled things live, both when running from source and inside the .app."""
from __future__ import annotations

import os
import platform
import shutil
import sys
from pathlib import Path


def resource_root() -> Path:
    # PyInstaller unpacks data next to the executable and sets sys._MEIPASS.
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        return Path(bundle) / "vellum_editor"
    return Path(__file__).resolve().parent


ASSETS = resource_root() / "assets"
FONTS = ASSETS / "fonts"
MODELS = ASSETS / "models"
BIN = ASSETS / "bin"

ANTON = FONTS / "Anton.ttf"
TIKTOK = FONTS / "TikTokSans.ttf"
GROTESK = FONTS / "SpaceGrotesk.ttf"
JETBRAINS = FONTS / "JetBrainsMono.ttf"
SERIF_ITALIC = FONTS / "InstrumentSerif-Italic.ttf"
HUMAN_SEG_MODEL = MODELS / "u2net_human_seg.onnx"


def _bundled(name: str) -> str | None:
    exe = BIN / (name + (".exe" if platform.system() == "Windows" else ""))
    if exe.exists():
        return str(exe)
    return None


def ffmpeg_path() -> str:
    """The bundled static ffmpeg first, then whatever is on PATH (dev machines and CI)."""
    found = os.environ.get("VELLUM_FFMPEG") or _bundled("ffmpeg") or shutil.which("ffmpeg")
    if not found:
        raise FileNotFoundError("ffmpeg not found")
    return found


def ffprobe_path() -> str:
    found = os.environ.get("VELLUM_FFPROBE") or _bundled("ffprobe") or shutil.which("ffprobe")
    if not found:
        raise FileNotFoundError("ffprobe not found")
    return found


def app_support_dir() -> Path:
    """Per-user settings folder."""
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    path = base / "Vellum Editor"
    path.mkdir(parents=True, exist_ok=True)
    return path
