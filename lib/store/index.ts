import path from "node:path";
import { BlobOrderStore } from "./blob";
import { FileOrderStore } from "./file";
import { ConfigError, type OrderStore } from "./types";

export * from "./types";

let cached: OrderStore | null = null;

/** Vercel connects a store either with a read-write token or with a store id + OIDC. */
export function blobConnected(): boolean {
  return Boolean(process.env.BLOB_READ_WRITE_TOKEN || process.env.BLOB_STORE_ID);
}

/** How the browser uploads: classic client token, presigned URL, or the local stand-in. */
export function uploadMode(): "blob" | "blob-presigned" | "local" {
  if (process.env.BLOB_READ_WRITE_TOKEN) return "blob";
  if (process.env.BLOB_STORE_ID) return "blob-presigned";
  return "local";
}

/**
 * Vercel Blob when it's connected, otherwise a local folder. On Vercel there
 * is no writable folder, so a missing Blob store becomes a clear error
 * instead of a mystery crash.
 */
export function getStore(): OrderStore {
  if (cached) return cached;
  if (blobConnected()) {
    cached = new BlobOrderStore();
  } else if (process.env.VERCEL && !process.env.VELLUM_DATA_DIR) {
    throw new ConfigError(
      "storage isn't connected yet: create a Blob store in Vercel (Storage tab) and connect it to this project, then redeploy",
    );
  } else {
    cached = new FileOrderStore(process.env.VELLUM_DATA_DIR ?? path.join(process.cwd(), ".data"));
  }
  return cached;
}

/** Only for tests: point the store somewhere else. */
export function setStoreForTests(store: OrderStore | null) {
  cached = store;
}
