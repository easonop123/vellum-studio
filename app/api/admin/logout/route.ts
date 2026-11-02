import { ADMIN_COOKIE } from "@/lib/admin-auth";

export async function POST(request: Request) {
  return new Response(null, {
    status: 303,
    headers: {
      location: new URL("/admin", request.url).toString(),
      "set-cookie": `${ADMIN_COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0`,
    },
  });
}
