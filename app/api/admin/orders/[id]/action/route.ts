import { isAdmin } from "@/lib/admin-auth";
import { isOrderId } from "@/lib/ids";
import { getStore } from "@/lib/store";

/** Buttons on the admin page: mark delivered, undo, delete clips. */
export async function POST(request: Request, ctx: RouteContext<"/api/admin/orders/[id]/action">) {
  if (!(await isAdmin())) return Response.json({ error: "log in first" }, { status: 401 });
  const { id } = await ctx.params;
  if (!isOrderId(id)) return Response.json({ error: "bad order" }, { status: 400 });
  const store = getStore();
  const order = await store.get(id);
  if (!order) return Response.json({ error: "no such order" }, { status: 404 });

  const action = String((await request.formData()).get("action") ?? "");
  if (action === "deliver") await store.setDelivered(id, true);
  else if (action === "undeliver") await store.setDelivered(id, false);
  else if (action === "delete-clips") {
    await store.deleteClips(order.uploads.map((u) => u.pathname));
    await store.markClipsDeleted(id);
  } else return Response.json({ error: "unknown action" }, { status: 400 });

  return Response.redirect(new URL(`/admin#${id}`, request.url), 303);
}
