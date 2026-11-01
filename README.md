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

Placeholder demo videos are generated with `python3 editor/tools/make_site_placeholders.py`.
