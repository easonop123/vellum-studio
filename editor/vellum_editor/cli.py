"""Command line for testing and power use.

  python -m vellum_editor.cli make --clips DIR --song FILE --title Tokyo [--length long] [--scale 0.25]
  python -m vellum_editor.cli song FILE
  python -m vellum_editor.cli hooks --edit DIR --hook "POV: you send me|your tokyo clips" --hook "..."
  python -m vellum_editor.cli swap --plan DIR/edit-plan.json --segment 7 --clip IMG_1234.MOV
  python -m vellum_editor.cli selftest
"""
from __future__ import annotations

import argparse
import multiprocessing
import sys
import tempfile
import time
from pathlib import Path


def _print_progress(frac: float, stage: str, msg: str, eta: float | None) -> None:
    left = f" ~{eta:.0f}s left" if eta is not None else ""
    print(f"\r[{frac * 100:5.1f}%] {msg[:60]:60s}{left}   ", end="", flush=True)


def main(argv: list[str] | None = None) -> int:
    from . import pipeline
    from .audio import analyze_song

    p = argparse.ArgumentParser(prog="vellum-editor")
    sub = p.add_subparsers(dest="cmd", required=True)

    mk = sub.add_parser("make")
    mk.add_argument("--clips", required=True)
    mk.add_argument("--song", required=True)
    mk.add_argument("--title", required=True)
    mk.add_argument("--length", default="short", choices=["short", "long"])
    mk.add_argument("--look", default="darkroom")
    mk.add_argument("--scale", type=float, default=1.0)
    mk.add_argument("--bpm", type=float)
    mk.add_argument("--drop", type=float)
    mk.add_argument("--song-start", type=float, default=0.0)
    mk.add_argument("--no-masks", action="store_true")
    mk.add_argument("--strict", action="store_true")
    mk.add_argument("--out")
    mk.add_argument("--workers", type=int)
    mk.add_argument("--keep-work", action="store_true")
    mk.add_argument("--preset", default="medium")

    sg = sub.add_parser("song")
    sg.add_argument("file")

    hk = sub.add_parser("hooks")
    hk.add_argument("--edit", required=True, help="the 'Vellum Edit - ...' folder")
    hk.add_argument("--hook", action="append", required=True, help='"line one|line two"')

    sw = sub.add_parser("swap")
    sw.add_argument("--plan", required=True)
    sw.add_argument("--segment", type=int, required=True)
    sw.add_argument("--clip", required=True)

    sub.add_parser("selftest")

    a = p.parse_args(argv)
    if a.cmd == "song":
        s = analyze_song(a.file)
        print(f"bpm {s.bpm:.2f}  beat {s.beat:.4f}s  drop {s.drop:.3f}s (jump {s.drop_strength} dB)  confidence {s.confidence}")
        return 0
    if a.cmd == "make":
        settings = pipeline.EditSettings(
            clips_dir=a.clips, song=a.song, title=a.title, length=a.length, look=a.look, scale=a.scale,
            bpm=a.bpm, drop=a.drop, song_start=a.song_start, use_masks=not a.no_masks, strict=a.strict,
            out_dir=a.out, workers=a.workers, keep_work=a.keep_work, preset=a.preset,
        )
        t = time.time()
        res = pipeline.make_edit(settings, on_progress=_print_progress)
        print(f"\ndone in {time.time() - t:.1f}s -> {res.out_dir}")
        for k, v in res.files.items():
            print(f"  {k}: {v.name}")
        return 0
    if a.cmd == "hooks":
        from .hooks import make_hooks
        from .plan import EditPlan

        edit = Path(a.edit)
        plan = EditPlan.load(edit / "edit-plan.json")
        names = pipeline.output_names(plan.title)
        hooks = [tuple((h.split("|", 1) + [""])[:2]) for h in a.hook]
        made = make_hooks(edit / names["vertical_post"], pipeline.safe_title(plan.title), hooks, plan.drop_edit, edit)
        for m in made:
            print(m.name)
        return 0
    if a.cmd == "swap":
        from .plan import EditPlan

        plan = EditPlan.load(a.plan)
        note = pipeline.swap_shot(plan, a.segment, a.clip)
        plan.save(a.plan)
        if note:
            print("note:", note)
        res = pipeline.rerender(a.plan, on_progress=_print_progress)
        print(f"\nre-rendered in {res.seconds:.1f}s")
        return 0
    if a.cmd == "selftest":
        from .testmedia import make_song, make_test_set

        with tempfile.TemporaryDirectory(prefix="vellum-selftest-") as tmp:
            clips = Path(tmp) / "clips"
            make_test_set(clips, count=14)
            truth = make_song(Path(tmp) / "song.wav", bpm=120, total=40)
            settings = pipeline.EditSettings(clips_dir=str(clips), song=str(truth.path), title="Test", scale=0.25,
                                             use_masks=False, preset="ultrafast")
            res = pipeline.make_edit(settings, on_progress=_print_progress)
            print(f"\nselftest ok: {len(res.plan.segments)} cuts in {res.seconds:.1f}s")
        return 0
    return 1


if __name__ == "__main__":
    multiprocessing.freeze_support()
    sys.exit(main())
