# Your steps

Everything here is clicking in a browser. No Terminal. One action per step.
Menus on Vercel and Stripe move around now and then: if a button name is slightly different, look for the closest match.

- **Part A: put the website online** (about 25 minutes)
- **Part B: put your real videos on the site**
- **Part C: go live with real payments** (later)
- **Part D: connect your own domain** (later)
- **Part E: the Mac app** (see the end of this file)

---

## Part A: put the website online

### A1. Merge my work into `main`

1. Open **github.com/easonop123/vellum-studio**.
2. Click **Pull requests** (top of the page).
3. Click **New pull request**.
4. In the **compare:** dropdown, pick **claude/session-cloud-location-2erb64**.
5. Click **Create pull request**, then **Create pull request** again.
6. Click **Merge pull request**.
7. Click **Confirm merge**.

### A2. Get your Stripe test key

1. Go to **dashboard.stripe.com** and sign up (or log in).
2. Make sure you're in **test mode**: the **Test mode** switch (top right) is on, or you've picked your **Sandbox** from the account menu (top left).
3. Click **Developers** (bottom left), then **API keys**.
4. Next to **Secret key**, click **Reveal test key**.
5. Copy the key (it starts with `sk_test_`). Keep this tab open.

### A3. Put the site on Vercel

1. Go to **vercel.com** and click **Sign Up** (or **Log In**).
2. Click **Continue with GitHub** and allow access.
3. Click **Add New…**, then **Project**.
4. Next to **vellum-studio**, click **Import**.
   - Not in the list? Click **Adjust GitHub App Permissions**, tick **vellum-studio**, save, and come back.
5. Open the **Environment Variables** section and add these three, one at a time (type the name in **Key**, paste the value in **Value**, then click **Add More** for the next one):

   | Key | Value |
   | --- | --- |
   | `STRIPE_SECRET_KEY` | the `sk_test_…` key from A2 |
   | `ADMIN_PASSWORD` | a password you make up. It opens your orders page |
   | `CRON_SECRET` | any 30+ random letters and numbers (mash the keyboard) |

6. Leave the **Stripe** box under **Optional Integrations** alone (it connects Stripe a different way; your key is already in).
7. Click **Deploy** and wait about two minutes. Greyed out? One variable row is half filled in: give it a name and a value, or remove it.
8. Click **Continue to Dashboard**. Your site address is shown under **Domains** (something like `vellum-studio-abc.vercel.app`). Write it down.

### A4. Add storage for uploaded clips

1. In your Vercel project, click the **Storage** tab.
2. Click **Create Database** (or **Create**).
3. Choose **Blob**, then **Continue**.
4. Name it `vellum-clips`.
5. Set **Access** to **Private**. (This matters: it can't be changed later.)
6. Click **Create**.
7. When it asks which project to connect, choose **vellum-studio**, leave every environment ticked, and click **Connect**.
8. Click the **Deployments** tab.
9. On the top deployment, click the **⋯** button, then **Redeploy**, then **Redeploy** again.

### A5. Tell Stripe where to send payment confirmations

1. Back in Stripe (still test mode), click **Developers**, then **Webhooks**.
2. Click **Add endpoint**. (Newer dashboards: **Add destination**, choose **Webhook endpoint**.)
3. In **Endpoint URL**, type your site address plus `/api/stripe/webhook`, e.g. `https://vellum-studio-abc.vercel.app/api/stripe/webhook`.
4. Click **Select events**, search for `checkout.session`, and tick **checkout.session.completed** and **checkout.session.async_payment_succeeded**.
5. Click **Add endpoint** (or **Create destination**).
6. On the endpoint's page, under **Signing secret**, click **Reveal** and copy it (starts with `whsec_`).
7. In Vercel, open your project's **Settings** tab, then **Environment Variables**.
8. Add Key `STRIPE_WEBHOOK_SECRET` with the `whsec_…` value, and click **Save**.
9. Go to **Deployments**, click **⋯** on the top one, then **Redeploy**, then **Redeploy**.

### A6. Place a test order

1. Open your site on your phone.
2. Tap **send me your clips**.
3. Fill in the form, upload one or two short clips, and tap **pay $5 nzd**.
4. On Stripe's page, use card **4242 4242 4242 4242**, expiry **12/34**, CVC **123**, any name.
5. Tap **Pay**. You should land on a page with an order number like `VS-7K3QX`.
6. On your laptop, open your site address plus `/admin` and type your `ADMIN_PASSWORD`.
7. Your test order should be under **to do**, with your clips. Click **mark delivered** to try it.

Something wrong? See **If something breaks** at the bottom.

---

## Part B: put your real videos on the site

The site shows placeholder videos until you swap them. Use these exact file names, and the new ones replace the placeholders automatically:

| File | What it is |
| --- | --- |
| `hero.mp4` + `hero.jpg` | the big video at the top (vertical) |
| `tokyo.mp4` + `tokyo.jpg` | demo 1 (vertical) |
| `italy.mp4` + `italy.jpg` | demo 2 (vertical) |
| `new-york.mp4` + `new-york.jpg` | demo 3 (vertical) |
| `raw.mp4` | one clip straight off a phone, ungraded |
| `edit.mp4` + `edit.jpg` | the same clip from your finished edit, same length (for the before/after slider) |

The `.jpg` is a still frame from the video (a screenshot is fine). Keep each video under 5 MB so the site loads fast: export at 720×1280. The vertical "post this" files from the Mac app work well.

1. On GitHub, open the repo, then the **public** folder, then **demos**.
2. Click **Add file**, then **Upload files**.
3. Drag your files in.
4. Click **Commit changes**.
5. Vercel puts the new version live by itself in about a minute.

To change a demo's title or clip count, open **content/demos.json** on GitHub, click the pencil icon, edit the words, and click **Commit changes**.

Your Instagram link is a placeholder: open **content/site.json**, click the pencil, change the `instagram` line's `handle` and `url`, and commit. Prices live in the same file (`500` means $5.00).

---

## Part C: go live with real payments (when you're ready)

1. In Stripe, click **Activate payments** (or **Complete your profile**) and fill in your details and NZ bank account.
2. Switch **Test mode** off (or leave your Sandbox).
3. Click **Developers**, then **API keys**, and copy the live **Secret key** (starts with `sk_live_`).
4. Click **Developers**, then **Webhooks**, and add the same endpoint again (A5 steps 2–6) in live mode. Copy its new `whsec_…`.
5. In Vercel: **Settings**, then **Environment Variables**. Click **⋯** next to `STRIPE_SECRET_KEY`, choose **Edit**, paste the `sk_live_…` key, and **Save**.
6. Do the same for `STRIPE_WEBHOOK_SECRET` with the live `whsec_…`.
7. Redeploy (**Deployments**, then **⋯**, then **Redeploy**).
8. Place one real $5 order with your own card, then refund it in Stripe: **Payments**, click the payment, then **Refund**.

---

## Part D: connect your own domain (GitHub Student Pack)

1. Go to **education.github.com/pack**, find the free domain offer (Namecheap `.me` or Name.com), and claim a domain like `vellumstudio.me`.
2. In Vercel, open your project, then **Settings**, then **Domains**.
3. Type your domain and click **Add**. When it asks, choose the option that adds `www` too.
4. Vercel shows the DNS records you need (usually an **A** record and a **CNAME** record). Leave this tab open.
5. At your domain company (e.g. Namecheap), open **Domain List**, then **Manage** next to your domain, then **Advanced DNS**.
6. Delete any existing "parking page" records.
7. Click **Add New Record** and copy in each record exactly as Vercel shows it (type, host, value).
8. Wait 10–60 minutes. Vercel's Domains page turns green (**Valid Configuration**).
9. Optional: in Stripe, edit your webhook endpoint's URL to use the new domain. The old `vercel.app` address keeps working, so you can skip this.

---

## Part E: the Mac app (Vellum Editor)

GitHub builds the app for you every time `main` changes (after A1). It takes about 10 minutes.

### E1. Download it

1. Open **github.com/easonop123/vellum-studio**.
2. On the right, click **Releases**.
3. Under the newest **Vellum Editor** release, click **Vellum-Editor.dmg**. It downloads to your Downloads folder.

### E2. Install it

1. Double-click **Vellum-Editor.dmg** in Downloads.
2. In the window that opens, drag **Vellum Editor** onto the **Applications** folder.
3. Close the window.

### E3. Open it the first time

The app isn't signed with a paid Apple developer account, so macOS asks once.

1. Open **Finder**, then **Applications**.
2. Right-click **Vellum Editor** and choose **Open**.
3. Click **Open** in the warning.
4. No **Open** button? Click **Done**, open **System Settings**, then **Privacy & Security**, scroll down to the message about Vellum Editor, click **Open Anyway**, and type your Mac password.
5. From now on it opens with a normal double-click.

### E4. Make a test edit

1. Put 10–40 clips in one folder (for example a folder called `Tokyo` on your Desktop).
2. Drag that folder onto **Drop the folder of clips here**.
3. Drag the song file (mp3, m4a or wav) onto **Drop the song here**. After a few seconds you'll see the BPM, the drop time, and a waveform with a red line on the drop.
4. Click **▶ hear the drop**. If the red line isn't on the big moment, move it with **◀ beat** / **beat ▶** (or a whole **bar**), then listen again. If the BPM looks half or double, click **×2** or **÷2**.
5. Type the title (the city or trip name). Pick **Short** or **Long** and a **Look**.
6. Click **Make edit**. A short edit takes about 2–4 minutes; the bar shows the time left.
7. Click **Open folder**. Next to your clips there's a new folder **Vellum Edit - (title)** with:
   - `(title) - vertical (post this).mp4`: post this one and add the song in TikTok or Instagram.
   - `(title) - vertical (preview with song).mp4`: send this to the customer so they hear it with the song.
   - the same two in 16x9, for YouTube.
   - `review.html`: every cut, every clip used, and every clip thrown out (and why).

### E5. Extras

- **Hook versions:** type two short lines in HOOK 2 (and 3, 4 if you want) and click **Make hook versions**. You get extra vertical files with that text over the start.
- **Swap a shot:** click **Swap a shot…**, pick the shot number on the left (the numbers match `review.html`), pick a clip on the right, and click **Swap and re-render**.
- **Settings:**
  - **Sound effects folder:** use your own sounds. Name the files `click`, `click_loud`, `shutter1`–`shutter4`, `riser`, `whoosh`, `impact`, `flash`, `ring` and `glitch` (any of .wav, .mp3, .aif).
  - **LUT:** for DJI D-Log M footage. Download DJI's Rec.709 `.cube` LUT for that drone, choose it, and set **Apply the LUT to** **DJI clips only**.
- **Never reuse a clip:** with few clips, the app reuses a different moment of a long clip to keep the cuts fast (never the same footage, never side by side). Tick this box if you'd rather have fewer cuts.

---

## If something breaks

- **Order page says "storage isn't connected yet"**: do A4, including the redeploy.
- **Order page says "payments aren't switched on yet"**: `STRIPE_SECRET_KEY` is missing. Add it (A3 step 5, or **Settings → Environment Variables**) and redeploy.
- **Uploads fail straight away**: the Blob store was probably created as **Public**. Either make a new **Private** store (A4) and connect that one, or add an environment variable `BLOB_ACCESS` with value `public` and redeploy.
- **Order paid but shows "not paid" in admin**: check the webhook (A5). Stripe's endpoint page lists each delivery and whether it worked. The thanks page also checks with Stripe directly, so this is rare.
- **Admin page says "set an ADMIN_PASSWORD"**: add it in **Settings → Environment Variables**, then redeploy.
- **Storage filling up**: free Blob storage is 1 GB. After delivering an order, click **delete clips** on it. Clips are deleted automatically 30 days after upload anyway (3 days if the order was never paid). For big orders, ask customers to use the link box instead of uploading.
- **Mac app says something went wrong**: the message names the problem. Full details are saved in `vellum-editor.log`: in Finder press **Shift+Cmd+G**, type `~/Library/Application Support/Vellum Editor` and press Return. Send me that file.
- **No release on GitHub yet**: open the repo's **Actions** tab, then **Vellum Editor (Mac app)**. A green tick means it's done; a red cross means the build failed (send me the link).
