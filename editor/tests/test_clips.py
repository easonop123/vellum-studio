"""Probing and judging the messy test folder."""
import pytest

from vellum_editor.analyze import analyse_folder
from vellum_editor.probe import ClipError, probe


def test_probe_handles_rotation_hdr_fps_and_photos(media):
    clips = media["clips"]
    rotated = probe(clips / "IMG_9001.MOV")
    assert (rotated.width, rotated.height) == (180, 320) and abs(rotated.rotation) == 90 and rotated.vertical
    hdr = probe(clips / "IMG_9002.MOV")
    assert hdr.hdr == "hlg" and hdr.bit_depth in (8, 10)
    fast = [probe(clips / n) for n in media["made"]["high_fps"]]
    assert fast and all(c.high_fps for c in fast)
    assert {round(c.fps) for c in fast} >= {60, 120}
    photo = probe(clips / "IMG_9007.JPG")
    assert photo.kind == "photo" and photo.width == 480


@pytest.mark.parametrize("name", ["IMG_9005.MOV", "IMG_9006.MP4"])
def test_corrupt_files_raise_a_readable_error(media, name):
    with pytest.raises(ClipError):
        probe(media["clips"] / name)


def test_junk_is_thrown_out_and_good_clips_kept(media):
    res = {a.name: a for a in analyse_folder(media["clips"], use_masks=False)}
    made = media["made"]
    assert not res["IMG_9003.MOV"].usable and res["IMG_9003.MOV"].reason == "too dark"
    assert not res["IMG_9004.MOV"].usable and res["IMG_9004.MOV"].reason == "blurry"
    for name in made["corrupt"]:
        assert not res[name].usable and "damaged" in res[name].reason
    for name in made["good"] + made["rotated"] + made["hdr"] + made["photo"]:
        assert res[name].usable, (name, res[name].reason)
        assert 0 < res[name].score <= 1
        assert 0 <= res[name].best_start < res[name].info.duration
