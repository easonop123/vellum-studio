import { expect, test, type Page } from "@playwright/test";
import path from "node:path";

const ADMIN_PASSWORD = "test-admin-password";
const SAMPLE_CLIP = path.join(__dirname, "..", "..", "public", "demos", "raw.mp4");

async function noSidewaysScroll(page: Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow, "page should not scroll sideways").toBeLessThanOrEqual(0);
}

async function fillBasics(page: Page, overrides: { email?: string } = {}) {
  await page.getByLabel("name", { exact: true }).fill("Mia Test");
  await page.getByLabel("email").fill(overrides.email ?? "mia@example.com");
  await page.getByLabel(/instagram or tiktok handle/).fill("@mia.travels");
  await page.getByLabel("song", { exact: true }).fill("a song i like - some artist");
  await page.getByLabel(/start the edit at/).fill("0:45");
  await page.getByRole("button", { name: "cinematic" }).click();
  await page.getByLabel(/notes/).fill("title it TOKYO please");
}

async function adminLogin(page: Page) {
  await page.goto("/admin");
  await page.getByLabel("password").fill(ADMIN_PASSWORD);
  await page.getByRole("button", { name: "open orders" }).click();
  await expect(page.getByRole("heading", { name: "orders", level: 1 })).toBeVisible();
}

test.describe("home page", () => {
  test("shows every section and links to the order form", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { level: 1 })).toContainText("send me your clips");
    const hero = page.locator("video").first();
    await expect(hero).toHaveAttribute("autoplay", "");
    await expect(hero).toHaveJSProperty("muted", true);
    await expect(hero).toHaveAttribute("loop", "");
    await expect(page.getByText("RAW → EDIT")).toBeVisible();
    await expect(page.getByRole("slider", { name: /raw clip and the edit/ })).toBeVisible();
    await expect(page.getByRole("heading", { name: "recent edits" })).toBeVisible();
    for (const city of ["tokyo", "italy", "new york"]) {
      await expect(page.locator("figcaption").filter({ hasText: new RegExp(city, "i") })).toHaveCount(1);
    }
    await expect(page.getByRole("heading", { name: "how it works" })).toBeVisible();
    await expect(page.locator("ol > li")).toHaveCount(3);
    await expect(page.getByRole("heading", { name: "pricing" })).toBeVisible();
    await expect(page.getByText("$5", { exact: true })).toBeVisible();
    await expect(page.getByText("$10", { exact: true })).toBeVisible();
    await expect(page.getByText("00:00:30:00")).toBeVisible();
    await expect(page.getByText("00:01:00:00")).toBeVisible();
    await expect(page.locator("details")).toHaveCount(5);
    await page.getByText("what happens to my clips?").click();
    await expect(page.getByText(/deleted 30 days after you send them/)).toBeVisible();
    await expect(page.getByRole("link", { name: "@vellumstudio.edits" })).toHaveAttribute("href", /tiktok\.com\/@vellumstudio\.edits/);
    await expect(page.getByRole("link", { name: "@vellumstudioedits" })).toHaveAttribute("href", /youtube\.com\/@vellumstudioedits/);
    await expect(page.locator('a[href="mailto:vellumstudio.edits@gmail.com"]')).toBeVisible();
    await noSidewaysScroll(page);

    await page.getByRole("link", { name: "send me your clips" }).first().click();
    await expect(page).toHaveURL(/\/order$/);
    await expect(page.getByRole("heading", { name: "send me your clips", level: 1 })).toBeVisible();
  });

  test("demo videos don't download until they're on screen", async ({ page }) => {
    await page.goto("/");
    const demo = page.locator('video[aria-label="demo edit: italy"]');
    await expect(demo).toHaveAttribute("preload", "none");
    await expect(demo).toHaveAttribute("poster", /italy\.jpg/);
    await expect(demo).not.toHaveAttribute("src", /.+/);
    await demo.scrollIntoViewIfNeeded();
    await expect(demo).toHaveAttribute("src", /italy\.mp4/);
  });

  test("the before/after line moves with the keyboard", async ({ page }) => {
    await page.goto("/");
    const slider = page.getByRole("slider", { name: /raw clip and the edit/ });
    await slider.focus();
    await expect(slider).toHaveAttribute("aria-valuenow", "50");
    await page.keyboard.press("ArrowRight");
    await expect(slider).toHaveAttribute("aria-valuenow", "55");
    await page.keyboard.press("Home");
    await expect(slider).toHaveAttribute("aria-valuenow", "0");
  });

  test("pricing buttons preselect the package", async ({ page }) => {
    await page.goto("/order?package=long");
    await expect(page.getByRole("radio", { name: /long/ })).toBeChecked();
    await expect(page.getByRole("button", { name: /pay \$10 nzd/ })).toBeVisible();
  });
});

test.describe("order form validation", () => {
  test("an empty form explains what's missing", async ({ page }) => {
    await page.goto("/order");
    await page.getByRole("button", { name: /pay \$5 nzd/ }).click();
    await expect(page.getByText("i need your name")).toBeVisible();
    await expect(page.getByText("i need your email so i can send you the edit")).toBeVisible();
    await expect(page.getByText("tell me the song: a name or a link")).toBeVisible();
    await expect(page.getByText("add your clips: upload them or paste a link")).toBeVisible();
    await expect(page.getByLabel("name", { exact: true })).toHaveAttribute("aria-invalid", "true");
    await expect(page).toHaveURL(/\/order$/);
    await noSidewaysScroll(page);
  });

  test("bad email, bad start time and bad link are caught", async ({ page }) => {
    await page.goto("/order");
    await fillBasics(page, { email: "mia@nowhere" });
    await page.getByLabel(/start the edit at/).fill("45 seconds in");
    await page.getByLabel("or paste a link").fill("my google drive");
    await page.getByRole("button", { name: /pay \$5 nzd/ }).click();
    await expect(page.getByText("that email doesn't look right. check for typos")).toBeVisible();
    await expect(page.getByText("write it as minutes:seconds, like 0:45")).toBeVisible();
    await expect(page.getByText(/that link doesn't look right/)).toBeVisible();
    await expect(page).toHaveURL(/\/order$/);
  });

  test("files that aren't videos or photos are refused", async ({ page }) => {
    await page.goto("/order");
    await page.locator("#files").setInputFiles({ name: "notes.txt", mimeType: "text/plain", buffer: Buffer.from("hello") });
    await expect(page.getByText("notes.txt isn't a video or photo.")).toBeVisible();
    await expect(page.locator('[aria-label="your uploads"] li')).toHaveCount(0);
  });

  test("the server re-checks everything, even if the browser is bypassed", async ({ request }) => {
    const res = await request.post("/api/orders", { data: { name: "", email: "nope", package: "huge", song: "" } });
    expect(res.status()).toBe(400);
    const body = await res.json();
    expect(Object.keys(body.errors)).toEqual(expect.arrayContaining(["name", "email", "package", "song"]));
    const forged = await request.post("/api/orders", {
      data: {
        name: "x",
        email: "x@example.com",
        package: "short",
        song: "s",
        draftId: "abcdefgh-1234",
        uploads: [{ pathname: "clips/someone-else/file.mp4", url: "x", name: "file.mp4", size: 10 }],
      },
    });
    expect(forged.status()).toBe(400);
    expect((await forged.json()).errors.clips).toMatch(/didn't come from this form/);
  });
});

test.describe("ordering", () => {
  test("link order → test checkout → thanks → shows in admin → delivered", async ({ page }) => {
    await page.goto("/order");
    await fillBasics(page);
    await page.getByRole("radio", { name: /long/ }).check({ force: true });
    await page.getByLabel("or paste a link").fill("https://drive.google.com/drive/folders/test123");
    await expect(page.getByTestId("checkout-note")).toHaveText("test checkout: no real payment is taken.");
    await page.getByRole("button", { name: /pay \$10 nzd/ }).click();

    await expect(page).toHaveURL(/\/fake-checkout\?order=VS-/);
    await expect(page.getByText("Long edit (up to 60 s)")).toBeVisible();
    await page.getByRole("button", { name: "complete test payment" }).click();

    await expect(page).toHaveURL(/\/thanks\?order=VS-/);
    const orderId = (await page.getByTestId("order-number").textContent())!.trim();
    expect(orderId).toMatch(/^VS-[A-Z0-9]{5}$/);
    await expect(page.getByText("i'll have it to you within 48 hours.")).toBeVisible();
    await expect(page.getByRole("heading", { name: "got it, mia." })).toBeVisible();
    await expect(page.getByTestId("payment-pending")).toHaveCount(0);

    await adminLogin(page);
    const card = page.locator(`article#${orderId}`);
    await expect(card).toHaveAttribute("data-status", "paid");
    await expect(card).toContainText("long edit, $10 NZD");
    await expect(card).toContainText("a song i like - some artist");
    await expect(card).toContainText("from 0:45");
    await expect(card).toContainText("cinematic");
    await expect(card).toContainText("title it TOKYO please");
    await expect(card.getByRole("link", { name: /drive\.google\.com/ })).toHaveAttribute("href", "https://drive.google.com/drive/folders/test123");
    await expect(card.getByTestId("order-status")).toContainText(/due in/);

    await card.getByRole("button", { name: "mark delivered" }).click();
    await expect(page.locator(`article#${orderId}`)).toHaveAttribute("data-status", "delivered");
    await page.locator(`article#${orderId}`).getByRole("button", { name: "undo delivered" }).click();
    await expect(page.locator(`article#${orderId}`)).toHaveAttribute("data-status", "paid");
  });

  test("upload order: progress bar, upload, pay, then download from admin", async ({ page }) => {
    await page.goto("/order");
    await fillBasics(page, { email: "uploader@example.com" });
    await page.locator("#files").setInputFiles([SAMPLE_CLIP, path.join(__dirname, "..", "..", "public", "demos", "edit.mp4")]);
    const rows = page.locator('[aria-label="your uploads"] li');
    await expect(rows).toHaveCount(2);
    await expect(rows.nth(0)).toHaveAttribute("data-status", "done");
    await expect(rows.nth(1)).toHaveAttribute("data-status", "done");
    await expect(rows.nth(0).getByRole("progressbar")).toHaveAttribute("aria-valuenow", "100");
    await page.getByRole("button", { name: /pay \$5 nzd/ }).click();
    await page.getByRole("button", { name: "complete test payment" }).click();
    const orderId = (await page.getByTestId("order-number").textContent())!.trim();

    await adminLogin(page);
    const card = page.locator(`article#${orderId}`);
    await expect(card).toContainText("2 uploaded clips");
    const zip = await page.request.get(`/api/admin/orders/${orderId}/zip`);
    expect(zip.status()).toBe(200);
    expect(zip.headers()["content-type"]).toBe("application/zip");
    const bytes = await zip.body();
    expect(bytes.subarray(0, 2).toString()).toBe("PK");
    expect(bytes.includes(Buffer.from("raw.mp4"))).toBe(true);

    await card.getByText("show files").click();
    const download = card.getByRole("link", { name: "download" }).first();
    const res = await page.request.get((await download.getAttribute("href"))!);
    expect(res.status()).toBe(200);
    expect(res.headers()["content-disposition"]).toMatch(/^attachment/);

    // deliver, then delete the clips to free space
    await card.getByRole("button", { name: "mark delivered" }).click();
    await page.locator(`article#${orderId}`).getByRole("button", { name: "delete clips" }).click();
    await expect(page.locator(`article#${orderId}`)).toContainText(/deleted/);
  });

  test("cancelling payment keeps the order and offers to try again", async ({ page }) => {
    await page.goto("/order");
    await fillBasics(page, { email: "cancel@example.com" });
    await page.getByLabel("or paste a link").fill("https://we.tl/t-abc123");
    await page.getByRole("button", { name: /pay \$5 nzd/ }).click();
    await page.getByRole("link", { name: "cancel" }).click();
    await expect(page).toHaveURL(/\/order\?cancelled=VS-/);
    await expect(page.getByText(/your payment didn't go through, so nothing was charged/)).toBeVisible();
    await page.getByRole("link", { name: "try paying again" }).click();
    await expect(page).toHaveURL(/\/fake-checkout\?order=VS-/);
  });
});

test.describe("other pages", () => {
  test("thanks page for an unknown order", async ({ page }) => {
    await page.goto("/thanks?order=VS-22222");
    await expect(page.getByRole("heading", { name: "can't find that order" })).toBeVisible();
  });

  test("admin rejects a wrong password and blocks the API", async ({ page, request }) => {
    await page.goto("/admin");
    await page.getByLabel("password").fill("not-it");
    await page.getByRole("button", { name: "open orders" }).click();
    await expect(page.getByText(/wrong password/)).toBeVisible();
    expect((await request.get("/api/admin/orders/VS-22222/zip")).status()).toBe(401);
    expect((await request.get("/api/admin/clip?p=clips/x/y.mp4")).status()).toBe(401);
  });

  test("clean-up job needs its secret", async ({ request }) => {
    expect((await request.get("/api/cron/cleanup")).status()).toBe(401);
    const ok = await request.get("/api/cron/cleanup", { headers: { authorization: "Bearer test-cron-secret" } });
    expect(ok.status()).toBe(200);
    expect(await ok.json()).toMatchObject({ deleted: 0 });
  });

  test("webhook refuses unsigned calls", async ({ request }) => {
    const res = await request.post("/api/stripe/webhook", { data: { type: "checkout.session.completed" } });
    expect([400, 500]).toContain(res.status());
  });
});
