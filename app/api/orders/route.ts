import { newOrderId } from "@/lib/ids";
import { formatBytes, MAX_TOTAL_BYTES } from "@/lib/limits";
import { fieldErrors, orderInputSchema } from "@/lib/order-schema";
import { checkoutMode, createStripeCheckout, isLiveKey, priceFor, stripeKeyProblem } from "@/lib/payments";
import { SITE } from "@/lib/site";
import { ConfigError, getStore, type OrderRecord, type OrderStore } from "@/lib/store";

function originOf(request: Request): string {
  const header = request.headers.get("origin");
  if (header && /^https?:\/\/[^/]+$/.test(header)) return header;
  return new URL(request.url).origin;
}

export async function POST(request: Request) {
  let store: OrderStore;
  try {
    store = getStore();
  } catch (err) {
    const message = err instanceof ConfigError ? err.message : "storage isn't working right now";
    return Response.json({ formError: message }, { status: 503 });
  }

  const mode = checkoutMode();
  if (mode === "off") {
    return Response.json(
      { formError: `payments aren't switched on yet. email me at ${SITE.links.email} and i'll sort you out.` },
      { status: 503 },
    );
  }
  const keyProblem = mode === "stripe" ? stripeKeyProblem() : null;
  if (keyProblem) return Response.json({ formError: keyProblem }, { status: 503 });

  const json = await request.json().catch(() => null);
  const parsed = orderInputSchema.safeParse(json);
  if (!parsed.success) return Response.json({ errors: fieldErrors(parsed.error) }, { status: 400 });
  const input = parsed.data;

  // Every upload must be one this form made, and must actually exist.
  let total = 0;
  for (const clip of input.uploads) {
    if (!input.draftId || !clip.pathname.startsWith(`clips/${input.draftId}/`)) {
      return Response.json({ errors: { clips: `${clip.name} didn't come from this form. remove it and add it again.` } }, { status: 400 });
    }
    const found = await store.clipExists(clip.pathname);
    if (!found) {
      return Response.json({ errors: { clips: `${clip.name} didn't finish uploading. remove it and add it again.` } }, { status: 400 });
    }
    clip.size = found.size;
    total += found.size;
  }
  if (total > MAX_TOTAL_BYTES) {
    return Response.json(
      { errors: { clips: `your uploads add up to ${formatBytes(total)}, over the ${formatBytes(MAX_TOTAL_BYTES)} limit. send some as a link.` } },
      { status: 400 },
    );
  }

  let id = newOrderId();
  for (let tries = 0; tries < 5 && (await store.get(id)); tries++) id = newOrderId();

  const record: OrderRecord = {
    id,
    createdAt: new Date().toISOString(),
    name: input.name,
    email: input.email,
    handle: input.handle,
    package: input.package,
    song: input.song,
    songStart: input.songStart,
    vibes: input.vibes,
    notes: input.notes,
    clipsLink: input.clipsLink,
    draftId: input.draftId,
    uploads: input.uploads,
    amountCents: priceFor(input.package),
    currency: SITE.currency,
    checkout: mode,
  };

  try {
    await store.create(record);
  } catch (err) {
    console.error("order create failed", err);
    return Response.json({ formError: "couldn't save your order. try again in a minute." }, { status: 500 });
  }

  if (mode === "fake") return Response.json({ id, url: `/fake-checkout?order=${id}` });

  try {
    const url = await createStripeCheckout(record, originOf(request));
    return Response.json({ id, url });
  } catch (err) {
    console.error("stripe checkout failed", err);
    // With a test key it's you testing, so show what Stripe said. Real customers get the plain message.
    const said = !isLiveKey() && err instanceof Error && err.message ? ` stripe said: "${err.message.slice(0, 300)}"` : "";
    return Response.json(
      { formError: `your order ${id} is saved but the payment page didn't open. try again, or email ${SITE.links.email}.${said}` },
      { status: 502 },
    );
  }
}
