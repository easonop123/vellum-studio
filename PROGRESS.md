# Progress

Updated as I go. Newest status first.

## Where things stand

| Part | Status |
| --- | --- |
| 1. Website (showcase, order form, Stripe test payments, admin) | **Works.** Tests pass here and on GitHub. Needs your Vercel + Stripe setup (YOUR-STEPS.md, Part A) |
| 2. Mac app engine | **Works.** Makes complete edits; 75 tests pass on Linux and on GitHub's Mac |
| 3. Mac `.dmg` built by GitHub Actions | **Works.** Every push builds the app on GitHub's Apple Silicon Mac, checks it makes an edit, and makes the `.dmg`. Releases start once `main` has the code (YOUR-STEPS A1) |
| 4. Polish | Most effects from your v4–v8 scripts and four looks are in. Fine-tuning needs your first real edit |

## Mac app: what works

- **The whole job.**
  - Analyses the song: BPM and drop, both nudgeable in the window, plus a "hear the drop" button.
  - Scores every clip and throws out junk (dark, blown out, blurry, shaky, damaged or empty files), listing why.
  - Plans the edit in your house style and renders all four files: vertical and 16x9, each "post this" (sound effects only) and "preview with song". Also writes `edit-plan.json` and `review.html`.
- **Timing:** cuts land on the beat grid `frame(k) = round((DROP + k × BEAT) × 24)`. On test songs the grid is within ±2 ms of the real beat a minute in; a frame is 42 ms.
- **Structure:**
  - raw "camera roll" intro with file-name labels, swelling to white on the drop;
  - hero title in Anton red, behind the person and always readable;
  - beat-cut main section with the corner labels;
  - climax with picture-in-picture inserts;
  - typed ending with the letterbox closing, then the VELLUM / STUDIO end card.
  - The vertical uses your exact layout and TikTok Sans text.
- **Effects:**
  - **Small:** punch-in, zoom blur, whip blur, shake + RGB split, white and black flash, light leak, glitch, flicker, typed text, flickering red corner labels, B&W flash, red border, zoom-through speed ramp, colour pop (v8), slit reveal and sliding strips (v6), light-leak cut (v4/v6), polaroid fly-off (v7/v8).
  - **Big (max 2):** 3×3 grid, triple frame + sticker, film strip, giant letters, spaced glowing title, cut-out sticker, white silhouette flash.
- **Looks:** Darkroom (your reference grade), Warm Film, Neon Night, Clean. Night street-light shots get the orange pulled down.
- **Sound design:**
  - a shutter on almost every cut (4 rotating);
  - the drop: riser, whoosh, impact, flash, click burst and ring;
  - whooshes on whips, clicks on grid tiles, the ending hits;
  - random volume/pan per hit, and the song ducked under impacts in the preview.
  - All synthesised in code; your own sound folder can replace any sound.
- **Messy inputs:**
  - iPhone HDR/HLG and Dolby Vision are tone-mapped to SDR; HEVC clips work.
  - Rotated and vertical clips, and mixed 24/25/30/60/120 fps (real slow motion on 50+ fps clips at the drop and climax).
  - Photos get a slow zoom; corrupt files are skipped and listed.
  - An optional LUT handles DJI D-Log M.
- **Extras:**
  - **Make hook versions:** two lines each, until the drop.
  - **Swap a shot:** re-renders using the saved plan.
  - Clip analysis is cached, so re-renders after a nudge are quick.
- **Disk and speed:** only the frames each shot needs are extracted, at most 1920 wide. A 30 s edit uses about 0.7 GB of temp space, deleted afterwards. All CPU cores are used, with a progress bar and time left.
  - Full 1080p 30 s edit: about 4 minutes on this 4-core cloud machine. Expect roughly 1.5–2 minutes on an Apple Silicon Mac.
- **Tests (75):**
  - beat and drop accuracy at five tempos;
  - probing (rotation, HDR, fps, photos, corrupt files) and junk rejection;
  - planner rules (structure, the grid, never repeated footage, never side by side, strict mode, ≤ 2 big effects);
  - title readability against fake people, and the sound bank;
  - the slit, strips, light leak, polaroid and colour pop, drawn from known test frames;
  - **end-to-end low-res renders**, checking:
    - cuts on the beat against the real song, and visible in the rendered video on the planned frame ±1;
    - no clip repeated, ≤ 2 big effects, the title readable and on screen;
    - audio present, plus duration, resolution and fps;
    - hooks and swap-a-shot;
  - the real app window driven through a whole job.

## Mac build (GitHub Actions)

`.github/workflows/editor.yml` does the following:

1. Runs the tests on Linux.
2. On a GitHub Apple Silicon Mac, downloads a static ffmpeg and runs the tests again with it.
3. Builds `Vellum Editor.app` with PyInstaller.
4. Makes the built app render an edit on its own (`--selftest`).
5. Wraps the app in `Vellum-Editor.dmg`.

On `main`, the `.dmg` is attached to a GitHub Release.

**Latest check (2 Nov):** every step passed. The tests passed on Linux and macOS, the built app rendered a 46-cut edit by itself in 12.5 s, and the `.dmg` came out at 281 MB. Most of that is the person-finding model and the video tools inside it. The release step only runs on `main`, so it starts after YOUR-STEPS A1.

## Website: what works

- **Home page:** hero video with live timecode, RAW → EDIT drag slider, three demos from `content/demos.json`, how it works, NZD pricing, FAQ, footer. Built for 375 px phones first; videos only load when they scroll into view.
- **Order form:**
  - all fields;
  - uploads go straight to Vercel Blob with progress bars and caps;
  - link box;
  - errors written in your voice.
- **Payment:**
  - Stripe Checkout in NZD.
  - A cancelled payment keeps the order and offers "try paying again".
  - Orders are marked paid by the webhook and again by the thanks page.
- **Pages:** thanks page with the order number; `/admin` behind one password; daily clean-up of clips after 30 days.
- **Tests:** 10 webhook unit tests (real Stripe-signed events) and 15 Playwright tests at phone and laptop size. They run here and on every push via GitHub Actions.

## What I couldn't test from here

- **Vercel Blob and Stripe for real:** they need your accounts. The test order in YOUR-STEPS A6 is the check.
- **The app on a real Mac:** the GitHub Mac runner builds and self-tests it, but nobody has clicked through the window on a Mac yet. Same for the first-open security prompt and "hear the drop" (macOS only).
- **Real footage:** all automated tests use synthetic clips (no copyrighted footage in the repo). Your first real edit is the true test of the look. If anything is off, tell me what to change: timings, effects and the grade are all in one place.

## What you need to do

1. YOUR-STEPS.md **Part A**: merge, Stripe test key, Vercel, Blob store, webhook, test order.
2. **Part E**: download the app from Releases, open it once, make a test edit with real clips.
3. Later: **Part B** (real demo videos), **Part C** (live payments), **Part D** (your domain).
