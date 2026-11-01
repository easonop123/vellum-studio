import { isAdmin } from "@/lib/admin-auth";
import { getStore } from "@/lib/store";

/** Sends you to a short-lived link for one private clip. */
export async function GET(request: Request) {
  if (!(await isAdmin())) return Response.json({ error: "log in first" }, { status: 401 });
  const url = new URL(request.url);
  const pathname = url.searchParams.get("p") ?? "";
  if (!pathname.startsWith("clips/") || pathname.includes("..")) return Response.json({ error: "bad path" }, { status: 400 });
  const target = await getStore().clipUrl(pathname, { download: url.searchParams.get("download") === "1" });
  return Response.redirect(new URL(target, request.url), 302);
}
