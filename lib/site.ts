import site from "@/content/site.json";
import demos from "@/content/demos.json";

export type PackageId = "short" | "long";
export const PACKAGE_IDS: PackageId[] = ["short", "long"];

export const SITE = site;
export const DEMOS = demos;

export function packageInfo(id: PackageId) {
  return site.packages[id];
}

/** "$5" or "$7.50", no currency code. */
export function formatPrice(cents: number): string {
  const dollars = cents / 100;
  return Number.isInteger(dollars) ? `$${dollars}` : `$${dollars.toFixed(2)}`;
}

/** SMPTE-style timecode at 24 fps: 00:00:30:00 */
export function timecode(seconds: number, fps = 24): string {
  const totalFrames = Math.max(0, Math.floor(seconds * fps + 1e-6));
  const ff = totalFrames % fps;
  const totalSeconds = Math.floor(totalFrames / fps);
  const ss = totalSeconds % 60;
  const mm = Math.floor(totalSeconds / 60) % 60;
  const hh = Math.floor(totalSeconds / 3600);
  return [hh, mm, ss, ff].map((n) => String(n).padStart(2, "0")).join(":");
}

export function isPackageId(value: unknown): value is PackageId {
  return value === "short" || value === "long";
}
