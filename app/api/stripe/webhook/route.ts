import Stripe from "stripe";
import { handleStripeEvent } from "@/lib/payments";
import { getStore } from "@/lib/store";

/**
 * Stripe calls this after a checkout. Verifies the signature with
 * STRIPE_WEBHOOK_SECRET, then marks the order paid.
 */
export async function POST(request: Request) {
  const secret = process.env.STRIPE_WEBHOOK_SECRET;
  if (!secret) return Response.json({ error: "STRIPE_WEBHOOK_SECRET is not set" }, { status: 500 });

  const signature = request.headers.get("stripe-signature");
  if (!signature) return Response.json({ error: "missing stripe-signature header" }, { status: 400 });

  const payload = await request.text();
  let event: Stripe.Event;
  try {
    event = Stripe.webhooks.constructEvent(payload, signature, secret);
  } catch {
    return Response.json({ error: "signature check failed" }, { status: 400 });
  }

  try {
    const result = await handleStripeEvent(event, getStore());
    return Response.json({ received: true, ...result });
  } catch (err) {
    console.error("webhook handling failed", err);
    // 500 makes Stripe retry later.
    return Response.json({ error: "couldn't record the payment" }, { status: 500 });
  }
}
