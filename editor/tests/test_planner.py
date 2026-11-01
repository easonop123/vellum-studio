"""House-style rules the planner must always keep."""
from collections import defaultdict

import pytest

from vellum_editor.analyze import analyse_folder
from vellum_editor.audio import analyze_song
from vellum_editor.planner import make_plan


@pytest.fixture(scope="module")
def analyses(media):
    return analyse_folder(media["clips"], use_masks=False)


@pytest.fixture(scope="module")
def song(media):
    return analyze_song(str(media["song"].path))


def footage_overlaps(plan):
    """(clip, a, b) ranges actually used; returns pairs that overlap."""
    ranges = defaultdict(list)
    for seg in plan.segments:
        f0, f1 = plan.frames_of(seg)
        for sh in seg.all_shots():
            if seg.fx.get("continues") and sh is seg.shot:
                continue
            frames = f1 - f0
            speed = max(sh.ramp) if sh.ramp else sh.speed
            ranges[sh.clip].append((sh.ss, sh.ss + frames * speed / 24))
    bad = []
    for clip, rs in ranges.items():
        rs.sort()
        for (a0, a1), (b0, b1) in zip(rs, rs[1:]):
            if b0 < a1 - 1e-6:
                bad.append((clip, (a0, a1), (b0, b1)))
    return bad


@pytest.mark.parametrize("length", ["short", "long"])
@pytest.mark.parametrize("title", ["Tokyo", "New York", "Bali 2026"])
def test_structure_and_rules(analyses, song, length, title):
    plan = make_plan(analyses, song, title=title, length=length, masks_ok=False)
    limit = 30 if length == "short" else 60
    assert plan.total_frames <= limit * 24
    segs = plan.segments
    # intro: raw camera roll with file-name labels, 4-8 clips, ending on the drop
    intro = [s for s in segs if s.k1 <= 0]
    assert 4 <= len(intro) <= 8 and all(s.fx.get("raw") and s.label for s in intro)
    assert intro[-1].fx.get("prebloom") and intro[-1].k1 == 0
    # drop: hero on beat 0, white flash on the drop
    hero = next(s for s in segs if s.fx.get("hero"))
    assert hero.k0 == 0 and 0.0 in plan.whites
    # ending + end card
    assert segs[-1].fx.get("ending") and segs[-1].k1 == plan.end_k and plan.total_k == plan.end_k + 4
    # at most two big effects
    assert len(plan.big_effects()) <= 2
    # cuts are on the beat grid (8ths and quarter-beat bursts only)
    for s in segs:
        assert abs(s.k0 * 4 - round(s.k0 * 4)) < 1e-9
        assert s.k1 > s.k0
    # contiguous timeline
    for a, b in zip(segs, segs[1:]):
        assert a.k1 == b.k0


def test_best_clip_on_the_drop_and_second_best_at_the_climax(analyses, song):
    plan = make_plan(analyses, song, title="Tokyo", length="short", masks_ok=False)
    usable = sorted((a for a in analyses if a.usable and a.info.kind == "video"), key=lambda a: -a.score)
    hero = next(s for s in plan.segments if s.fx.get("hero"))
    climax = next(s for s in plan.segments if s.fx.get("boom"))
    top3 = {a.name for a in usable[:3]}
    assert hero.shot.clip in top3
    assert climax.shot.clip in top3 and climax.shot.clip != hero.shot.clip


@pytest.mark.parametrize("length", ["short", "long"])
def test_never_repeats_footage_or_puts_a_clip_next_to_itself(analyses, song, length):
    plan = make_plan(analyses, song, title="Tokyo", length=length, masks_ok=False)
    assert footage_overlaps(plan) == []
    for a, b in zip(plan.segments, plan.segments[1:]):
        if a.shot and b.shot and not b.fx.get("continues"):
            assert a.shot.clip != b.shot.clip
    # every usable clip is used before any clip is used a second time
    used = {sh.clip for s in plan.segments for sh in s.all_shots()}
    if any(sh.reuse for s in plan.segments for sh in s.all_shots()):
        spare = [a.name for a in analyses if a.usable and a.info.kind == "video" and a.name not in used and a.info.duration > 1.5]
        assert spare == []


def test_strict_mode_uses_each_clip_once(analyses, song):
    plan = make_plan(analyses, song, title="Tokyo", length="long", masks_ok=False, strict=True)
    clips = [sh.clip for s in plan.segments for sh in s.all_shots() if not s.fx.get("continues")]
    assert len(clips) == len(set(clips))
    assert not any(sh.reuse for s in plan.segments for sh in s.all_shots())


def test_big_effects_never_exceed_two(analyses, song):
    for seed in range(12):
        plan = make_plan(analyses, song, title="Tokyo", length="long", masks_ok=True, seed=seed)
        assert len(plan.big_effects()) <= 2


def test_plan_round_trips_through_json(analyses, song, tmp_path):
    from vellum_editor.plan import EditPlan

    plan = make_plan(analyses, song, title="Tokyo", length="short", masks_ok=False)
    plan.save(tmp_path / "p.json")
    again = EditPlan.load(tmp_path / "p.json")
    assert again.total_frames == plan.total_frames
    assert [s.to_dict() for s in again.segments] == [s.to_dict() for s in plan.segments]
