import { afterEach, describe, expect, it } from "vitest";
import { POST } from "@/app/api/orders/route";
import { checkoutMode, isLiveKey, stripeKeyProblem } from "@/lib/payments";
import { setStoreForTests } from "@/lib/store";
import { FileOrderStore } from "@/lib/store/file";
import { mkdtempSync, rmSync } from "node:fs";
import os from "node:os";
import path from "node:path";

const original = process.env.STRIPE_SECRET_KEY;

function setKey(key: string | undefined) {
  if (key === undefined) delete process.env.STRIPE_SECRET_KEY;
  else process.env.STRIPE_SECRET_KEY = key;
}

afterEach(() => setKey(original));

describe("stripe key checks", () => {
  it("accepts secret and restricted keys, even with stray spaces around them", () => {
    for (const key of ["sk_test_51AbcXYZ", "rk_test_51AbcXYZ", "sk_live_51AbcXYZ", "  sk_test_51AbcXYZ \n"]) {
      setKey(key);
      expect(stripeKeyProblem()).toBeNull();
      expect(checkoutMode()).toBe("stripe");
    }
  });

  it("names the publishable-key mix-up", () => {
    setKey("pk_test_51AbcXYZ");
    expect(stripeKeyProblem()).toMatch(/publishable/);
  });

  it("flags keys that can't be right", () => {
    for (const key of ["sk_test_51Abc XYZ", "whsec_123", "51AbcXYZ"]) {
      setKey(key);
      expect(stripeKeyProblem()).toMatch(/doesn't look right/);
    }
  });

  it("only live keys hide Stripe's own error text", () => {
    setKey("sk_test_51AbcXYZ");
    expect(isLiveKey()).toBe(false);
    setKey("sk_live_51AbcXYZ");
    expect(isLiveKey()).toBe(true);
  });
});

describe("order route with a wrong key", () => {
  it("says what's wrong before saving anything", async () => {
    const dir = mkdtempSync(path.join(os.tmpdir(), "vellum-orders-"));
    const store = new FileOrderStore(dir);
    setStoreForTests(store);
    try {
      setKey("pk_test_51AbcXYZ");
      const res = await POST(new Request("http://localhost/api/orders", { method: "POST", body: "{}" }));
      expect(res.status).toBe(503);
      expect((await res.json()).formError).toMatch(/publishable/);
      expect(await store.list()).toEqual([]);
    } finally {
      setStoreForTests(null);
      rmSync(dir, { recursive: true, force: true });
    }
  });
});
