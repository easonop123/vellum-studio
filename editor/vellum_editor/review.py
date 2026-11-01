"""review.html: a contact sheet of the edit, the clips it used, and the clips it threw out (and why)."""
from __future__ import annotations

import base64
import html
import io
from collections import Counter
from pathlib import Path

from PIL import Image

from .plan import FPS, EditPlan

FX_NAMES = {
    "raw": "raw", "hero": "hero title", "boom": "climax", "punch": "punch-in", "creep": "slow zoom", "whip": "whip",
    "bw": "b&w flash", "rgb": "rgb split", "border": "red border", "leak": "light leak", "zt": "zoom-through",
    "flash": "white flash", "sil": "silhouette flash", "spaced": "spaced title", "ending": "ending", "prebloom": "swell to drop",
    "continues": "carries on", "pips": "picture-in-picture",
}
KIND_NAMES = {"grid9": "3x3 grid", "tri": "triple frame", "film": "film strip", "tmask": "giant letters", "cutout": "cut-out sticker"}


def _thumb_from_frames(work: Path, shot_id: str, width: int = 192) -> str:
    d = work / "frames" / shot_id
    files = sorted(d.glob("*.jpg")) if d.exists() else []
    if not files:
        return ""
    im = Image.open(files[min(len(files) - 1, 3)]).convert("RGB")
    im.thumbnail((width, width))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=70)
    return base64.b64encode(buf.getvalue()).decode()


def _tc(frame: int) -> str:
    s = frame // FPS
    return f"{s // 60}:{s % 60:02d}.{frame % FPS:02d}"


def _img(b64: str, alt: str) -> str:
    if not b64:
        return '<div class="noimg">no picture</div>'
    return f'<img src="data:image/jpeg;base64,{b64}" alt="{html.escape(alt)}">'


def write_review(plan: EditPlan, work: Path | None, out: Path, outputs: list[str]) -> None:
    e = html.escape
    uses = Counter(sh.clip for seg in plan.segments for sh in seg.all_shots())
    rows = []
    for idx, seg in enumerate(plan.segments):
        f0, f1 = plan.frames_of(seg)
        effects = [KIND_NAMES[seg.kind]] if seg.kind in KIND_NAMES else []
        effects += [FX_NAMES.get(k, k) for k, v in seg.fx.items() if v and k in FX_NAMES]
        shots = seg.all_shots()
        main = shots[0] if shots else None
        thumb = _thumb_from_frames(work, main.id) if (work and main) else (plan.clips.get(main.clip, {}).get("thumb", "") if main else "")
        clip_txt = "<br>".join(
            f'{e(sh.clip)} <span class="dim">{sh.ss:.2f}s{" (2nd moment)" if sh.reuse else ""}</span>' for sh in shots
        ) or '<span class="dim">no footage</span>'
        big = f'<span class="tag big">{e(seg.big)}</span>' if seg.big else ""
        rows.append(f"""
      <tr id="seg{idx + 1}">
        <td class="num">#{idx + 1}</td>
        <td class="thumb">{_img(thumb, f"segment {idx + 1}")}</td>
        <td class="mono">{_tc(f0)}<br><span class="dim">{seg.k1 - seg.k0:g} beat{'s' if seg.k1 - seg.k0 != 1 else ''}, {f1 - f0} frames</span></td>
        <td>{clip_txt}</td>
        <td>{big}{''.join(f'<span class="tag">{e(x)}</span>' for x in effects)}</td>
      </tr>""")

    used_cards, unused_cards = [], []
    for name, d in sorted(plan.clips.items()):
        card = f"""
      <figure class="clip">{_img(d.get("thumb", ""), name)}
        <figcaption><b>{e(name)}</b><br>
        <span class="dim">score {d.get("score", 0):.2f} · {d["info"]["width"]}x{d["info"]["height"]} · {d["info"]["fps"]:g} fps · {d["info"]["duration"]:.1f}s{" · HDR" if d["info"].get("hdr") or d["info"].get("dolby_vision") else ""}</span><br>
        {"used " + str(uses[name]) + "x" if uses[name] else "not used"}</figcaption></figure>"""
        (used_cards if uses[name] else unused_cards).append(card)
    rejected_cards = [
        f"""
      <figure class="clip rejected">{_img(r.get("thumb", ""), r["name"])}
        <figcaption><b>{e(r["name"])}</b><br><span class="why">{e(r["reason"])}</span></figcaption></figure>"""
        for r in plan.rejected
    ]
    song_name = Path(plan.song["path"]).name
    notes = "".join(f"<li>{e(n)}</li>" for n in plan.notes) or "<li>nothing to flag.</li>"
    outs = "".join(f"<li>{e(o)}</li>" for o in outputs)
    title_note = ""
    if plan.title_layout:
        tl = plan.title_layout
        title_note = (f"hero title: {e(tl['mode'])} layout, {tl['visible'] * 100:.0f}% of the letters visible "
                      f"({'behind the person' if tl.get('behind') else 'in front of the person'})")
    doc = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(plan.title)} | edit review</title>
<style>
:root {{ --ink:#0d0d0f; --bone:#edeae4; --red:#ff4d3d; --graphite:#2a2a2f; --ash:#8e8b85; }}
* {{ box-sizing:border-box }}
body {{ margin:0; background:var(--ink); color:var(--bone); font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }}
main {{ max-width:1100px; margin:0 auto; padding:32px 20px 80px }}
h1 {{ font-size:40px; line-height:1; text-transform:uppercase; letter-spacing:-.03em; margin:0 0 8px }}
h2 {{ font-size:22px; text-transform:uppercase; letter-spacing:-.02em; margin:48px 0 14px }}
.mono, .num {{ font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:13px }}
.dim {{ color:var(--ash) }}
.stats {{ display:flex; flex-wrap:wrap; gap:8px 24px; color:var(--ash) }}
.stats b {{ color:var(--bone); font-weight:600 }}
table {{ width:100%; border-collapse:collapse }}
td {{ border-top:1px solid var(--graphite); padding:8px 10px 8px 0; vertical-align:top }}
td.thumb img {{ width:160px; border-radius:2px; display:block }}
.tag {{ display:inline-block; border:1px solid var(--graphite); border-radius:99px; padding:0 8px; margin:0 4px 4px 0; font-size:12px }}
.tag.big {{ border-color:var(--red); color:var(--red) }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(170px,1fr)); gap:14px }}
.clip {{ margin:0 }} .clip img {{ width:100%; border-radius:2px; display:block }}
.clip figcaption {{ font-size:12px; margin-top:6px; word-break:break-all }}
.rejected img {{ opacity:.45 }} .why {{ color:var(--red) }}
.noimg {{ width:160px; height:90px; background:var(--graphite); color:var(--ash); font-size:11px; display:grid; place-items:center }}
ul {{ padding-left:20px }}
</style></head><body><main>
<h1>{e(plan.title)}</h1>
<div class="stats">
  <span><b>{plan.length}</b> edit, {plan.total_frames / FPS:.1f}s</span>
  <span>look <b>{e(plan.look)}</b></span>
  <span>song <b>{e(song_name)}</b></span>
  <span><b>{plan.song["bpm"]:.2f}</b> bpm</span>
  <span>drop at <b>{plan.song["drop"]:.2f}s</b> in the song</span>
  <span><b>{len(plan.segments)}</b> cuts</span>
  <span><b>{len(used_cards)}</b> clips used, {len(unused_cards)} spare, {len(rejected_cards)} rejected</span>
  <span>big effects: <b>{e(", ".join(plan.big_effects()) or "none")}</b></span>
</div>
<p class="dim">{title_note}</p>
<h2>notes</h2><ul>{notes}</ul>
<h2>files</h2><ul class="mono">{outs}</ul>
<h2>timeline</h2>
<p class="dim">to swap a shot: in Vellum Editor click <b>Swap a shot</b>, pick the segment number from this list, then pick a different clip.</p>
<table>{''.join(rows)}</table>
<h2>clips used</h2><div class="grid">{''.join(used_cards)}</div>
<h2>spare clips</h2><div class="grid">{''.join(unused_cards) or '<p class="dim">none: every good clip made it in.</p>'}</div>
<h2>rejected</h2><div class="grid">{''.join(rejected_cards) or '<p class="dim">none.</p>'}</div>
</main></body></html>
"""
    out.write_text(doc, encoding="utf-8")
