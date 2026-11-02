import { randomBytes } from "node:crypto";
import { isAcceptedClipName, MAX_FILE_BYTES, safeFileName } from "@/lib/limits";
import { getStore } from "@/lib/store";
import { FileOrderStore } from "@/lib/store/file";

/**
 * Local stand-in for Vercel Blob client uploads, used only when no Blob store
 * is connected (local runs and tests). Streams the file to .data/uploads.
 */
export async function POST(request: Request) {
  const store = getStore();
  if (!(store instanceof FileOrderStore)) return Response.json({ error: "not available" }, { status: 404 });

  const url = new URL(request.url);
  const draft = url.searchParams.get("draft") ?? "";
  const name = url.searchParams.get("name") ?? "";
  if (!/^[a-zA-Z0-9-]{8,64}$/.test(draft)) return Response.json({ error: "bad upload" }, { status: 400 });
  if (!isAcceptedClipName(name)) return Response.json({ error: "only video and photo files" }, { status: 400 });
  const declared = Number(request.headers.get("content-length") ?? "0");
  if (declared > MAX_FILE_BYTES) return Response.json({ error: "that file is too big" }, { status: 413 });
  if (!request.body) return Response.json({ error: "empty upload" }, { status: 400 });

  const pathname = `clips/${draft}/${randomBytes(4).toString("hex")}-${safeFileName(name)}`;
  const size = await store.saveClip(pathname, request.body);
  if (size > MAX_FILE_BYTES) {
    await store.deleteClips([pathname]);
    return Response.json({ error: "that file is too big" }, { status: 413 });
  }
  const contentType = request.headers.get("content-type") ?? "application/octet-stream";
  return Response.json({ pathname, url: pathname, size, contentType });
}
