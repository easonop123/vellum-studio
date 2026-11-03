# Vellum Studio

Cinematic, beat-synced short edits from your clips. Two things live here:

- **The website** (repo root): showcase, order form, Stripe payments, admin. Next.js, deployed on Vercel.
- **Vellum Editor** (`editor/`): the Mac app that makes the edits in the house style.

Start with **[YOUR-STEPS.md](YOUR-STEPS.md)**: what you need to click, in order.
**[PROGRESS.md](PROGRESS.md)** says what works. **[DECISIONS.md](DECISIONS.md)** explains the choices.

`reference/` holds the original hand-made edit scripts the app is modelled on.

## For developers

```bash
npm install
npm run dev          # http://localhost:3000, fake checkout, uploads to .data/
npm run test:unit    # webhook unit tests (Vitest)
npm run build && npm run test:e2e   # Playwright smoke tests
```

Environment variables (all optional locally): `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `ADMIN_PASSWORD`, `CRON_SECRET`, `BLOB_READ_WRITE_TOKEN` or `BLOB_STORE_ID` (added by Vercel), `BLOB_ACCESS` (`private` default).

The placeholder demo videos in `public/demos/` are made by the editor itself: `cd editor && python tools/make_engine_demos.py`.

### Vellum Editor (Mac app)

```bash
cd editor
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python run_app.py                       # the window
.venv/bin/python -m vellum_editor.cli make --clips ~/Desktop/Tokyo --song song.mp3 --title Tokyo
.venv/bin/python -m vellum_editor.cli song song.mp3   # just the BPM and drop
.venv/bin/python -m pytest -q                    # 79 tests, including end-to-end renders
```

Needs `ffmpeg` on PATH when run from source. The person-mask model (`u2net_human_seg.onnx`) goes in `editor/vellum_editor/assets/models/`. Without it, titles are placed without masks.

The `.dmg` is built by `.github/workflows/editor.yml` on GitHub's Apple Silicon runner.
