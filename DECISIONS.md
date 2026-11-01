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
