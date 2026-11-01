"""Shared test media: a messy folder of fake clips and a synthetic song with a known BPM and drop."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from vellum_editor.testmedia import make_song, make_test_set

SONG_BPM = 120.0
SONG_LEAD_IN = 0.25
SONG_INTRO_BEATS = 16  # drop at 0.25 + 16 * 0.5 = 8.25 s


@pytest.fixture(scope="session")
def media(tmp_path_factory):
    root = tmp_path_factory.mktemp("media")
    clips = root / "clips"
    made = make_test_set(clips, count=26)
    truth = make_song(root / "song.wav", bpm=SONG_BPM, lead_in=SONG_LEAD_IN, intro_beats=SONG_INTRO_BEATS, total=75)
    return {"clips": clips, "made": made, "song": truth, "root": root}


@pytest.fixture(autouse=True, scope="session")
def _no_masks_by_default():
    # Masks are tested on their own; the end-to-end renders skip the model to stay fast.
    old = os.environ.get("VELLUM_NO_MASKS")
    os.environ["VELLUM_NO_MASKS"] = "1"
    yield
    if old is None:
        os.environ.pop("VELLUM_NO_MASKS", None)
    else:
        os.environ["VELLUM_NO_MASKS"] = old


def clip_path(media, name: str) -> Path:
    return media["clips"] / name
