"""Render a real (low resolution) edit and check what comes out.

Checks from the brief: cuts land on beats (+-1 frame), no clip is repeated,
at most 2 big effects, the title is readable, the files have audio, and the
duration, resolution and fps are right.
"""
import json
import subprocess

import numpy as np
import pytest

from vellum_editor import pipeline
from vellum_editor.ffmpeg import read_audio
from vellum_editor.paths import ffmpeg_path, ffprobe_path
from vellum_editor.plan import EditPlan

from .conftest import SONG_BPM

pytestmark = pytest.mark.slow
SCALE = 0.25


def _render(media, tmp_path_factory, name, **kw):
    out = tmp_path_factory.mktemp(name)
    settings = pipeline.EditSettings(
        clips_dir=str(media["clips"]), song=str(media["song"].path), title="Tokyo", length="short",
        scale=SCALE, use_masks=False, preset="ultrafast", out_dir=str(out), **kw,
    )
    return pipeline.make_edit(settings)


@pytest.fixture(scope="module")
def edit(media, tmp_path_factory):
    return _render(media, tmp_path_factory, "edit")


@pytest.fixture(scope="module")
def strict_edit(media, tmp_path_factory):
    return _render(media, tmp_path_factory, "strict", strict=True)


def probe_streams(path):
    out = subprocess.run([ffprobe_path(), "-v", "error", "-print_format", "json", "-show_streams", "-count_frames", str(path)],
                         capture_output=True, check=True).stdout
    return json.loads(out)["streams"]


def decode_gray(path, w, h):
    raw = subprocess.run([ffmpeg_path(), "-v", "error", "-i", str(path), "-vf", f"scale={w}:{h}", "-f", "rawvideo",
                          "-pix_fmt", "gray", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, h, w).astype(np.float32)


def decode_rgb(path, w, h):
    raw = subprocess.run([ffmpeg_path(), "-v", "error", "-i", str(path), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, h, w, 3)


def test_all_files_exist_with_the_right_names(edit):
    names = {p.name for p in edit.out_dir.iterdir()}
    for expected in ["Tokyo - vertical (post this).mp4", "Tokyo - vertical (preview with song).mp4",
                     "Tokyo - 16x9 (post this).mp4", "Tokyo - 16x9 (preview with song).mp4", "edit-plan.json", "review.html"]:
        assert expected in names
    assert edit.out_dir.name.startswith("Tokyo") or edit.out_dir.exists()


def test_duration_resolution_fps_and_audio(edit):
    plan = edit.plan
    expected = {"vertical": (270, 480), "16x9": (480, 270)}
    for key, path in edit.files.items():
        if not key.endswith(("post", "preview")):
            continue
        streams = probe_streams(path)
        video = next(s for s in streams if s["codec_type"] == "video")
        audio = [s for s in streams if s["codec_type"] == "audio"]
        size = expected["vertical" if "vertical" in key else "16x9"]
        assert (video["width"], video["height"]) == size
        assert video["r_frame_rate"] == "24/1"
        assert int(video["nb_read_frames"]) == plan.total_frames
        assert plan.total_frames <= 30 * 24
        assert audio and audio[0]["codec_name"] == "aac"
        assert abs(float(audio[0]["duration"]) - plan.total_frames / 24) < 0.1


def test_sound_design_and_song(edit):
    sfx_only = read_audio(edit.files["vertical_post"], sr=48000, channels=2)
    preview = read_audio(edit.files["vertical_preview"], sr=48000, channels=2)
    rms = lambda x: float(np.sqrt(np.mean(x.astype(np.float64) ** 2)))
    assert rms(sfx_only) > 0.01  # there's real sound design in the post-this file
    drop = int(edit.plan.drop_edit * 48000)
    assert rms(preview[drop:]) > rms(sfx_only[drop:])  # the preview has the song in it


def test_cuts_land_on_the_beat(edit, media):
    """Every cut, measured against the song's real beat grid, is within one frame of a (quarter-)beat."""
    plan = edit.plan
    truth = media["song"]
    true_beat = 60.0 / SONG_BPM
    for seg in plan.segments[1:]:
        f = plan.F(seg.k0)
        t_song = plan.song["offset"] + f / 24
        q = true_beat / 4
        nearest = truth.drop + round((t_song - truth.drop) / q) * q
        assert abs(t_song - nearest) <= 1 / 24 + 1e-6, (seg.k0, t_song, nearest)


def colour_hist_changes(path, w=48, h=27):
    """Frame-to-frame change in the coarse colour histogram (0..1). Each test clip has its own tint,
    so a cut shows up even when a busy pattern changes every frame."""
    rgb = decode_rgb_scaled(path, w, h)
    bins = (rgb // 64).astype(np.int32)  # 4 levels per channel
    idx = bins[..., 0] * 16 + bins[..., 1] * 4 + bins[..., 2]
    hists = np.stack([np.bincount(f.ravel(), minlength=64) for f in idx]).astype(np.float64)
    hists /= hists.sum(axis=1, keepdims=True)
    d = 0.5 * np.abs(np.diff(hists, axis=0)).sum(axis=1)
    return np.concatenate([[0.0], d])


def decode_rgb_scaled(path, w, h):
    raw = subprocess.run([ffmpeg_path(), "-v", "error", "-i", str(path), "-vf", f"scale={w}:{h}", "-f", "rawvideo",
                          "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, h, w, 3)


def test_cuts_happen_in_the_video_where_planned(edit):
    """Look at the rendered 16:9 file: every clearly visible cut is on the planned frame (+-1)."""
    plan = edit.plan
    diff = colour_hist_changes(edit.files["wide_post"])
    specials = {plan.F(k) for k in plan.whites + plan.blooms}
    clear, unclear = 0, 0
    for a, b in zip(plan.segments, plan.segments[1:]):
        f = plan.F(b.k0)
        if a.kind != "shot" or b.kind != "shot" or b.fx.get("continues"):
            continue
        noisy = ("whip", "flash", "dark", "flicker", "glitch", "hero", "boom", "ending")
        if any(b.fx.get(k) for k in noisy) or any(a.fx.get(k) for k in ("zt", "prebloom", "flicker", "glitch", "dark")):
            continue
        if any(abs(f - s) <= 3 for s in specials):
            continue
        if a.shot and b.shot and a.shot.clip == b.shot.clip:
            continue
        around = diff[max(1, f - 3) : f + 4]
        peak = max(1, f - 3) + int(np.argmax(around))
        neighbours = np.concatenate([diff[max(1, f - 6) : f - 1], diff[f + 3 : f + 7]])
        if diff[peak] < max(0.12, 2.0 * float(np.median(neighbours))):
            unclear += 1  # two clips that happen to look alike: nothing to measure
            continue
        assert abs(peak - f) <= 1, (f, peak, around)
        clear += 1
    assert clear >= 10 and unclear <= 0.25 * (clear + unclear), (clear, unclear)


def test_no_clip_repeated(strict_edit):
    clips = [sh.clip for s in strict_edit.plan.segments for sh in s.all_shots() if not s.fx.get("continues")]
    assert len(clips) == len(set(clips))


def test_default_edit_never_repeats_footage(edit):
    from .test_planner import footage_overlaps

    assert footage_overlaps(edit.plan) == []


def test_at_most_two_big_effects(edit, strict_edit):
    assert len(edit.plan.big_effects()) <= 2
    assert len(strict_edit.plan.big_effects()) <= 2


def test_title_is_readable(edit):
    layout = edit.plan.title_layout
    assert layout and layout["visible"] >= 0.78 and layout["worst_letter"] >= 0.6
    # and it's really on screen in hero red once it has finished typing
    plan = edit.plan
    rgb = decode_rgb(edit.files["wide_post"], 480, 270)
    hero = next(s for s in plan.segments if s.fx.get("hero"))
    f0 = plan.F(hero.k0)
    typed = f0 + 2 + 2 * len(plan.title)

    def red_share(img):
        r, g, b = img[..., 0].astype(int), img[..., 1].astype(int), img[..., 2].astype(int)
        return float(((r > 140) & (g < 95) & (b < 105) & (r - g > 80)).mean())

    assert red_share(rgb[typed]) - red_share(rgb[f0 + 1]) > 0.05


def test_plan_and_review_are_written(edit):
    plan = EditPlan.load(edit.files["plan"])
    assert plan.total_frames == edit.plan.total_frames and plan.settings.get("render")
    review = edit.files["review"].read_text()
    for r in edit.plan.rejected:
        assert r["name"] in review
    assert "too dark" in review and "blurry" in review


def test_hook_versions(edit):
    from vellum_editor.hooks import make_hooks

    made = make_hooks(edit.files["vertical_post"], "Tokyo", [("POV: you send me", "your tokyo clips"), ("rate this edit", "out of 10")],
                      edit.plan.drop_edit, edit.out_dir)
    assert [p.name for p in made] == ["Tokyo - vertical HOOK 2 (post this).mp4", "Tokyo - vertical HOOK 3 (post this).mp4"]
    base = decode_rgb(edit.files["vertical_post"], 270, 480)
    hooked = decode_rgb(made[1], 270, 480)
    assert len(hooked) == len(base)
    band = slice(int(380 * 0.25) + 2, int(640 * 0.25) - 2)
    before_drop = 10
    assert np.abs(hooked[before_drop, band].astype(int) - base[before_drop, band].astype(int)).mean() > 20
    after = int(edit.plan.drop_edit * 24) + 30
    assert np.abs(hooked[after].astype(int) - base[after].astype(int)).mean() < 6


def test_swap_a_shot_and_rerender(edit):
    plan = EditPlan.load(edit.files["plan"])
    used = {sh.clip for s in plan.segments for sh in s.all_shots()}
    spare = [n for n in plan.clips if n not in used and plan.clips[n]["info"]["kind"] == "video"]
    target = next(i for i, s in enumerate(plan.segments, 1) if s.kind == "shot" and not s.fx.get("raw") and s.k0 > 4)
    new_clip = spare[0] if spare else next(iter(plan.clips))
    pipeline.swap_shot(plan, target, new_clip)
    plan.save(edit.files["plan"])
    res = pipeline.rerender(edit.files["plan"])
    again = EditPlan.load(res.files["plan"])
    assert again.segments[target - 1].shot.clip == new_clip
    assert res.files["vertical_post"].exists()
