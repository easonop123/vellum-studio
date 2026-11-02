import { ADMIN_COOKIE, passwordMatches, sessionToken } from "@/lib/admin-auth";

export async function POST(request: Request) {
  const form = await request.formData();
  const attempt = String(form.get("password") ?? "");
  const target = new URL("/admin", request.url);
  if (!passwordMatches(attempt)) {
    // A little friction against guessing.
    await new Promise((r) => setTimeout(r, 600));
    target.searchParams.set("error", "1");
    return Response.redirect(target, 303);
  }
  const secure = new URL(request.url).protocol === "https:";
  const cookie = [
    `${ADMIN_COOKIE}=${sessionToken()}`,
    "Path=/",
    "HttpOnly",
    "SameSite=Lax",
    `Max-Age=${60 * 60 * 24 * 30}`,
    secure ? "Secure" : "",
  ]
    .filter(Boolean)
    .join("; ");
  return new Response(null, { status: 303, headers: { location: target.toString(), "set-cookie": cookie } });
}
