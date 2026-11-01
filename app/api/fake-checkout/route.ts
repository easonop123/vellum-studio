import { isOrderId } from "@/lib/ids";
import { checkoutMode } from "@/lib/payments";
import { getStore } from "@/lib/store";

/** Completes a pretend payment. Only works when there's no Stripe key and fake checkout is allowed. */
export async function POST(request: Request) {
  if (checkoutMode() !== "fake") return Response.json({ error: "not available" }, { status: 404 });
  const form = await request.formData();
  const id = String(form.get("order") ?? "");
  if (!isOrderId(id)) return Response.json({ error: "bad order" }, { status: 400 });
  const result = await getStore().markPaid(id, { method: "fake", paidAt: new Date().toISOString() });
  if (result === "missing") return Response.json({ error: "no such order" }, { status: 404 });
  return Response.redirect(new URL(`/thanks?order=${id}`, request.url), 303);
}
