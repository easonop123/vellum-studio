import { createHmac, timingSafeEqual } from "node:crypto";
import { cookies } from "next/headers";

export const ADMIN_COOKIE = "vs_admin";

function expectedToken(password: string): string {
  return createHmac("sha256", password).update("vellum-admin-v1").digest("hex");
}

export function adminConfigured(): boolean {
  return Boolean(process.env.ADMIN_PASSWORD);
}

function safeEqual(a: string, b: string): boolean {
  const ab = Buffer.from(a);
  const bb = Buffer.from(b);
  return ab.length === bb.length && timingSafeEqual(ab, bb);
}

export function passwordMatches(attempt: string): boolean {
  const password = process.env.ADMIN_PASSWORD;
  if (!password) return false;
  return safeEqual(expectedToken(attempt), expectedToken(password));
}

/** The cookie holds an HMAC of the password, never the password itself. */
export function sessionToken(): string {
  return expectedToken(process.env.ADMIN_PASSWORD ?? "");
}

export function tokenIsValid(token: string | undefined): boolean {
  const password = process.env.ADMIN_PASSWORD;
  if (!password || !token) return false;
  return safeEqual(token, expectedToken(password));
}

/** For server components and route handlers. */
export async function isAdmin(): Promise<boolean> {
  const jar = await cookies();
  return tokenIsValid(jar.get(ADMIN_COOKIE)?.value);
}
