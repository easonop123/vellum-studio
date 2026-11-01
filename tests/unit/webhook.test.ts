import { mkdtempSync, rmSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import Stripe from "stripe";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { POST } from "@/app/api/stripe/webhook/route";
import { handleStripeEvent } from "@/lib/payments";
import { setStoreForTests } from "@/lib/store";
import { FileOrderStore } from "@/lib/store/file";
import type { OrderRecord } from "@/lib/store/types";

const SECRET = "whsec_unit_test_secret";

function record(id: string): OrderRecord {
  return {
    id,
    createdAt: new Date("2026-11-01T10:00:00Z").toISOString(),
    name: "Test Person",
    email: "test@example.com",
    handle: "@test",
    package: "short",
    song: "some song",
    songStart: "0:45",
    vibes: ["cinematic"],
    notes: "",
    clipsLink: "https://drive.google.com/drive/folders/abc",
    uploads: [],
    amountCents: 500,
    currency: "nzd",
    checkout: "stripe",
  };
}

/** A checkout.session.completed event shaped like the real thing. */
function sessionEvent(orderId: string, session: Partial<Record<string, unknown>> = {}, type = "checkout.session.completed") {
  return {
    id: "evt_test_123",
    object: "event",
    api_version: "2026-01-01",
    created: 1793000000,
    livemode: false,
    pending_webhooks: 1,
    request: { id: null, idempotency_key: null },
    type,
    data: {
      object: {
        id: "cs_test_abc123",
        object: "checkout.session",
        mode: "payment",
        payment_status: "paid",
        status: "complete",
        amount_total: 500,
        currency: "nzd",
        livemode: false,
        client_reference_id: orderId,
        metadata: { orderId },
        ...session,
      },
    },
  };
}

function webhookRequest(payload: string, signature?: string) {
  const header = signature ?? Stripe.webhooks.generateTestHeaderString({ payload, secret: SECRET });
  return new Request("http://localhost/api/stripe/webhook", {
    method: "POST",
    body: payload,
    headers: { "content-type": "application/json", "stripe-signature": header },
  });
}

describe("stripe webhook", () => {
  let dir: string;
  let store: FileOrderStore;

  beforeEach(async () => {
    dir = mkdtempSync(path.join(os.tmpdir(), "vellum-webhook-"));
    store = new FileOrderStore(dir);
    setStoreForTests(store);
    process.env.STRIPE_WEBHOOK_SECRET = SECRET;
    await store.create(record("VS-ABCDE"));
  });

  afterEach(() => {
    setStoreForTests(null);
    rmSync(dir, { recursive: true, force: true });
  });

  it("marks the order paid when a signed checkout.session.completed arrives", async () => {
    expect((await store.get("VS-ABCDE"))?.status).toBe("unpaid");
    const res = await POST(webhookRequest(JSON.stringify(sessionEvent("VS-ABCDE"))));
    expect(res.status).toBe(200);
    expect(await res.json()).toMatchObject({ received: true, handled: true, orderId: "VS-ABCDE", result: "marked" });
    const order = await store.get("VS-ABCDE");
    expect(order?.status).toBe("paid");
    expect(order?.payment).toMatchObject({ method: "stripe", sessionId: "cs_test_abc123", amountTotal: 500, currency: "nzd", livemode: false });
  });

  it("is safe when Stripe sends the same event twice", async () => {
    const payload = JSON.stringify(sessionEvent("VS-ABCDE"));
    await POST(webhookRequest(payload));
    const second = await POST(webhookRequest(payload));
    expect(second.status).toBe(200);
    expect(await second.json()).toMatchObject({ result: "already" });
    expect((await store.get("VS-ABCDE"))?.status).toBe("paid");
  });

  it("rejects a forged or tampered event", async () => {
    const payload = JSON.stringify(sessionEvent("VS-ABCDE"));
    const forged = Stripe.webhooks.generateTestHeaderString({ payload, secret: "whsec_wrong" });
    const res = await POST(webhookRequest(payload, forged));
    expect(res.status).toBe(400);
    const tampered = await POST(
      webhookRequest(payload.replace('"amount_total":500', '"amount_total":1'), Stripe.webhooks.generateTestHeaderString({ payload, secret: SECRET })),
    );
    expect(tampered.status).toBe(400);
    expect((await store.get("VS-ABCDE"))?.status).toBe("unpaid");
  });

  it("rejects a request with no signature header", async () => {
    const res = await POST(
      new Request("http://localhost/api/stripe/webhook", { method: "POST", body: JSON.stringify(sessionEvent("VS-ABCDE")) }),
    );
    expect(res.status).toBe(400);
  });

  it("doesn't mark paid while the payment is still pending", async () => {
    const res = await POST(webhookRequest(JSON.stringify(sessionEvent("VS-ABCDE", { payment_status: "unpaid" }))));
    expect(res.status).toBe(200);
    expect((await store.get("VS-ABCDE"))?.status).toBe("unpaid");
  });

  it("marks paid when a delayed payment succeeds later", async () => {
    const event = sessionEvent("VS-ABCDE", {}, "checkout.session.async_payment_succeeded");
    await POST(webhookRequest(JSON.stringify(event)));
    expect((await store.get("VS-ABCDE"))?.status).toBe("paid");
  });

  it("ignores events it doesn't care about", async () => {
    const res = await POST(webhookRequest(JSON.stringify(sessionEvent("VS-ABCDE", {}, "payment_intent.created"))));
    expect(await res.json()).toMatchObject({ received: true, handled: false });
    expect((await store.get("VS-ABCDE"))?.status).toBe("unpaid");
  });

  it("answers 200 for an unknown order so Stripe doesn't retry forever", async () => {
    const res = await POST(webhookRequest(JSON.stringify(sessionEvent("VS-ZZZZZ"))));
    expect(res.status).toBe(200);
    expect(await res.json()).toMatchObject({ result: "missing" });
  });

  it("refuses to run without a webhook secret", async () => {
    delete process.env.STRIPE_WEBHOOK_SECRET;
    const res = await POST(webhookRequest(JSON.stringify(sessionEvent("VS-ABCDE"))));
    expect(res.status).toBe(500);
  });

  it("handleStripeEvent falls back to client_reference_id", async () => {
    const event = sessionEvent("VS-ABCDE", { metadata: {} }) as unknown as Stripe.Event;
    const result = await handleStripeEvent(event, store);
    expect(result).toMatchObject({ handled: true, result: "marked" });
  });
});
