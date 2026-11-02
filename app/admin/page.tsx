import type { Metadata } from "next";
import { Suspense } from "react";
import { DownloadOneByOne } from "@/components/download-all";
import { SiteHeader } from "@/components/site-header";
import { adminConfigured, isAdmin } from "@/lib/admin-auth";
import { formatBytes } from "@/lib/limits";
import { formatPrice, SITE } from "@/lib/site";
import { ConfigError, getStore, type OrderView } from "@/lib/store";

export const metadata: Metadata = { title: "orders", robots: { index: false, follow: false } };

const BLOB_FREE_BYTES = 1024 * 1024 * 1024;
const HOUR = 60 * 60 * 1000;

function nzTime(iso: string) {
  return new Date(iso).toLocaleString("en-NZ", {
    timeZone: "Pacific/Auckland",
    day: "numeric",
    month: "short",
    hour: "numeric",
    minute: "2-digit",
  });
}

function hoursLabel(ms: number) {
  const h = Math.round(Math.abs(ms) / HOUR);
  return h < 1 ? "under an hour" : `${h} h`;
}

function clipHref(pathname: string, download = false) {
  const params = new URLSearchParams({ p: pathname });
  if (download) params.set("download", "1");
  return `/api/admin/clip?${params.toString()}`;
}

function Login({ failed }: { failed: boolean }) {
  return (
    <form action="/api/admin/login" method="post" className="max-w-sm">
      <h1 className="display text-h1">orders</h1>
      <label htmlFor="password" className="mt-8 block font-medium">
        password
      </label>
      <input
        id="password"
        name="password"
        type="password"
        autoComplete="current-password"
        className="field mt-2"
        aria-invalid={failed || undefined}
        aria-describedby={failed ? "password-error" : undefined}
        required
      />
      {failed ? (
        <p id="password-error" className="mt-2 text-small text-safelight">
          wrong password. it&apos;s the ADMIN_PASSWORD you set in vercel.
        </p>
      ) : null}
      <button type="submit" className="btn-primary mt-5 w-full">
        open orders
      </button>
    </form>
  );
}

function Detail({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[6.5rem_1fr] gap-3">
      <dt className="text-ash">{label}</dt>
      <dd className="min-w-0 break-words">{children}</dd>
    </div>
  );
}

function OrderCard({ order, now }: { order: OrderView; now: number }) {
  const paidAt = order.payment?.paidAt;
  const due = paidAt ? new Date(paidAt).getTime() + SITE.deliveryHours * HOUR : null;
  const clipBytes = order.uploads.reduce((s, u) => s + u.size, 0);
  const clipsGone = Boolean(order.clipsDeletedAt);
  const statusText =
    order.status === "delivered"
      ? `delivered ${order.deliveredAt ? nzTime(order.deliveredAt) : ""}`
      : order.status === "paid"
        ? due && due < now
          ? `overdue by ${hoursLabel(now - due)}`
          : `due in ${hoursLabel((due ?? now) - now)}`
        : "not paid";
  const statusColour =
    order.status === "paid" ? "bg-safelight text-ink" : order.status === "delivered" ? "bg-graphite text-bone" : "border border-graphite text-ash";

  return (
    <article id={order.id} className="scroll-mt-20 rounded-[3px] bg-well p-4 sm:p-6" data-testid="order" data-status={order.status}>
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
          <h3 className="text-lead font-bold mono">{order.id}</h3>
          <span className="text-bone/80">
            {order.package} edit, {formatPrice(order.amountCents)} {order.currency.toUpperCase()}
          </span>
          {order.payment?.method === "fake" ? <span className="text-small text-ash">(test payment)</span> : null}
          {order.payment && order.payment.method === "stripe" && order.payment.livemode === false ? (
            <span className="text-small text-ash">(stripe test mode)</span>
          ) : null}
        </div>
        <span className={`rounded-full px-3 py-1 text-small font-medium ${statusColour}`} data-testid="order-status">
          {statusText}
        </span>
      </header>

      <dl className="mt-5 grid gap-2 text-small sm:text-body">
        <Detail label="ordered">{nzTime(order.createdAt)}</Detail>
        <Detail label="name">{order.name}</Detail>
        <Detail label="email">
          <a className="underline decoration-graphite hover:decoration-bone" href={`mailto:${order.email}?subject=your edit (${order.id})`}>
            {order.email}
          </a>
        </Detail>
        {order.handle ? <Detail label="handle">{order.handle}</Detail> : null}
        <Detail label="song">
          {order.song}
          {order.songStart ? <span className="text-ash"> from {order.songStart}</span> : null}
        </Detail>
        <Detail label="vibe">{order.vibes.length ? order.vibes.join(", ") : <span className="text-ash">none picked</span>}</Detail>
        {order.notes ? <Detail label="notes">{order.notes}</Detail> : null}
        {order.clipsLink ? (
          <Detail label="clips link">
            <a href={order.clipsLink} target="_blank" rel="noreferrer" className="underline decoration-safelight decoration-2">
              {order.clipsLink}
            </a>
          </Detail>
        ) : null}
      </dl>

      {order.uploads.length ? (
        <div className="mt-5">
          <p className="text-small text-ash">
            {order.uploads.length} uploaded {order.uploads.length === 1 ? "clip" : "clips"}, {formatBytes(clipBytes)}
            {clipsGone ? `, deleted ${nzTime(order.clipsDeletedAt!)}` : ""}
          </p>
          {!clipsGone ? (
            <>
              <div className="mt-3 flex flex-wrap gap-2">
                <a href={`/api/admin/orders/${order.id}/zip`} className="btn-quiet min-h-10 text-small">
                  download all (.zip)
                </a>
                <DownloadOneByOne hrefs={order.uploads.map((u) => clipHref(u.pathname, true))} />
              </div>
              <details className="mt-3">
                <summary className="cursor-pointer text-small text-ash hover:text-bone">show files</summary>
                <ul className="mt-2 grid gap-1 text-small">
                  {order.uploads.map((u) => (
                    <li key={u.pathname} className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1">
                      <span className="min-w-0 truncate mono">{u.name}</span>
                      <span className="flex gap-3 text-ash">
                        {formatBytes(u.size)}
                        <a href={clipHref(u.pathname)} target="_blank" rel="noreferrer" className="underline hover:text-bone">
                          open
                        </a>
                        <a href={clipHref(u.pathname, true)} className="underline hover:text-bone">
                          download
                        </a>
                      </span>
                    </li>
                  ))}
                </ul>
              </details>
            </>
          ) : null}
        </div>
      ) : null}

      <div className="mt-6 flex flex-wrap gap-2 border-t border-graphite pt-4">
        {order.status === "paid" ? (
          <form action={`/api/admin/orders/${order.id}/action`} method="post">
            <input type="hidden" name="action" value="deliver" />
            <button type="submit" className="btn-primary min-h-10 px-4 text-small">
              mark delivered
            </button>
          </form>
        ) : null}
        {order.status === "delivered" ? (
          <form action={`/api/admin/orders/${order.id}/action`} method="post">
            <input type="hidden" name="action" value="undeliver" />
            <button type="submit" className="btn-quiet min-h-10 text-small">
              undo delivered
            </button>
          </form>
        ) : null}
        {order.uploads.length && !clipsGone && order.status !== "paid" ? (
          <form action={`/api/admin/orders/${order.id}/action`} method="post">
            <input type="hidden" name="action" value="delete-clips" />
            <button type="submit" className="btn-quiet min-h-10 text-small">
              delete clips
            </button>
          </form>
        ) : null}
      </div>
    </article>
  );
}

async function loadOrders(): Promise<{ orders: OrderView[]; now: number } | { error: string }> {
  try {
    const orders = await getStore().list();
    return { orders, now: Date.now() };
  } catch (err) {
    return { error: err instanceof ConfigError ? err.message : "couldn't load orders from storage." };
  }
}

async function Dashboard() {
  const loaded = await loadOrders();
  if ("error" in loaded) return <p className="text-safelight">{loaded.error}</p>;
  const { orders, now } = loaded;
  const todo = orders.filter((o) => o.status === "paid").sort((a, b) => (a.payment?.paidAt ?? "").localeCompare(b.payment?.paidAt ?? ""));
  const delivered = orders.filter((o) => o.status === "delivered");
  const unpaid = orders.filter((o) => o.status === "unpaid");
  const stored = orders.filter((o) => !o.clipsDeletedAt).reduce((s, o) => s + o.uploads.reduce((t, u) => t + u.size, 0), 0);

  const groups = [
    { key: "todo", title: "to do", empty: "nothing waiting. nice.", list: todo },
    { key: "delivered", title: "delivered", empty: "none yet.", list: delivered },
    { key: "unpaid", title: "not paid", empty: "none.", list: unpaid },
  ];

  return (
    <>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <h1 className="display text-h1">orders</h1>
        <form action="/api/admin/logout" method="post">
          <button type="submit" className="text-small text-ash underline hover:text-bone">
            log out
          </button>
        </form>
      </div>
      <p className="mt-4 text-bone/80">
        {todo.length} to do, {delivered.length} delivered, {unpaid.length} not paid.
      </p>
      <p className="mt-1 text-small text-ash" data-testid="storage">
        uploaded clips stored: {formatBytes(stored)} of the free {formatBytes(BLOB_FREE_BYTES)}. delete clips after delivering
        to keep room.
      </p>
      {groups.map((g) => (
        <section key={g.key} className="mt-12" aria-labelledby={`group-${g.key}`}>
          <h2 id={`group-${g.key}`} className="display text-h3">
            {g.title} <span className="text-ash">{g.list.length}</span>
          </h2>
          <div className="mt-5 grid gap-4">
            {g.list.length ? g.list.map((o) => <OrderCard key={o.id} order={o} now={now} />) : <p className="text-ash">{g.empty}</p>}
          </div>
        </section>
      ))}
    </>
  );
}

async function AdminContent({ searchParams }: { searchParams: PageProps<"/admin">["searchParams"] }) {
  const params = await searchParams;
  if (!adminConfigured()) {
    return (
      <>
        <h1 className="display text-h1">orders</h1>
        <p className="mt-5 max-w-[50ch] text-bone/80">
          set an ADMIN_PASSWORD in vercel (project settings, environment variables), then redeploy. this page opens with that
          password.
        </p>
      </>
    );
  }
  if (!(await isAdmin())) return <Login failed={params.error === "1"} />;
  return <Dashboard />;
}

export default function AdminPage({ searchParams }: PageProps<"/admin">) {
  return (
    <>
      <SiteHeader showOrder={false} />
      <main className="mx-auto max-w-4xl px-4 pt-12 pb-24">
        <Suspense fallback={<p className="text-ash">loading orders...</p>}>
          <AdminContent searchParams={searchParams} />
        </Suspense>
      </main>
    </>
  );
}
