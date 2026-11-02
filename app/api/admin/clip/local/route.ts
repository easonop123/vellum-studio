import { isAdmin } from "@/lib/admin-auth";
import { getStore } from "@/lib/store";
import { FileOrderStore } from "@/lib/store/file";

/** Serves a clip from the local folder (only when Vercel Blob isn't connected). */
export async function GET(request: Request) {
  if (!(await isAdmin())) return Response.json({ error: "log in first" }, { status: 401 });
  const store = getStore();
  if (!(store instanceof FileOrderStore)) return Response.json({ error: "not available" }, { status: 404 });
  const url = new URL(request.url);
  const pathname = url.searchParams.get("p") ?? "";
  const stream = await store.clipStream(pathname);
  if (!stream) return Response.json({ error: "clip not found" }, { status: 404 });
  const file = pathname.split("/").pop() ?? "clip";
  const disposition = url.searchParams.get("download") === "1" ? "attachment" : "inline";
  return new Response(stream, {
    headers: {
      "content-type": "application/octet-stream",
      "content-disposition": `${disposition}; filename="${file.replace(/"/g, "")}"`,
    },
  });
}
