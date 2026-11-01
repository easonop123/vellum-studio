/**
 * Upload caps. Vercel Blob's free tier is 1 GB of storage and 2,000 write
 * operations a month, and going over locks the store for 30 days, so these
 * are deliberately tight. Big batches should come as a link instead.
 */
export const MAX_FILES = 40;
export const MAX_FILE_BYTES = 150 * 1024 * 1024; // 150 MB
export const MAX_TOTAL_BYTES = 400 * 1024 * 1024; // 400 MB per order
/** Files above this go up in 8 MB parts (each part is one Blob operation). */
export const MULTIPART_ABOVE_BYTES = 64 * 1024 * 1024;

export const ALLOWED_CONTENT_TYPES = [
  "video/*",
  "image/*",
  "application/octet-stream",
];

const VIDEO_EXT = ["mov", "mp4", "m4v", "avi", "mkv", "mts", "m2ts", "3gp", "webm", "insv", "lrv"];
const IMAGE_EXT = ["jpg", "jpeg", "png", "heic", "heif", "dng", "webp", "avif"];

export function extensionOf(name: string): string {
  const dot = name.lastIndexOf(".");
  return dot >= 0 ? name.slice(dot + 1).toLowerCase() : "";
}

export function isAcceptedClipName(name: string): boolean {
  const ext = extensionOf(name);
  return VIDEO_EXT.includes(ext) || IMAGE_EXT.includes(ext);
}

/** Best-guess content type when the browser leaves File.type empty (common for .mov on Windows). */
export function guessContentType(name: string, browserType: string): string {
  if (browserType) return browserType;
  const ext = extensionOf(name);
  if (ext === "mov") return "video/quicktime";
  if (ext === "mp4" || ext === "m4v") return "video/mp4";
  if (ext === "heic" || ext === "heif") return "image/heic";
  if (ext === "jpg" || ext === "jpeg") return "image/jpeg";
  if (ext === "png") return "image/png";
  if (VIDEO_EXT.includes(ext)) return "application/octet-stream";
  return "application/octet-stream";
}

/** Keep file names readable but safe as a storage path segment. */
export function safeFileName(name: string): string {
  const cleaned = name
    .normalize("NFKD")
    .replace(/[^\w.\- ]+/g, "")
    .replace(/\s+/g, "_")
    .replace(/_+/g, "_")
    .slice(-120);
  return cleaned || "clip";
}

function trimmed(value: number, digits: number): string {
  return value.toFixed(digits).replace(/\.0+$/, "").replace(/(\.\d*?)0+$/, "$1");
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${trimmed(bytes / (1024 * 1024), bytes < 10 * 1024 * 1024 ? 1 : 0)} MB`;
  return `${trimmed(bytes / (1024 * 1024 * 1024), 2)} GB`;
}
