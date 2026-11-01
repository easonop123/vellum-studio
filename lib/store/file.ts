import { promises as fs, createReadStream } from "node:fs";
import path from "node:path";
import { Readable } from "node:stream";
import {
  deriveStatus,
  type OrderRecord,
  type OrderStore,
  type OrderView,
  type PaymentInfo,
  type StoredClip,
} from "./types";

/**
 * Local stand-in for Vercel Blob, used when BLOB_READ_WRITE_TOKEN is not set
 * (local runs and the automated tests). Same layout as the Blob version:
 *   orders/<id>/order.json, paid.json, delivered.json, clips-deleted.json
 *   uploads/clips/<draftId>/<file>
 */
export class FileOrderStore implements OrderStore {
  readonly kind = "file" as const;
  readonly uploadMode = "local" as const;

  constructor(private readonly root: string) {}

  private orderDir(id: string) {
    return path.join(this.root, "orders", id);
  }

  private async readJson<T>(file: string): Promise<T | null> {
    try {
      return JSON.parse(await fs.readFile(file, "utf8")) as T;
    } catch {
      return null;
    }
  }

  private async writeJson(file: string, data: unknown) {
    await fs.mkdir(path.dirname(file), { recursive: true });
    await fs.writeFile(file, JSON.stringify(data, null, 2), { flag: "wx" }).catch(async (err: NodeJS.ErrnoException) => {
      if (err.code !== "EEXIST") throw err;
    });
  }

  async create(record: OrderRecord) {
    const file = path.join(this.orderDir(record.id), "order.json");
    await fs.mkdir(path.dirname(file), { recursive: true });
    await fs.writeFile(file, JSON.stringify(record, null, 2), { flag: "wx" });
  }

  async get(id: string): Promise<OrderView | null> {
    if (!/^VS-[A-Z0-9]{4,8}$/.test(id)) return null;
    const dir = this.orderDir(id);
    const record = await this.readJson<OrderRecord>(path.join(dir, "order.json"));
    if (!record) return null;
    const payment = (await this.readJson<PaymentInfo>(path.join(dir, "paid.json"))) ?? undefined;
    const delivered = await this.readJson<{ at: string }>(path.join(dir, "delivered.json"));
    const clipsDeleted = await this.readJson<{ at: string }>(path.join(dir, "clips-deleted.json"));
    return {
      ...record,
      status: deriveStatus(Boolean(payment), Boolean(delivered)),
      payment,
      deliveredAt: delivered?.at,
      clipsDeletedAt: clipsDeleted?.at,
    };
  }

  async list(): Promise<OrderView[]> {
    let ids: string[] = [];
    try {
      ids = await fs.readdir(path.join(this.root, "orders"));
    } catch {
      return [];
    }
    const views = await Promise.all(ids.map((id) => this.get(id)));
    return views
      .filter((v): v is OrderView => v !== null)
      .sort((a, b) => b.createdAt.localeCompare(a.createdAt));
  }

  async markPaid(id: string, info: PaymentInfo) {
    const order = await this.get(id);
    if (!order) return "missing" as const;
    if (order.payment) return "already" as const;
    await this.writeJson(path.join(this.orderDir(id), "paid.json"), info);
    return "marked" as const;
  }

  async setDelivered(id: string, delivered: boolean) {
    const file = path.join(this.orderDir(id), "delivered.json");
    if (delivered) await this.writeJson(file, { at: new Date().toISOString() });
    else await fs.rm(file, { force: true });
  }

  async markClipsDeleted(id: string) {
    await this.writeJson(path.join(this.orderDir(id), "clips-deleted.json"), { at: new Date().toISOString() });
  }

  // ---- clips -------------------------------------------------------------

  /** Map a stored pathname (clips/<draft>/<file>) to a file on disk, refusing anything that escapes. */
  resolveClip(pathname: string): string | null {
    if (!pathname.startsWith("clips/") || pathname.includes("..")) return null;
    const full = path.join(this.root, "uploads", pathname);
    const base = path.join(this.root, "uploads", "clips") + path.sep;
    return full.startsWith(base) ? full : null;
  }

  async saveClip(pathname: string, body: ReadableStream<Uint8Array>): Promise<number> {
    const file = this.resolveClip(pathname);
    if (!file) throw new Error("bad path");
    await fs.mkdir(path.dirname(file), { recursive: true });
    const handle = await fs.open(file, "w");
    let size = 0;
    try {
      const reader = body.getReader();
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        size += value.byteLength;
        await handle.write(value);
      }
    } finally {
      await handle.close();
    }
    return size;
  }

  async clipExists(pathname: string) {
    const file = this.resolveClip(pathname);
    if (!file) return null;
    try {
      const stat = await fs.stat(file);
      return { size: stat.size };
    } catch {
      return null;
    }
  }

  async clipUrl(pathname: string, opts?: { download?: boolean }) {
    const params = new URLSearchParams({ p: pathname });
    if (opts?.download) params.set("download", "1");
    return `/api/admin/clip/local?${params.toString()}`;
  }

  async clipStream(pathname: string) {
    const file = this.resolveClip(pathname);
    if (!file) return null;
    try {
      await fs.access(file);
    } catch {
      return null;
    }
    return Readable.toWeb(createReadStream(file)) as ReadableStream<Uint8Array>;
  }

  async listClips(): Promise<StoredClip[]> {
    const out: StoredClip[] = [];
    const base = path.join(this.root, "uploads", "clips");
    let drafts: string[] = [];
    try {
      drafts = await fs.readdir(base);
    } catch {
      return out;
    }
    for (const draft of drafts) {
      const files = await fs.readdir(path.join(base, draft)).catch(() => [] as string[]);
      for (const name of files) {
        const stat = await fs.stat(path.join(base, draft, name));
        out.push({ pathname: `clips/${draft}/${name}`, size: stat.size, uploadedAt: stat.mtime });
      }
    }
    return out;
  }

  async deleteClips(pathnames: string[]) {
    for (const p of pathnames) {
      const file = this.resolveClip(p);
      if (file) await fs.rm(file, { force: true });
    }
  }
}
