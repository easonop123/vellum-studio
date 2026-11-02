import type { Metadata } from "next";
import { Suspense } from "react";
import { SiteHeader } from "@/components/site-header";
import { isOrderId } from "@/lib/ids";
import { checkoutMode, productName } from "@/lib/payments";
import { formatPrice } from "@/lib/site";
import { getStore } from "@/lib/store";

export const metadata: Metadata = { title: "test checkout", robots: { index: false } };

/**
 * Stand-in for Stripe Checkout when no Stripe key is set (local runs and the
 * automated tests). Switched off on the live site.
 */
async function FakeCheckout({ searchParams }: { searchParams: PageProps<"/fake-checkout">["searchParams"] }) {
  const params = await searchParams;
  const id = typeof params.order === "string" ? params.order : "";
  if (checkoutMode() !== "fake") return <p className="text-bone/80">this test page is switched off.</p>;
  const order = isOrderId(id) ? await getStore().get(id) : null;
  if (!order) return <p className="text-bone/80">no order with that number.</p>;
  return (
    <>
      <p className="text-label text-ash mono">TEST CHECKOUT</p>
      <h1 className="display mt-3 text-h1">pretend to pay</h1>
      <p className="mt-4 max-w-[46ch] text-bone/80">
        no stripe key is set, so this page stands in for stripe. no real money moves.
      </p>
      <dl className="mt-8 grid grid-cols-[7rem_1fr] gap-y-2 rounded-[3px] bg-well p-5">
        <dt className="text-ash">order</dt>
        <dd className="mono">{order.id}</dd>
        <dt className="text-ash">item</dt>
        <dd>{productName(order.package)}</dd>
        <dt className="text-ash">total</dt>
        <dd className="font-bold">
          {formatPrice(order.amountCents)} {order.currency.toUpperCase()}
        </dd>
      </dl>
      <form action="/api/fake-checkout" method="post" className="mt-8 flex flex-wrap items-center gap-4">
        <input type="hidden" name="order" value={order.id} />
        <button type="submit" className="btn-primary">
          complete test payment
        </button>
        <a href={`/order?cancelled=${order.id}`} className="text-ash underline hover:text-bone">
          cancel
        </a>
      </form>
    </>
  );
}

export default function FakeCheckoutPage({ searchParams }: PageProps<"/fake-checkout">) {
  return (
    <>
      <SiteHeader showOrder={false} />
      <main className="mx-auto max-w-2xl px-4 pt-14 pb-20">
        <Suspense fallback={<p className="text-ash">loading...</p>}>
          <FakeCheckout searchParams={searchParams} />
        </Suspense>
      </main>
    </>
  );
}
