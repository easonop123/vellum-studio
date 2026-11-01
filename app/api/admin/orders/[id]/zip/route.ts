import { downloadZip } from "client-zip";
import { isAdmin } from "@/lib/admin-auth";
import { isOrderId } from "@/lib/ids";
import { getStore } from "@/lib/store";

/**
 * All of an order's uploaded clips as one .zip, streamed (nothing is held in
 * memory). Very large orders can hit the hosting time limit; the admin page
 * also offers one-by-one downloads for those.
 */
export const maxDuration = 300;

export async function GET(_request: Request, ctx: RouteContext<"/api/admin/orders/[id]/zip">) {
  if (!(await isAdmin())) return Response.json({ error: "log in first" }, { status: 401 });
  const { id } = await ctx.params;
  if (!isOrderId(id)) return Response.json({ error: "bad order" }, { status: 400 });
  const store = getStore();
  const order = await store.get(id);
  if (!order) return Response.json({ error: "no such order" }, { status: 404 });
  if (order.uploads.length === 0) return Response.json({ error: "this order has no uploaded clips" }, { status: 404 });

  const used = new Set<string>();
  async function* files() {
    for (const clip of order!.uploads) {
      const stream = await store.clipStream(clip.pathname);
      if (!stream) continue;
      let name = clip.name;
      for (let n = 2; used.has(name); n++) name = clip.name.replace(/(\.[^.]*)?$/, `-${n}$1`);
      used.add(name);
      yield { name, input: stream, size: clip.size };
    }
  }

  const zip = downloadZip(files());
  return new Response(zip.body, {
    headers: {
      "content-type": "application/zip",
      "content-disposition": `attachment; filename="${id}-clips.zip"`,
    },
  });
}
