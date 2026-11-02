"""The transitions and looks ported from the reference scripts, drawn from known solid-colour shots."""
import json

import numpy as np
import pytest
from PIL import Image

from vellum_editor.plan import EditPlan, Segment, Shot
from vellum_editor.render import Renderer

SCALE = 0.1  # 192 x 108
COLOURS = {"A": (200, 40, 40), "B": (40, 40, 200), "C": (40, 190, 40), "D": (90, 40, 160)}


def _frame(name, w, h):
    if name == "E":  # mostly blue with a yellow block: the colour pop keeps the yellow
        a = np.zeros((h, w, 3), np.uint8)
        a[:] = (40, 60, 200)
        a[: h // 2, : w // 3] = (235, 200, 20)
        return Image.fromarray(a)
    return Image.new("RGB", (w, h), COLOURS[name])


def make_renderer(work, cuts):
    """cuts: (clip letter, k0, k1, fx). Beat 0.5 s and the drop 2 s in, so frame(k) = 48 + 12k."""
    segs = [Segment(k0, k1, shot=Shot(f"{c}.mov", 0.0), fx=fx) for c, k0, k1, fx in cuts]
    clips = {f"{c}.mov": {"info": {"duration": 10.0}} for c, *_ in cuts}
    end_k = float(cuts[-1][2])
    plan = EditPlan(title="Tokyo", length="short", look="clean", seed=1,
                    song={"path": "", "bpm": 120.0, "beat": 0.5, "drop": 2.0, "offset": 0.0, "duration": 30.0},
                    end_k=end_k, total_k=end_k + 4, clips=clips, rejected=[], segments=segs, whites=[], blooms=[])
    plan.assign_ids()
    for seg in segs:
        d = work / "frames" / seg.shot.id
        d.mkdir(parents=True)
        _frame(seg.shot.clip[0], 192, 108).save(d / "0001.jpg", quality=95)
        (d / "meta.json").write_text(json.dumps({"w": 192, "h": 108, "map": [0] * 40}))
    return Renderer(plan, work, SCALE)


@pytest.fixture(scope="module")
def renderer(tmp_path_factory):
    return make_renderer(tmp_path_factory.mktemp("fx1"), [
        ("A", -4, 0, {}), ("B", 0, 2, {}), ("C", 2, 4, {"slit": 1}), ("D", 4, 6, {"shrink": 1}), ("E", 6, 8, {"cpop": 1}),
    ])


@pytest.fixture(scope="module")
def renderer2(tmp_path_factory):
    return make_renderer(tmp_path_factory.mktemp("fx2"), [
        ("A", -4, 0, {}), ("B", 0, 2, {}), ("C", 2, 4, {"strips": 1}), ("D", 4, 6, {"burn": 1}),
    ])


def px(im, x, y):
    return np.asarray(im)[y, x].astype(int)


def dominant(p):
    return "rgb"[int(np.argmax(p))]


def test_slit_opens_the_new_shot_from_the_centre(renderer):
    first = renderer.render(72)  # first frame of C: a narrow slit of green over the blue shot before it
    assert dominant(px(first, 96, 54)) == "g"
    assert dominant(px(first, 20, 54)) == "b" and dominant(px(first, 170, 54)) == "b"
    white_cols = [x for x in range(192) if px(first, x, 54).min() > 200]
    assert white_cols and all(70 < x < 122 for x in white_cols)  # the thin white slit edges
    assert dominant(px(renderer.render(76), 20, 54)) == "g"  # fully open after 5 frames


def test_polaroid_flies_off_to_the_right(renderer):
    assert dominant(px(renderer.render(96), 96, 54)) == "g"  # the last shot, barely shrunk
    mid = renderer.render(99)
    assert tuple(px(mid, 5, 54)) != tuple(px(renderer.render(96), 5, 54))
    assert px(mid, 5, 54)[2] > px(mid, 5, 54)[1]  # the new (purple) shot shows on the left
    bone = (np.asarray(mid).min(axis=2) > 200).sum()
    assert bone > 20  # the white print border
    gone = renderer.render(103)  # flown off by the 8th frame
    assert dominant(px(gone, 96, 54)) != "g" and dominant(px(gone, 180, 54)) != "g"


def test_colour_pop_keeps_one_colour(renderer):
    blue, yellow = (150, 80), (25, 20)
    before = renderer.render(121)  # the pop starts on the 3rd frame
    assert np.ptp(px(before, *blue)) > 80
    popped = renderer.render(123)
    assert np.ptp(px(popped, *blue)) < 25  # blue drained to grey
    y = px(popped, *yellow)
    assert y[0] > 150 and y[1] > 120 and y[2] < 90  # yellow kept


def test_strips_slide_in_from_alternate_sides(renderer2):
    first = renderer2.render(72)  # top strip enters from the right, the others haven't started
    assert dominant(px(first, 185, 18)) == "g" and dominant(px(first, 96, 54)) == "b" and dominant(px(first, 96, 90)) == "b"
    mid = renderer2.render(74)
    assert dominant(px(mid, 96, 18)) == "g"
    assert dominant(px(mid, 60, 54)) == "g" and dominant(px(mid, 170, 54)) == "b"  # middle comes from the left
    assert dominant(px(mid, 170, 90)) == "g" and dominant(px(mid, 60, 90)) == "b"  # bottom from the right
    done = renderer2.render(77)
    assert all(dominant(px(done, 96, y)) == "g" for y in (18, 54, 90))


def test_light_leak_burns_across_the_cut(renderer2):
    red = lambda f: float(np.asarray(renderer2.render(f))[..., 0].mean())
    assert red(94) - red(88) > 20  # the end of the shot before the cut starts burning
    assert red(98) - red(104) > 30  # and the new shot comes in through the leak
