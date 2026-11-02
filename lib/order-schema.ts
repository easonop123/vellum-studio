import { z } from "zod";
import { MAX_FILES } from "@/lib/limits";

export const VIBES = ["cinematic", "hype", "soft", "funny"] as const;
export type Vibe = (typeof VIBES)[number];

export const uploadedClipSchema = z.object({
  pathname: z.string().min(1).max(500),
  url: z.string().min(1).max(2000),
  name: z.string().min(1).max(300),
  size: z.number().int().nonnegative(),
  contentType: z.string().max(200).optional(),
});
export type UploadedClip = z.infer<typeof uploadedClipSchema>;

export function isHttpUrl(value: string): boolean {
  try {
    const url = new URL(value);
    return (url.protocol === "https:" || url.protocol === "http:") && url.hostname.includes(".");
  } catch {
    return false;
  }
}

export const orderInputSchema = z
  .object({
    name: z.string().trim().min(1, "i need your name").max(100, "that name is too long"),
    email: z
      .string()
      .trim()
      .min(1, "i need your email so i can send you the edit")
      .max(200, "that email is too long")
      .email("that email doesn't look right. check for typos"),
    handle: z.string().trim().max(60, "that handle is too long").default(""),
    package: z.enum(["short", "long"], "pick short or long"),
    song: z
      .string()
      .trim()
      .min(1, "tell me the song: a name or a link")
      .max(300, "keep the song to a name or one link"),
    songStart: z
      .string()
      .trim()
      .regex(/^$|^\d{1,2}:[0-5]\d$/, "write it as minutes:seconds, like 0:45")
      .default(""),
    vibes: z.array(z.enum(VIBES)).max(VIBES.length).default([]),
    notes: z.string().trim().max(2000, "notes are capped at 2000 characters").default(""),
    draftId: z
      .string()
      .regex(/^[a-zA-Z0-9-]{8,64}$/)
      .optional(),
    clipsLink: z.string().trim().max(1000, "that link is too long").default(""),
    uploads: z.array(uploadedClipSchema).max(MAX_FILES, `that's more than ${MAX_FILES} files. send the rest as a link`).default([]),
  })
  .superRefine((value, ctx) => {
    if (!value.clipsLink && value.uploads.length === 0) {
      ctx.addIssue({
        code: "custom",
        path: ["clips"],
        message: "add your clips: upload them or paste a link",
      });
    }
    if (value.clipsLink && !isHttpUrl(value.clipsLink)) {
      ctx.addIssue({
        code: "custom",
        path: ["clipsLink"],
        message: "that link doesn't look right. paste the share link from google drive, wetransfer, icloud or dropbox",
      });
    }
    if (value.uploads.length > 0 && !value.draftId) {
      ctx.addIssue({ code: "custom", path: ["clips"], message: "your uploads got lost. add them again" });
    }
  });

export type OrderInput = z.infer<typeof orderInputSchema>;

/** Flatten zod issues to { field: firstMessage } for the form. */
export function fieldErrors(error: z.ZodError): Record<string, string> {
  const out: Record<string, string> = {};
  for (const issue of error.issues) {
    const key = String(issue.path[0] ?? "form");
    if (!out[key]) out[key] = issue.message;
  }
  return out;
}
