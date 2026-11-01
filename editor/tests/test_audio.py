import pytest

from vellum_editor.audio import analyze_song
from vellum_editor.testmedia import make_song


@pytest.mark.parametrize("bpm,lead,intro", [(120, 0.25, 16), (128, 0.6, 24), (96, 0.1, 16), (140, 1.3, 32), (87, 0.4, 8)])
def test_bpm_drop_and_grid(tmp_path, bpm, lead, intro):
    truth = make_song(tmp_path / "song.wav", bpm=bpm, lead_in=lead, intro_beats=intro, total=80)
    a = analyze_song(str(truth.path))
    assert abs(a.bpm - bpm) < 0.3, a.bpm
    # the drop lands on the right beat, within a few milliseconds
    assert abs(a.drop - truth.drop) < 0.012, (a.drop, truth.drop)
    # the grid stays locked to the music a minute after the drop (one frame is 41.7 ms)
    k = round(60 / a.beat)
    assert abs((a.drop + k * a.beat) - (truth.drop + k * 60 / bpm)) < 0.012


def test_nudges_keep_the_grid_on_the_drop(tmp_path):
    truth = make_song(tmp_path / "song.wav", bpm=120, total=40)
    a = analyze_song(str(truth.path))
    b = a.with_bpm(60.0)
    assert b.drop == a.drop and abs(b.beat - 1.0) < 1e-9
    c = a.with_drop(a.drop + a.beat)
    assert abs(c.drop - (a.drop + a.beat)) < 1e-9


def test_drop_search_can_start_later(tmp_path):
    truth = make_song(tmp_path / "song.wav", bpm=120, total=40)
    a = analyze_song(str(truth.path), search_from=truth.drop + 4.0)
    assert a.drop >= truth.drop + 4.0 - 1e-6  # no jump after that point: falls back to a grid beat after it
