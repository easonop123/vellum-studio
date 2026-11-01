"""The hero title stays readable whatever the person does; the sound effects are sane."""
import numpy as np
import pytest

from vellum_editor import sfx
from vellum_editor.text import MIN_LETTER, MIN_VISIBLE, layout_title

H, W = 270, 480


def person(cx, width, top=0.12):
    yy, xx = np.mgrid[0:H, 0:W]
    body = (np.abs(xx - cx * W) < width * W / 2) & (yy > top * H)
    head = ((xx - cx * W) ** 2 + (yy - top * H) ** 2) < (width * W * 0.45) ** 2
    return (body | head).astype(np.float32)


@pytest.mark.parametrize("title", ["TOKYO", "NEW YORK", "ITALIA", "BALI", "QUEENSTOWN"])
@pytest.mark.parametrize("where", [(0.5, 0.3), (0.5, 0.16), (0.3, 0.2), (0.72, 0.22), (0.5, 0.45)])
def test_title_behind_person_stays_readable(title, where):
    layout = layout_title(title, person(*where))
    if layout.behind:
        assert layout.visible >= MIN_VISIBLE and layout.worst_letter >= MIN_LETTER
    joined = "".join(p["text"] for p in layout.parts).replace(" ", "")
    assert joined == title.replace(" ", "")


def test_title_splits_around_a_centred_person():
    layout = layout_title("NEW YORK", person(0.5, 0.25))
    assert layout.mode == "split" and [p["text"] for p in layout.parts] == ["NEW", "YORK"]


def test_title_goes_in_front_when_the_person_fills_the_frame():
    layout = layout_title("TOKYO", person(0.5, 0.85, top=0.02))
    assert layout.mode == "front" and not layout.behind


def test_title_is_big_and_centred_with_nobody_there():
    layout = layout_title("TOKYO", None)
    assert layout.mode == "centre" and layout.size > 500


def test_sound_bank_is_complete_and_clean():
    bank = sfx.builtin_bank()
    assert set(bank) == set(sfx.NAMES)
    for name, x in bank.items():
        assert x.ndim == 2 and x.shape[1] == 2, name
        assert np.isfinite(x).all(), name
        assert 0.8 < np.abs(x).max() <= 0.91, name
    assert len(bank["riser"]) / sfx.SR > 2.0  # riser covers the 2 s before the drop


def test_custom_sound_folder_overrides_builtins(tmp_path):
    from vellum_editor.ffmpeg import write_wav

    tone = np.sin(2 * np.pi * 440 * np.arange(4800) / 48000).astype(np.float32) * 0.5
    write_wav(tmp_path / "Shutter1.wav", np.stack([tone, tone], 1))
    bank = sfx.load_bank(str(tmp_path))
    assert len(bank["shutter1"]) == 4800
    assert len(bank["shutter2"]) == len(sfx.builtin_bank()["shutter2"])
