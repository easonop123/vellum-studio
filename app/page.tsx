import Link from "next/link";
import { DemoReel } from "@/components/demo-reel";
import { HeroMonitor } from "@/components/hero-monitor";
import { RawEditWipe } from "@/components/raw-edit-wipe";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";
import { DEMOS, formatPrice, packageInfo, SITE, timecode } from "@/lib/site";

const short = packageInfo("short");
const long = packageInfo("long");
const fromPrice = `${formatPrice(short.priceCents)} ${SITE.currency}`;

const steps = [
  {
    title: "send me your clips",
    body: "10 to 40 clips from any phone or camera. upload them here, or paste a google drive, wetransfer, icloud or dropbox link.",
  },
  {
    title: "pick a song",
    body: "any song. if there's a part you love, tell me where to start the edit.",
  },
  {
    title: `get your edit in ${SITE.deliveryHours}h`,
    body: "you get a version to post with no song on it, so it doesn't get muted, plus a preview with the song mixed in. add the song in tiktok or instagram when you post.",
    readout: `${SITE.deliveryHours}:00:00:00`,
  },
];

const faqs = [
  {
    q: "what clips should i send?",
    a: "10 to 40 clips. phones, gopros, drones and cameras all work, vertical or sideways. mix it up: wide shots, close-ups, people, food, things moving. a few seconds of each is plenty.",
  },
  {
    q: "how does the song work?",
    a: "tiktok and instagram mute videos that have a song baked in. so the version you post only has my sound effects, and you add the song in the app when you post it. i also send a preview with the song mixed in, so you can hear how the cuts land.",
  },
  {
    q: "what happens to my clips?",
    a: "i only use them for your edit and never post them anywhere. they're deleted 30 days after you send them.",
  },
  {
    q: "what if you can't make it work?",
    a: "if i can't deliver your edit, you get a full refund. if it's not quite right, you get one free revision.",
  },
  {
    q: "how do i get the finished edit?",
    a: `i email it to you within ${SITE.deliveryHours} hours of your order.`,
  },
];

export default function Home() {
  return (
    <>
      <SiteHeader />
      <main>
        {/* Hero: the footage first. On phones the words sit over the bottom of the video. */}
        <section className="mx-auto grid max-w-[1240px] lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end lg:gap-16 lg:px-8 lg:pt-12 lg:pb-20">
          <div className="relative [grid-area:1/1] h-[calc(100svh-3.5rem)] max-h-[60rem] min-h-[34rem] lg:[grid-area:1/2] lg:aspect-[9/16] lg:h-[min(80vh,50rem)] lg:min-h-0">
            <HeroMonitor src={DEMOS.hero.video} poster={DEMOS.hero.poster} label={DEMOS.hero.title} />
          </div>
          {/* On phones this sits in the black space under the picture band, so the footage stays clear. */}
          <div className="relative z-10 [grid-area:1/1] self-end bg-gradient-to-t from-ink from-70% to-transparent px-4 pt-10 pb-5 lg:bg-none lg:p-0 lg:pb-2">
            <h1 className="display max-w-[16ch] text-[clamp(1.9rem,8.6vw,3.375rem)] lg:max-w-[14ch] lg:text-xxl">
              send me your clips. i&apos;ll cut them to the song you pick.
            </h1>
            <p className="mt-6 hidden max-w-[34ch] text-lead leading-snug text-bone/80 lg:block">
              beat-synced edits for tiktok, reels and shorts. from {fromPrice}, back within {SITE.deliveryHours} hours.
            </p>
            <Link href="/order" className="btn-primary mt-4 w-full sm:w-auto lg:mt-9">
              send me your clips
            </Link>
            <p className="mt-2.5 text-small text-ash lg:hidden">
              from {fromPrice}, back within {SITE.deliveryHours} hours.
            </p>
          </div>
        </section>

        {/* RAW → EDIT: the one loud moment */}
        <section aria-labelledby="raw-edit" className="mx-auto max-w-[1240px] px-4 pt-20 pb-24 lg:grid lg:grid-cols-[minmax(0,1fr)_minmax(0,27rem)] lg:items-center lg:gap-16 lg:px-8 lg:pt-28">
          <div className="lg:pb-24">
            <p className="text-label text-ash mono">RAW → EDIT</p>
            <h2 id="raw-edit" className="display mt-3 text-h2 lg:text-xl">
              same clip, my edit
            </h2>
            <p className="mt-5 max-w-[42ch] text-bone/80">
              left is how it came off the phone. right is after my grade. drag the red line.
            </p>
          </div>
          <div className="mt-9 lg:mt-0">
            <RawEditWipe
              raw={DEMOS.beforeAfter.raw}
              edit={DEMOS.beforeAfter.edit}
              poster={DEMOS.beforeAfter.poster}
              rawLabel={DEMOS.beforeAfter.rawLabel}
            />
          </div>
        </section>

        <section aria-labelledby="demos" className="mx-auto max-w-[1240px] px-4 pb-24 lg:px-8">
          <h2 id="demos" className="display text-h2 lg:text-xl">
            recent edits
          </h2>
          <p className="mt-4 mb-9 max-w-[46ch] text-bone/80">
            each one started as a pile of phone clips. tap sound off to hear them.
          </p>
          <DemoReel demos={DEMOS.demos} />
        </section>

        <section aria-labelledby="how" className="mx-auto max-w-[1240px] px-4 pb-24 lg:px-8">
          <h2 id="how" className="display text-h2 lg:text-xl">
            how it works
          </h2>
          <ol className="mt-10 grid gap-10 lg:grid-cols-3 lg:gap-12">
            {steps.map((step, i) => (
              <li key={step.title} className="grid grid-cols-[2.75rem_1fr] gap-x-3 lg:block">
                <span className="display text-h3 text-ash lg:text-h2" aria-hidden>
                  {i + 1}
                </span>
                <div className="lg:mt-5">
                  <h3 className="text-lead leading-tight font-bold">{step.title}</h3>
                  <p className="mt-2 max-w-[38ch] text-bone/75">{step.body}</p>
                  {step.readout ? (
                    <p className="mt-4 text-small text-safelight mono" aria-label={`${SITE.deliveryHours} hours`}>
                      {step.readout}
                    </p>
                  ) : null}
                </div>
              </li>
            ))}
          </ol>
        </section>

        <section aria-labelledby="pricing" className="mx-auto max-w-[1240px] px-4 pb-24 lg:px-8">
          <h2 id="pricing" className="display text-h2 lg:text-xl">
            pricing
          </h2>
          <div className="mt-10 grid grid-cols-2 overflow-hidden rounded-[3px] bg-graphite/60 lg:max-w-3xl">
            {(["short", "long"] as const).map((id) => {
              const pkg = packageInfo(id);
              return (
                <div key={id} className="flex flex-col p-4 first:border-r first:border-ink sm:p-7">
                  <h3 className="display text-h3 sm:text-h2">{pkg.label}</h3>
                  <p className="mt-1 text-small text-ash">up to {pkg.maxSeconds} s</p>
                  <p className="mt-5 text-label text-bone/70 mono sm:text-small">{timecode(pkg.maxSeconds)}</p>
                  <p className="mt-1 flex items-baseline gap-1.5">
                    <span className="display text-h1 sm:text-xl">{formatPrice(pkg.priceCents)}</span>
                    <span className="text-label text-ash mono">{SITE.currency.toUpperCase()}</span>
                  </p>
                  <Link href={`/order?package=${id}`} className="btn-quiet mt-6 w-full px-2 text-small sm:text-body">
                    order {pkg.label}
                  </Link>
                </div>
              );
            })}
          </div>
          <p className="mt-5 max-w-[52ch] text-bone/80">
            both come back within {SITE.deliveryHours} hours, with one free revision. you pay by card through stripe.
          </p>
        </section>

        <section aria-labelledby="faq" className="mx-auto max-w-[1240px] px-4 pb-24 lg:px-8">
          <h2 id="faq" className="display text-h2 lg:text-xl">
            questions
          </h2>
          <div className="mt-8 max-w-3xl divide-y divide-graphite border-y border-graphite">
            {faqs.map((item) => (
              <details key={item.q} className="group">
                <summary className="flex cursor-pointer list-none items-center justify-between gap-6 py-5 text-lead leading-snug font-medium [&::-webkit-details-marker]:hidden">
                  {item.q}
                  <span aria-hidden className="text-lead text-ash mono transition-transform group-open:rotate-45">
                    +
                  </span>
                </summary>
                <p className="max-w-[60ch] pb-6 text-bone/80">{item.a}</p>
              </details>
            ))}
          </div>
        </section>

        <section className="mx-auto max-w-[1240px] px-4 pb-24 lg:px-8">
          <div className="rounded-[3px] bg-graphite/60 px-5 py-10 sm:px-10 sm:py-14">
            <h2 className="display text-h2 lg:text-xl">send me your clips</h2>
            <p className="mt-4 max-w-[46ch] text-bone/80">
              short edit {formatPrice(short.priceCents)}, long edit {formatPrice(long.priceCents)}. back within{" "}
              {SITE.deliveryHours} hours.
            </p>
            <Link href="/order" className="btn-primary mt-7 w-full sm:w-auto">
              send me your clips
            </Link>
          </div>
        </section>
      </main>
      <SiteFooter />
    </>
  );
}
