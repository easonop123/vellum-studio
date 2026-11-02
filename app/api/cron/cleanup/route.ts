import { getStore } from "@/lib/store";

const DAY = 24 * 60 * 60 * 1000;
const KEEP_PAID_DAYS = 30;
const KEEP_UNPAID_DAYS = 3;

/**
 * Runs once a day (vercel.json). Deletes clips 30 days after upload, as the
 * FAQ promises, and clips from orders that were never paid after 3 days, to
 * stay inside the free Blob storage.
 */
export async function GET(request: Request) {
  const secret = process.env.CRON_SECRET;
  if (!secret || request.headers.get("authorization") !== `Bearer ${secret}`) {
    return Response.json({ error: "unauthorised" }, { status: 401 });
  }
  const store = getStore();
  const orders = await store.list();
  const paidDrafts = new Set(orders.filter((o) => o.status !== "unpaid" && o.draftId).map((o) => o.draftId!));
  const now = Date.now();

  const doomed: string[] = [];
  for (const clip of await store.listClips()) {
    const age = now - clip.uploadedAt.getTime();
    const draft = clip.pathname.split("/")[1] ?? "";
    if (age > KEEP_PAID_DAYS * DAY || (age > KEEP_UNPAID_DAYS * DAY && !paidDrafts.has(draft))) doomed.push(clip.pathname);
  }
  if (doomed.length) await store.deleteClips(doomed);

  const gone = new Set(doomed);
  let marked = 0;
  for (const order of orders) {
    if (order.clipsDeletedAt || order.uploads.length === 0) continue;
    if (order.uploads.every((u) => gone.has(u.pathname))) {
      await store.markClipsDeleted(order.id);
      marked++;
    }
  }
  return Response.json({ deleted: doomed.length, ordersCleared: marked });
}
