"""Make the website's placeholder demos with the real engine.

Procedurally drawn night-city "clips" (no real footage) and a synthesised drum
track (no real song) go through Vellum Editor exactly like a customer job.
The vertical "preview with song" outputs become public/demos/*.mp4, so the
placeholders show what the product actually makes. Replace them with real
edits later (YOUR-STEPS.md, Part B).

    cd editor && python tools/make_engine_demos.py
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

from make_site_placeholders import THEMES, Scene  # noqa: E402

from vellum_editor import pipeline  # noqa: E402
from vellum_editor.paths import ffmpeg_path  # noqa: E402
from vellum_editor.testmedia import make_song  # noqa: E402

OUT = ROOT / "public" / "demos"
DEMOS = [("tokyo", "tokyo", "neon_night", 1), ("italy", "italy", "warm_film", 2), ("new-york", "new york", "darkroom", 3)]


def write_clip(path: Path, theme: dict, seed: int, kind: int, w: int, h: int, seconds: float, fps: int = 30) -> None:
    scene = Scene(w, h, theme, seed, kind)
    proc = subprocess.Popen(
        [ffmpeg_path(), "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", str(path)],
        stdin=subprocess.PIPE,
    )
    for f in range(int(seconds * fps)):
        a = scene.frame(f / fps)
        proc.stdin.write((np.clip(a, 0, 1) * 255).astype(np.uint8).tobytes())
    proc.stdin.close()
    proc.wait()


def web_encode(src: Path, dst: Path, *, seconds: float | None = None, audio: bool = True) -> None:
    args = [ffmpeg_path(), "-v", "error", "-y", "-i", str(src)]
    if seconds:
        args += ["-t", f"{seconds:.2f}"]
    args += ["-vf", "scale=540:960:flags=lanczos", "-c:v", "libx264", "-preset", "slow", "-crf", "27", "-pix_fmt", "yuv420p",
             "-movflags", "+faststart"]
    args += ["-c:a", "aac", "-b:a", "96k"] if audio else ["-an"]
    subprocess.run(args + [str(dst)], check=True)


def poster(src: Path, dst: Path, t: float) -> None:
    subprocess.run([ffmpeg_path(), "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(src), "-frames:v", "1",
                    "-vf", "scale=540:960", "-q:v", "4", str(dst)], check=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="vellum-demos-") as tmp:
        tmp = Path(tmp)
        song = make_song(tmp / "song.wav", bpm=124, lead_in=0.4, intro_beats=16, total=60)
        for slug, title, look, seed in DEMOS:
            clips = tmp / slug
            clips.mkdir()
            theme = THEMES[title]
            for i in range(30):
                vertical = i % 4 == 1
                w, h = (360, 640) if vertical else (640, 360)
                write_clip(clips / f"IMG_{4800 + i:04d}.MOV", theme, seed * 1000 + i, i % 3, w, h, 4.0 + (i % 3))
            settings = pipeline.EditSettings(
                clips_dir=str(clips), song=str(song.path), title=title.title(), look=look, scale=0.5,
                use_masks=False, preset="medium",
            )
            res = pipeline.make_edit(settings, on_progress=lambda f, s, m, e: print(f"\r{slug}: {f * 100:5.1f}% {m[:40]:40s}", end=""))
            print()
            src = res.files["vertical_preview"]
            web_encode(src, OUT / f"{slug}.mp4")
            plan = res.plan
            hero = next(s for s in plan.segments if s.fx.get("hero"))
            title_done = (plan.F(hero.k0) + 2 + 2 * len(plan.title) + 6) / 24
            poster(src, OUT / f"{slug}.jpg", title_done)
            if slug == "tokyo":
                # the hero loop: intro, drop, title and the first cuts, no sound (it autoplays muted)
                web_encode(src, OUT / "hero.mp4", seconds=plan.drop_edit + 7.0, audio=False)
                poster(src, OUT / "hero.jpg", title_done)
            print(f"{slug}: {(OUT / f'{slug}.mp4').stat().st_size / 1024:.0f} KB, {len(plan.segments)} cuts, look {look}")
            shutil.rmtree(res.out_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
