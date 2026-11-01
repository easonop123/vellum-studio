# Progress

Updated as I go. Newest status first.

## Where things stand

| Part | Status |
| --- | --- |
| 1. Website (showcase, order form, Stripe test payments, admin) | **Works locally and in tests.** Needs your Vercel + Stripe setup (YOUR-STEPS.md, Part A) |
| 2. Mac app engine | in progress |
| 3. Mac `.dmg` built by GitHub Actions | not started |
| 4. Polish | not started |

## Website: what works

- **Home page:** hero video with live timecode, the RAW → EDIT drag slider, three demos (Tokyo, Italy, New York), how it works, NZD pricing, FAQ and footer. Built for 375 px phones first. Videos only download when they scroll into view.
- **Order form:** every field from the brief. Uploads go straight from the browser to Vercel Blob, two at a time, each with a progress bar. There are caps (40 files, 150 MB each, 400 MB total) and a link box for big batches. Error messages are written in your voice.
- **Payment:** Stripe Checkout in NZD.
  - If a customer cancels, their order is kept and they get a "try paying again" link.
  - Orders are marked paid by the webhook, and again by the thanks page checking Stripe directly.
- **Thanks page:** shows the order number and "i'll have it to you within 48 hours."
- **Admin page** (`/admin`, one password): orders split into to do / delivered / not paid.
  - Each order has a due-in countdown, every form field, and links to the clips (open, download, download one by one, or all as a .zip).
  - Buttons: mark delivered (and undo), delete clips.
  - Shows how much of the free 1 GB storage is in use.
- **Clean-up job:** runs daily. Deletes clips 30 days after upload, as the FAQ promises (3 days for unpaid orders).
- **Tests:**
  - 10 unit tests for the Stripe webhook, using real Stripe-signed test events.
  - 15 Playwright tests, run at phone and laptop sizes (30 runs). They cover every page, the form validation, uploads, the fake checkout, admin, the cancel/retry flow and the clean-up job.
  - All pass.

## Website: what I couldn't test here

This container can't reach vercel.com or use your accounts, so these parts are written against the official libraries but have only run for real in tests with stand-ins:

- **Real uploads to Vercel Blob** (both connection styles Vercel uses are supported). Your test order in YOUR-STEPS A6 is the real check.
- **Real Stripe checkout and webhook.** The webhook is tested with properly signed test events; your 4242 test order checks the rest.
- **The "download all (.zip)" button on big orders.** It streams, but Vercel's free plan stops a request after 5 minutes. For huge orders use "download one by one", or the customer's link.

## What you need to do

1. YOUR-STEPS.md **Part A** (merge, Stripe test key, Vercel, Blob store, webhook, test order).
2. Later: **Part B** (real demo videos), **Part C** (live payments), **Part D** (your domain).
