import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";
import { SiteHeader } from "@/components/site-header";
import { isOrderId } from "@/lib/ids";
import { confirmFromSession } from "@/lib/payments";
import { SITE } from "@/lib/site";
import { getStore } from "@/lib/store";

export const metadata: Metadata = { title: "order received", robots: { index: false } };

function firstName(name: string) {
  return name.trim().split(/\s+/)[0]?.toLowerCase() ?? "";
}

function Missing() {
  return (
    <>
      <h1 className="display text-h1 sm:text-xl">can&apos;t find that order</h1>
      <p className="mt-5 max-w-[46ch] text-bone/80">
        if you just paid, you&apos;re fine: stripe emailed you a receipt and i&apos;ve got your order. any worries, email{" "}
        <a className="underline decoration-safelight decoration-2" href={`mailto:${SITE.links.email}`}>
          {SITE.links.email}
        </a>
        .
      </p>
    </>
  );
}

async function ThanksContent({ searchParams }: { searchParams: PageProps<"/thanks">["searchParams"] }) {
  const params = await searchParams;
  const orderId = typeof params.order === "string" ? params.order : "";
  const sessionId = typeof params.session_id === "string" ? params.session_id : "";
  if (!isOrderId(orderId)) return <Missing />;

  const store = getStore();
  if (sessionId) await confirmFromSession(sessionId, orderId, store);
  const order = await store.get(orderId);
  if (!order) return <Missing />;

  const name = firstName(order.name);
  return (
    <>
      <p className="flex items-center gap-2 text-label text-ash mono">
        <span className="size-[0.62em] rounded-full bg-safelight" aria-hidden />
        order number
      </p>
      <p className="mt-2 text-h2 font-bold tracking-tight mono sm:text-h1" data-testid="order-number">
        {order.id}
      </p>
      <h1 className="display mt-10 text-h1 sm:text-xl">got it{name ? `, ${name}` : ""}.</h1>
      <p className="mt-5 max-w-[40ch] text-lead leading-snug">i&apos;ll have it to you within {SITE.deliveryHours} hours.</p>
      <p className="mt-4 max-w-[46ch] text-bone/80">
        i&apos;ll email it to <span className="text-bone">{order.email}</span>. if something&apos;s off, email{" "}
        <a className="underline decoration-safelight decoration-2" href={`mailto:${SITE.links.email}?subject=${order.id}`}>
          {SITE.links.email}
        </a>{" "}
        with your order number.
      </p>
      {order.status === "unpaid" ? (
        <p className="mt-8 max-w-[46ch] rounded-[3px] border border-graphite bg-well p-4 text-bone/85" data-testid="payment-pending">
          your payment is still going through. if it doesn&apos;t, you can{" "}
          <a className="underline decoration-safelight decoration-2" href={`/api/orders/${order.id}/pay`}>
            try paying again
          </a>
          .
        </p>
      ) : null}
      <Link href="/" className="btn-quiet mt-12">
        back to the site
      </Link>
    </>
  );
}

export default function ThanksPage({ searchParams }: PageProps<"/thanks">) {
  return (
    <>
      <SiteHeader showOrder={false} />
      <main className="mx-auto max-w-2xl px-4 pt-14 pb-20 sm:pt-20">
        <Suspense fallback={<p className="text-ash">checking your order...</p>}>
          <ThanksContent searchParams={searchParams} />
        </Suspense>
      </main>
    </>
  );
}
