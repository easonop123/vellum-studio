import Link from "next/link";

export function Wordmark({ className = "" }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-2.5 font-bold uppercase tracking-[-0.02em] ${className}`}>
      <span aria-hidden className="size-[0.55em] rounded-full bg-safelight" />
      <span>
        Vellum <span className="font-medium text-ash">/</span> Studio
      </span>
    </span>
  );
}

export function SiteHeader({ showOrder = true }: { showOrder?: boolean }) {
  return (
    <header className="sticky top-0 z-40 border-b border-graphite/70 bg-ink/90 backdrop-blur-md">
      <div className="mx-auto flex h-14 max-w-[1240px] items-center justify-between px-4 lg:px-8">
        <Link href="/" className="text-[1.0625rem]" aria-label="Vellum Studio home">
          <Wordmark />
        </Link>
        {showOrder ? (
          <Link href="/order" className="btn-quiet min-h-9 px-3.5 text-small">
            order an edit
          </Link>
        ) : null}
      </div>
    </header>
  );
}
