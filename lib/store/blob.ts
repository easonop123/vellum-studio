import { del, get, head, issueSignedToken, list, presignUrl, put, type ListBlobResultBlob } from "@vercel/blob";
import {
  deriveStatus,
  type OrderRecord,
  type OrderStore,
  type OrderView,
  type PaymentInfo,
  type StoredClip,
} from "./types";

/**
 * Orders as small immutable JSON files in Vercel Blob (no database account):
 *   orders/<id>/order-<random>.json      the form, written once
 *   orders/<id>/paid-<random>.json       added when paid
 *   orders/<id>/delivered-<random>.json  added when you mark it delivered (deleted to undo)
 *   orders/<id>/clips-deleted-<random>.json
 * Nothing is ever overwritten, so CDN caching can't serve stale state and
 * two webhooks arriving at once can't clobber each other.
 */
const ACCESS: "public" | "private" = process.env.BLOB_ACCESS === "public" ? "public" : "private";

type MarkerKind = "order" | "paid" | "delivered" | "clips-deleted";

function markerKind(pathname: string): MarkerKind | null {
  const file = pathname.split("/").pop() ?? "";
  if (file.startsWith("clips-deleted")) return "clips-deleted";
  if (file.startsWith("order")) return "order";
  if (file.startsWith("paid")) return "paid";
  if (file.startsWith("delivered")) return "delivered";
  return null;
}

// Order JSON never changes once written, so it's safe to keep in memory.
const jsonCache = new Map<string, unknown>();

async function readJson<T>(blob: Pick<ListBlobResultBlob, "url" | "pathname">): Promise<T | null> {
  if (jsonCache.has(blob.url)) return jsonCache.get(blob.url) as T;
  const result = await get(blob.url, { access: ACCESS });
  if (!result || result.statusCode !== 200 || !result.stream) return null;
  const parsed = JSON.parse(await new Response(result.stream).text()) as T;
  jsonCache.set(blob.url, parsed);
  return parsed;
}

async function listAll(prefix: string): Promise<ListBlobResultBlob[]> {
  const out: ListBlobResultBlob[] = [];
  let cursor: string | undefined;
  do {
    const page = await list({ prefix, cursor, limit: 1000 });
    out.push(...page.blobs);
    cursor = page.hasMore ? page.cursor : undefined;
  } while (cursor);
  return out;
}

async function putJson(pathname: string, data: unknown) {
  await put(pathname, JSON.stringify(data), {
    access: ACCESS,
    addRandomSuffix: true,
    contentType: "application/json",
  });
}

// One signed token covers the whole store for reads; each URL is still signed
// for a single pathname, so a leaked link only opens that one file.
let signed: { delegationToken: string; clientSigningToken: string; validUntil: number } | null = null;

async function signingToken() {
  if (!signed || signed.validUntil - Date.now() < 5 * 60 * 1000) {
    signed = await issueSignedToken({ operations: ["get"], validUntil: Date.now() + 60 * 60 * 1000 });
  }
  return signed;
}

export class BlobOrderStore implements OrderStore {
  readonly kind = "blob" as const;
  readonly uploadMode = "blob" as const;

  private async build(id: string, blobs: ListBlobResultBlob[]): Promise<OrderView | null> {
    const orderBlob = blobs.find((b) => markerKind(b.pathname) === "order");
    if (!orderBlob) return null;
    const record = await readJson<OrderRecord>(orderBlob);
    if (!record) return null;
    const paidBlob = blobs
      .filter((b) => markerKind(b.pathname) === "paid")
      .sort((a, b) => a.uploadedAt.getTime() - b.uploadedAt.getTime())[0];
    const deliveredBlob = blobs.find((b) => markerKind(b.pathname) === "delivered");
    const deletedBlob = blobs.find((b) => markerKind(b.pathname) === "clips-deleted");
    const payment = paidBlob ? ((await readJson<PaymentInfo>(paidBlob)) ?? undefined) : undefined;
    return {
      ...record,
      id,
      status: deriveStatus(Boolean(paidBlob), Boolean(deliveredBlob)),
      payment,
      deliveredAt: deliveredBlob?.uploadedAt.toISOString(),
      clipsDeletedAt: deletedBlob?.uploadedAt.toISOString(),
    };
  }

  async create(record: OrderRecord) {
    await putJson(`orders/${record.id}/order.json`, record);
  }

  async get(id: string) {
    if (!/^VS-[A-Z0-9]{4,8}$/.test(id)) return null;
    const blobs = await listAll(`orders/${id}/`);
    return this.build(id, blobs);
  }

  async list() {
    const blobs = await listAll("orders/");
    const byId = new Map<string, ListBlobResultBlob[]>();
    for (const b of blobs) {
      const id = b.pathname.split("/")[1];
      if (!id) continue;
      const group = byId.get(id) ?? [];
      group.push(b);
      byId.set(id, group);
    }
    const ids = [...byId.keys()];
    const views: OrderView[] = [];
    // A few at a time keeps us well under Blob's rate limits.
    for (let i = 0; i < ids.length; i += 8) {
      const batch = await Promise.all(ids.slice(i, i + 8).map((id) => this.build(id, byId.get(id)!)));
      for (const v of batch) if (v) views.push(v);
    }
    return views.sort((a, b) => b.createdAt.localeCompare(a.createdAt));
  }

  async markPaid(id: string, info: PaymentInfo) {
    const blobs = await listAll(`orders/${id}/`);
    if (!blobs.some((b) => markerKind(b.pathname) === "order")) return "missing" as const;
    if (blobs.some((b) => markerKind(b.pathname) === "paid")) return "already" as const;
    await putJson(`orders/${id}/paid.json`, info);
    return "marked" as const;
  }

  async setDelivered(id: string, delivered: boolean) {
    const blobs = await listAll(`orders/${id}/`);
    const existing = blobs.filter((b) => markerKind(b.pathname) === "delivered");
    if (delivered && existing.length === 0) await putJson(`orders/${id}/delivered.json`, { at: new Date().toISOString() });
    if (!delivered && existing.length > 0) await del(existing.map((b) => b.url));
  }

  async markClipsDeleted(id: string) {
    await putJson(`orders/${id}/clips-deleted.json`, { at: new Date().toISOString() });
  }

  async clipExists(pathname: string) {
    try {
      const meta = await head(pathname);
      return { size: meta.size };
    } catch {
      return null;
    }
  }

  async clipUrl(pathname: string, opts?: { download?: boolean }) {
    const token = await signingToken();
    const { presignedUrl } = await presignUrl(token, { operation: "get", pathname, access: ACCESS });
    if (!opts?.download) return presignedUrl;
    const url = new URL(presignedUrl);
    url.searchParams.set("download", "1");
    return url.toString();
  }

  async clipStream(pathname: string) {
    const result = await get(pathname, { access: ACCESS });
    if (!result || result.statusCode !== 200) return null;
    return result.stream;
  }

  async listClips(): Promise<StoredClip[]> {
    const blobs = await listAll("clips/");
    return blobs.map((b) => ({ pathname: b.pathname, size: b.size, uploadedAt: b.uploadedAt }));
  }

  async deleteClips(pathnames: string[]) {
    for (let i = 0; i < pathnames.length; i += 100) {
      await del(pathnames.slice(i, i + 100));
    }
  }
}

export const BLOB_ACCESS = ACCESS;
