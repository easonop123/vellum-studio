import Link from "next/link";
import { SITE } from "@/lib/site";
import { Wordmark } from "@/components/site-header";

export function SiteFooter() {
  const { links } = SITE;
  const rows = [
    { name: "tiktok", value: links.tiktok.handle, href: links.tiktok.url },
    { name: "youtube", value: links.youtube.handle, href: links.youtube.url },
    { name: "instagram", value: links.instagram.handle, href: links.instagram.url },
    { name: "email", value: links.email, href: `mailto:${links.email}` },
  ];
  return (
    <footer className="border-t border-graphite/70">
      <div className="mx-auto max-w-[1240px] px-4 pt-14 pb-10 lg:px-8">
        <Link href="/" aria-label="Vellum Studio home" className="text-h3 sm:text-h2">
          <Wordmark />
        </Link>
        <dl className="mt-10 grid max-w-xl gap-y-3">
          {rows.map((row) => (
            <div key={row.name} className="grid grid-cols-[6.5rem_1fr] items-baseline gap-3">
              <dt className="text-small text-ash">{row.name}</dt>
              <dd className="min-w-0">
                <a
                  href={row.href}
                  className="break-words underline decoration-graphite decoration-1 hover:decoration-bone"
                  {...(row.href.startsWith("http") ? { target: "_blank", rel: "noreferrer" } : {})}
                >
                  {row.name === "email" ? (
                    <>
                      {row.value.split("@")[0]}
                      <wbr />@{row.value.split("@")[1]}
                    </>
                  ) : (
                    row.value
                  )}
                </a>
              </dd>
            </div>
          ))}
        </dl>
        <p className="mt-12 text-small text-ash">made in new zealand. prices in nzd.</p>
      </div>
    </footer>
  );
}
