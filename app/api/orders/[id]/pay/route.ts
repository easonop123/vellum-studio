import { isOrderId } from "@/lib/ids";
import { checkoutMode, createStripeCheckout } from "@/lib/payments";
import { getStore } from "@/lib/store";

/** "try paying again" after a cancelled checkout: a fresh Stripe session for the same order. */
export async function GET(request: Request, ctx: RouteContext<"/api/orders/[id]/pay">) {
  const { id } = await ctx.params;
  const origin = new URL(request.url).origin;
  if (!isOrderId(id)) return Response.redirect(`${origin}/order`, 303);
  const store = getStore();
  const order = await store.get(id);
  if (!order) return Response.redirect(`${origin}/order`, 303);
  if (order.status !== "unpaid") return Response.redirect(`${origin}/thanks?order=${id}`, 303);
  const mode = checkoutMode();
  if (mode === "fake") return Response.redirect(`${origin}/fake-checkout?order=${id}`, 303);
  if (mode !== "stripe") return Response.redirect(`${origin}/order`, 303);
  const url = await createStripeCheckout(order, origin);
  return Response.redirect(url, 303);
}
