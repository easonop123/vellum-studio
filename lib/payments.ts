import Stripe from "stripe";
import { formatPrice, packageInfo, SITE, type PackageId } from "@/lib/site";
import type { OrderStore, OrderRecord, PaymentInfo } from "@/lib/store/types";

export type CheckoutMode = "stripe" | "fake" | "off";

/**
 * - "stripe": a Stripe key is set (test or live).
 * - "fake":   no key, and we're running locally or in tests. A pretend
 *             payment page stands in for Stripe.
 * - "off":    no key on the live site. Ordering shows a clear error instead
 *             of handing out free edits.
 */
export function checkoutMode(): CheckoutMode {
  if (process.env.STRIPE_SECRET_KEY) return "stripe";
  if (process.env.NODE_ENV !== "production" || process.env.ALLOW_FAKE_CHECKOUT === "1") return "fake";
  return "off";
}

export function isStripeTestMode(): boolean {
  const key = process.env.STRIPE_SECRET_KEY ?? "";
  return key.startsWith("sk_test_") || key.startsWith("rk_test_");
}

let stripeClient: Stripe | null = null;
export function getStripe(): Stripe {
  const key = process.env.STRIPE_SECRET_KEY;
  if (!key) throw new Error("STRIPE_SECRET_KEY is not set");
  if (!stripeClient) stripeClient = new Stripe(key, { appInfo: { name: "vellum-studio" } });
  return stripeClient;
}

export function priceFor(pkg: PackageId): number {
  return packageInfo(pkg).priceCents;
}

export function productName(pkg: PackageId): string {
  const info = packageInfo(pkg);
  return pkg === "short" ? `Short edit (up to ${info.maxSeconds} s)` : `Long edit (up to ${info.maxSeconds} s)`;
}

export async function createStripeCheckout(order: OrderRecord, origin: string): Promise<string> {
  const stripe = getStripe();
  const session = await stripe.checkout.sessions.create({
    mode: "payment",
    currency: SITE.currency,
    customer_email: order.email,
    client_reference_id: order.id,
    metadata: { orderId: order.id },
    payment_intent_data: {
      description: `Vellum Studio order ${order.id}`,
      metadata: { orderId: order.id },
    },
    line_items: [
      {
        quantity: 1,
        price_data: {
          currency: SITE.currency,
          unit_amount: order.amountCents,
          product_data: {
            name: productName(order.package),
            description: `Beat-synced edit, delivered within ${SITE.deliveryHours} hours. ${SITE.freeRevisions} free revision. Order ${order.id}.`,
          },
        },
      },
    ],
    success_url: `${origin}/thanks?order=${order.id}&session_id={CHECKOUT_SESSION_ID}`,
    cancel_url: `${origin}/order?cancelled=${order.id}`,
  });
  if (!session.url) throw new Error("Stripe didn't return a checkout link");
  return session.url;
}

function paymentFromSession(session: Stripe.Checkout.Session, paidAtSeconds?: number): PaymentInfo {
  return {
    paidAt: new Date((paidAtSeconds ?? Math.floor(Date.now() / 1000)) * 1000).toISOString(),
    method: "stripe",
    sessionId: session.id,
    amountTotal: session.amount_total,
    currency: session.currency,
    livemode: session.livemode,
  };
}

function orderIdOf(session: Stripe.Checkout.Session): string | null {
  return session.metadata?.orderId ?? session.client_reference_id ?? null;
}

/**
 * The webhook's job. Pure apart from the store, so it's unit-testable with a
 * hand-made event.
 */
export async function handleStripeEvent(
  event: Stripe.Event,
  store: OrderStore,
): Promise<{ handled: boolean; orderId?: string; result?: string }> {
  if (event.type === "checkout.session.completed" || event.type === "checkout.session.async_payment_succeeded") {
    const session = event.data.object as Stripe.Checkout.Session;
    const orderId = orderIdOf(session);
    if (!orderId) return { handled: false };
    if (session.payment_status !== "paid") return { handled: true, orderId, result: "not-paid-yet" };
    const result = await store.markPaid(orderId, paymentFromSession(session, event.created));
    return { handled: true, orderId, result };
  }
  return { handled: false };
}

/** Called by the thanks page so a slow or missing webhook never loses a paid order. */
export async function confirmFromSession(sessionId: string, orderId: string, store: OrderStore) {
  if (checkoutMode() !== "stripe" || !/^cs_[A-Za-z0-9_]+$/.test(sessionId)) return null;
  try {
    const session = await getStripe().checkout.sessions.retrieve(sessionId);
    if (orderIdOf(session) !== orderId || session.payment_status !== "paid") return null;
    return await store.markPaid(orderId, paymentFromSession(session));
  } catch {
    return null;
  }
}

export function priceLabel(pkg: PackageId): string {
  return `${formatPrice(priceFor(pkg))} ${SITE.currency}`;
}
