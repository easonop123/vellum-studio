"""App settings saved between runs (in ~/Library/Application Support/Vellum Editor/settings.json)."""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields

from .paths import app_support_dir


@dataclass
class AppSettings:
    sfx_folder: str = ""  # your own sound effects (click.wav, shutter1.wav, ...)
    lut_path: str = ""  # .cube LUT for log footage (e.g. DJI D-Log M)
    lut_apply: str = "off"  # off | dji | all
    use_masks: bool = True  # person detection (title behind the person, cut-outs)
    quality: str = "best"  # best (crf 17) | smaller (crf 21)
    all_cores: bool = True
    last_look: str = "darkroom"
    last_length: str = "short"
    strict: bool = False
    texture: bool = True  # old-film texture (grain, faded blacks)

    @property
    def crf(self) -> int:
        return 17 if self.quality == "best" else 21

    @property
    def workers(self) -> int:
        n = os.cpu_count() or 2
        return n if self.all_cores else max(1, n - 1)


def path():
    return app_support_dir() / "settings.json"


def load() -> AppSettings:
    try:
        data = json.loads(path().read_text())
        known = {f.name for f in fields(AppSettings)}
        return AppSettings(**{k: v for k, v in data.items() if k in known})
    except Exception:
        return AppSettings()


def save(s: AppSettings) -> None:
    try:
        path().write_text(json.dumps(asdict(s), indent=2))
    except OSError:
        pass
