# Decisions

Choices I made while building, and why. Newest sections at the bottom of each part.

## Repo layout

- **The website lives at the repo root** (Next.js). Vercel finds it with zero settings, so importing the repo is one click.
- **The Mac app lives in `editor/`** (Python engine + window + packaging). Vercel ignores it (`.vercelignore`).
- **Your hand-made scripts moved to `reference/`** (`v4.py`, `v6.py`, `v7.py`, `v8.py`, `hooks/mk.py`). They were at the root; the brief expects a `reference/` folder, and the website needs the root.

## Website: design plan

The brief pins the palette, the two typefaces and the voice. Everything below is how I used them.

### Colour (5 tokens)

| token | hex | use |
| --- | --- | --- |
| ink | `#0D0D0F` | page background (brief) |
| bone | `#EDEAE4` | text (brief) |
| safelight | `#FF4D3D` | the one accent: REC dot, playhead, primary button, errors (brief) |
| graphite | `#2A2A2F` | panels, inputs, video frames (brief) |
| ash | `#8E8B85` | secondary text. Bone pulled toward ink; 5.6:1 contrast on ink, passes AA |

Safelight buttons use ink text (5.9:1). Bone on safelight fails contrast, so it's never used.

### Type

- **Space Grotesk Bold, uppercase, tight tracking (-0.035em)** for headlines (brief). Line height 0.9 so stacked lines read as one block.
- **Space Grotesk Regular** for body copy, written lowercase, 17–18 px.
- **JetBrains Mono** only for things that are actually data: timecodes, durations, file names, `● REC`, `RAW → EDIT` (the brief's own examples). Tabular numbers so timecode doesn't jitter.
- Scale (≈1.34 ratio): 12.5 / 14 / 17 / 22 / 30 / 40 / 54 / 72 / 96.

### Layout concept: "a program monitor in a dark room"

The page opens on the footage itself. On a phone the demo plays edge to edge (like it would on TikTok, where most visitors come from) with a live timecode and `● REC` burned in. The headline and the big button sit over the bottom of the video, in thumb reach. On a laptop the video sits in a 9:16 monitor on the right and the headline takes the left.

```
phone (375)                      laptop (1440)
┌───────────────────────┐        ┌─────────────────────────────────────────────┐
│ ● VELLUM / STUDIO  order│      │ ● VELLUM / STUDIO                    order  │
│▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓│        │ SEND ME YOUR CLIPS.          ┌─────────┐    │
│▓ ● REC 00:00:04:12 ▓▓▓│        │ I'LL CUT THEM TO THE         │● REC tc │    │
│▓▓▓ vertical demo ▓▓▓▓▓│        │ SONG YOU PICK.               │ 9:16    │    │
│▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓│        │ line of plain copy           │ demo    │    │
│ SEND ME YOUR CLIPS.   │        │ [ send me your clips ]       │         │    │
│ I'LL CUT THEM TO ...  │        │                              └─────────┘    │
│ [ send me your clips ]│        ├─────────────────────────────────────────────┤
└───────────────────────┘        │ RAW → EDIT   wipe with a red playhead       │
                                 │ demos · how it works · pricing · faq · foot │
                                 └─────────────────────────────────────────────┘
```

Text is left-aligned, one column of at most ~62 characters. Sections are separated by space, not rules or boxes.

### Principles

1. **Footage first.** The video is the hero; words are captions.
2. **Timecode means something.** It appears only where it's real data: the playing clip's position, a package's maximum length (`00:00:30:00`), the delivery window.
3. **One loud moment.** The RAW → EDIT wipe with the safelight playhead is the thing people remember. Everything around it stays quiet.
4. **Sounds like a DM from you.** Lowercase, first person, plain.
5. **Phone first.** Thumb-reachable button, no sideways scrolling, light above the fold.

### Review against the brief (what I changed before building)

- My first sketch put a mono marker (`01 — DEMOS`) above every heading. That's template chrome, not information, so it's gone. Only "how it works" is numbered, because it's a real sequence.
- I had `● REC` in the site header. Nothing is recording there, so it moved onto the hero video, next to the live timecode of the clip that's actually playing.
- I had a scroll-progress "timeline" bar across the top. Decorative motion, cut.
- Pricing started as two identical rounded cards with shadows (the generic SaaS look). It's now a flat two-column "export preset" panel, where each package's length is shown as a timecode.
- Kept: near-black + one red accent + mono labels. Those are generic choices in general, but here the brief asks for them exactly.

## Website: how it works underneath

- **Next.js 16.4 with Cache Components** (the new default). Pages that read cookies or the URL stream inside `<Suspense>`; the home page is fully static.
- **Payments: Stripe Checkout**, one-off payment in NZD. Prices live in `content/site.json` and are only ever read on the server, so nobody can change the price from their browser.
- **Fake checkout for tests and local runs.** With no Stripe key, the order button goes to a fake payment page instead. On the live site the fake page is switched off unless you deliberately set `ALLOW_FAKE_CHECKOUT=1`, so a missing key can't give away free edits.
- **Two ways an order gets marked paid:** the Stripe webhook, and the thanks page (it asks Stripe directly when the customer lands there). Either one is enough, so a webhook hiccup doesn't lose a paid order.
- **No database.** Each order is a few small JSON files in Vercel Blob:
  - `orders/<id>/order-….json` holds the form;
  - `paid-….json` and `delivered-….json` are added when those things happen.
  
  Files are never overwritten, so there are no stale caches or race conditions. Locally (no Blob token) the same files go into `.data/`.
- **Private Blob store.** Customer clips are private. Your admin page makes short-lived download links. This needs the store to be created as **Private** (it's in the steps).
- **Upload caps, because the free Blob tier is tight.** The free tier gives 1 GB of storage and 2,000 write operations a month, and going over locks the store for 30 days. Limits per order: 40 files, 150 MB per file, 400 MB total. Anything bigger should come as a Google Drive / WeTransfer / iCloud / Dropbox link, and the form says so. Files over 64 MB are uploaded in 8 MB parts (more reliable on phones); smaller ones go in one request to save operations.
- **Clips get deleted.** A daily clean-up job deletes clips 30 days after upload, as the FAQ promises. Clips from orders that never got paid go after 3 days. The admin page also has a "delete clips" button for after you've delivered.
- **No Resend / email service.** Stripe emails you about payments and the customer gets Stripe's receipt. That's one less account.

## Mac app (Vellum Editor): engine

- **Python engine, numpy only for analysis.** No librosa, no OpenCV. They're big and fragile to bundle into a Mac app, and numpy does the job:
  - Beat detection folds the onset strength over candidate tempos and picks the exact period and phase. On test songs it's within ±2 ms of the true beat a minute after the drop (one frame is 42 ms).
  - Clip scoring (sharpness, exposure, shake by phase correlation, colour) is plain array maths.
- **The drop** is the first beat where the next 8 beats are clearly louder than the last 8 (≥ 4.5 dB, and among the loudest parts of the song). It ignores the song simply starting out of silence. You can always nudge it.
- **Fast songs (> 150 BPM) are cut half-time, very slow ones (< 72) double-time**, so cuts stay around 4–8 a second. The app tells you when it does this.
- **The edit starts two bars before the drop** (your scripts' 8-beat raw intro). If the drop comes earlier than that, the intro gets shorter.
- **"Never repeat a clip": how I read it.** Your scripts reuse clips at different moments to stay snappy (v8 used 35 clips for about 45 shots), and the brief also wants mostly 8th-note cuts. With 10–40 customer clips both can't be true at once. So by default:
  - every usable clip is used once before any clip is used again;
  - a second use is always a different moment, never overlapping, never next to its first use;
  - no clip is used more than 4 times;
  - when footage really runs out, the edit ends earlier rather than holding one shot for ages (Short/Long are maximum lengths).
  
  The **Never reuse a clip** box is the strict version: each clip at most once, with fewer cuts. `review.html` lists any clip that appears twice.
- **Best clip on the drop, second best at the climax** (a 4-beat hold about 65% of the way through, with light leak, shake and picture-in-picture inserts). The third best gets the ending. The weakest usable clips go in the raw intro: they're shown "as sent", ungraded.
- **Big effects: at most 2,** chosen per edit from 3×3 grid, triple frame + sticker, film strip, giant letters, spaced glowing title, cut-out sticker, silhouette flash. Effects that eat many clips (grid needs 9) are only picked when there are clips to spare. People-based ones (sticker, silhouette) are only picked when a person is found.
- **Readable title.** The hero title goes behind the person using the mask, measured across the whole hero shot. It needs ≥ 78% of the title and ≥ 60% of every single letter visible. The app tries centred, beside the person, split around them (NEW | YORK) and above them. A little overlap is preferred (that's the "standing in front of the letters" look). If nothing is readable enough, the title goes in front.
- **Slow motion is only real slow motion:** clips shot at 47+ fps play at 0.5× on the drop and 0.45× at the climax. Everything else plays at normal speed (no fake frame-blending).
- **HDR / Dolby Vision / HLG** go to SDR with ffmpeg's `zscale` + Hable tone mapping. If an ffmpeg build lacks `zscale`, a rough contrast/saturation fallback is used and the build log warns about it.
- **D-Log M**: there's no reliable way to detect log footage from metadata, so it's an optional `.cube` LUT in Settings, applied to DJI clips or to all clips.
- **Night street-light shots** (dark, with orange highlights) get a variant of each look that pulls orange down instead of warming it further.
- **Looks:** Darkroom (your exact reference grade), Warm Film, Neon Night, Clean. Bloom, vignette and grain are added per frame, as in your `finish()`.
- **Slit reveal (v6) and polaroid fly-off (v7/v8)** keep the previous shot playing for 6–8 frames while the new one comes in. Those frames count as used footage, so they can't break the never-repeat rule. They only follow a plain cut, never the hero, the climax, a big effect or a zoom-through.
- **Colour pop keeps the shot's own strongest colour**, not always yellow. v8 popped New York's yellow taxis, but customer clips have neon pink, sea blue or a red jacket instead. Yellow is the fallback when no colour stands out.
- **Vertical layout is your reference layout:**
  - the 16:9 picture is a band in the middle;
  - TikTok Sans text sits above it ("the clips they sent me" / "what i made with them" / "want yours like this?") and below it ("no edit, no grade");
  - the bottom bar has `@vellumstudio.edits` and the blinking `REC mm:ss`;
  - "dm me your clips" appears in the last 8 beats.
- **Sound effects are synthesised in code** (shutters, clicks, riser, whoosh, impact, flash, ring, glitch), so they're royalty-free and nothing extra ships. Cue placement, levels, ±1.2 dB / ±0.15 pan randomness and song ducking are ported from your `audio()`. A Settings folder can replace any sound.
- **Never decodes whole clips.** Each shot extracts only its own frames, cropped around the person (or the detail) and scaled to at most 1920 wide, as JPEGs in a temp folder. Frames go straight from the renderer into ffmpeg (no frame files), and the temp folder is deleted at the end. A 30 s edit peaks around 0.7 GB of temp space.
- **Every core:** the edit renders in 2-second chunks across all CPU cores, then the chunks are joined without re-encoding.
- **Files:** H.264, CRF 17 capped at 16 Mbps. Grain makes uncapped files huge, and TikTok/Instagram re-encode anyway. Audio is AAC 256k. The output folder **Vellum Edit - (title)** goes inside the clips folder.
- **Clip analysis is cached** in that output folder, so changing the BPM, drop, title or look and pressing Make edit again skips straight to rendering.
- **Hooks** follow your `hooks/mk.py`: black band, two TikTok Sans lines, line 2 red from HOOK 3 on, shown until the drop.

## Mac app: window and packaging

- **PySide6 window** (the "Essentials" wheel, no web view). Drag-and-drop gives real file paths and it packages reliably.
- **Work runs on background threads** and talks to the window through Qt signals, so the window never freezes. Rendering itself uses separate worker processes.
- **"Hear the drop"** plays a few seconds around the drop with a click on every beat, using macOS's built-in `afplay`. The slim Qt package has no audio player.
- **PyInstaller** builds `Vellum Editor.app` on GitHub's Apple Silicon runner (`macos-14`), with:
  - a static ffmpeg/ffprobe (from ffmpeg.martin-riedl.de, falling back to osxexperts.net);
  - the u2net_human_seg model and the fonts, so it works offline.
  
  The build runs the tests on macOS, then makes the built `.app` produce an edit by itself (`--selftest`) before wrapping the `.dmg`.
- **Not signed** (that needs a paid Apple developer account). The first open needs right-click → Open, or Open Anyway. After that, the app clears the download-quarantine flag from its own files so the bundled ffmpeg can run.
- **Releases:** every push to `main` that changes `editor/` makes a new GitHub Release with the `.dmg`. Pushes to other branches build and test, and keep the `.dmg` as a 14-day artifact.
