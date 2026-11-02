import type { Metadata } from "next";
import { OrderForm } from "@/components/order-form";
import { SiteHeader } from "@/components/site-header";
import { SITE } from "@/lib/site";

export const metadata: Metadata = {
  title: "order an edit",
  description: "send me your clips and a song. i'll send back a beat-synced edit within 48 hours.",
};

export default function OrderPage() {
  return (
    <>
      <SiteHeader showOrder={false} />
      <main className="mx-auto max-w-2xl px-4 pt-10 pb-16 sm:pt-16">
        <h1 className="display text-h1 sm:text-xl">send me your clips</h1>
        <p className="mt-5 max-w-[46ch] text-bone/80">
          fill this in and pay, and i&apos;ll start on your edit. it&apos;s back within {SITE.deliveryHours} hours.
        </p>
        <OrderForm />
      </main>
    </>
  );
}
