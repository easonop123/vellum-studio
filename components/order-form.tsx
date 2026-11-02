"use client";

import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import {
  formatBytes,
  guessContentType,
  isAcceptedClipName,
  MAX_FILE_BYTES,
  MAX_FILES,
  MAX_TOTAL_BYTES,
  MULTIPART_ABOVE_BYTES,
  safeFileName,
} from "@/lib/limits";
import { fieldErrors, orderInputSchema, VIBES, type UploadedClip } from "@/lib/order-schema";
import { formatPrice, PACKAGE_IDS, SITE, timecode, type PackageId } from "@/lib/site";

type Config = {
  uploadMode: "blob" | "blob-presigned" | "local";
  blobAccess: "public" | "private";
  checkout: "stripe" | "fake" | "off";
  testMode: boolean;
};

type UploadStatus = "queued" | "uploading" | "done" | "error";
type UploadItem = {
  key: string;
  file: File;
  progress: number;
  status: UploadStatus;
  error?: string;
  result?: UploadedClip;
  abort: AbortController;
};

const CONCURRENT_UPLOADS = 2;

function newDraftId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
}

function uploadLocal(item: UploadItem, draftId: string, onProgress: (pct: number) => void): Promise<UploadedClip> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const params = new URLSearchParams({ draft: draftId, name: item.file.name });
    xhr.open("POST", `/api/dev-upload?${params.toString()}`);
    xhr.setRequestHeader("content-type", guessContentType(item.file.name, item.file.type));
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress((e.loaded / e.total) * 100);
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        const body = JSON.parse(xhr.responseText) as { pathname: string; url: string; size: number; contentType: string };
        resolve({ pathname: body.pathname, url: body.url, name: item.file.name, size: body.size, contentType: body.contentType });
      } else {
        let message = "upload failed";
        try {
          message = (JSON.parse(xhr.responseText) as { error?: string }).error ?? message;
        } catch {}
        reject(new Error(message));
      }
    };
    xhr.onerror = () => reject(new Error("the connection dropped"));
    xhr.onabort = () => reject(new Error("cancelled"));
    item.abort.signal.addEventListener("abort", () => xhr.abort());
    xhr.send(item.file);
  });
}

async function uploadToBlob(
  item: UploadItem,
  draftId: string,
  access: "public" | "private",
  presigned: boolean,
  onProgress: (pct: number) => void,
): Promise<UploadedClip> {
  const { upload, uploadPresigned } = await import("@vercel/blob/client");
  const send = presigned ? uploadPresigned : upload;
  const result = await send(`clips/${draftId}/${safeFileName(item.file.name)}`, item.file, {
    access,
    handleUploadUrl: "/api/upload",
    clientPayload: JSON.stringify({ draftId }),
    multipart: item.file.size > MULTIPART_ABOVE_BYTES,
    contentType: guessContentType(item.file.name, item.file.type),
    abortSignal: item.abort.signal,
    onUploadProgress: ({ percentage }) => onProgress(percentage),
  });
  return {
    pathname: result.pathname,
    url: result.url,
    name: item.file.name,
    size: item.file.size,
    contentType: result.contentType,
  };
}

function FieldError({ id, message }: { id: string; message?: string }) {
  if (!message) return null;
  return (
    <p id={id} className="mt-2 text-small text-safelight">
      {message}
    </p>
  );
}

const noSubscribe = () => () => {};

export function OrderForm() {
  const [config, setConfig] = useState<Config | null>(null);
  const configRef = useRef<Config | null>(null);

  // ?package=long from the pricing buttons, ?cancelled=VS-XXXXX back from Stripe.
  const search = useSyncExternalStore(noSubscribe, () => window.location.search, () => "");
  const params = useMemo(() => new URLSearchParams(search), [search]);
  const cancelledParam = params.get("cancelled") ?? "";
  const cancelledOrder = /^VS-[A-Z0-9]{5}$/.test(cancelledParam) ? cancelledParam : null;
  const urlPackage = params.get("package");

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [handle, setHandle] = useState("");
  const [chosenPkg, setPkg] = useState<PackageId | null>(null);
  const pkg: PackageId = chosenPkg ?? (urlPackage === "long" ? "long" : "short");
  const [song, setSong] = useState("");
  const [songStart, setSongStart] = useState("");
  const [vibes, setVibes] = useState<string[]>([]);
  const [notes, setNotes] = useState("");
  const [clipsLink, setClipsLink] = useState("");

  const [uploads, setUploads] = useState<UploadItem[]>([]);
  const uploadsRef = useRef<UploadItem[]>([]);
  const [rejected, setRejected] = useState<string[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const draftId = useRef<string | null>(null);

  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const formRef = useRef<HTMLFormElement>(null);

  const price = SITE.packages[pkg].priceCents;
  const priceText = `${formatPrice(price)} ${SITE.currency}`;
  const totalBytes = useMemo(() => uploads.reduce((sum, u) => sum + u.file.size, 0), [uploads]);
  const busy = uploads.filter((u) => u.status === "queued" || u.status === "uploading").length;
  const failed = uploads.filter((u) => u.status === "error").length;

  // The upload list lives in a ref too, so the queue always sees the latest state.
  const commit = useCallback((next: UploadItem[]) => {
    uploadsRef.current = next;
    setUploads(next);
  }, []);
  const patch = useCallback(
    (key: string, change: Partial<UploadItem>) => commit(uploadsRef.current.map((u) => (u.key === key ? { ...u, ...change } : u))),
    [commit],
  );

  // Upload queue: a couple at a time so phones on mobile data don't choke.
  const pumpRef = useRef<() => void>(() => {});
  const pump = useCallback(() => pumpRef.current(), []);
  useEffect(() => {
    pumpRef.current = () => {
      const cfg = configRef.current;
      if (!cfg) return;
      const list = uploadsRef.current;
      const running = list.filter((u) => u.status === "uploading").length;
      const next = list.filter((u) => u.status === "queued").slice(0, Math.max(0, CONCURRENT_UPLOADS - running));
      for (const item of next) {
        patch(item.key, { status: "uploading", progress: 0 });
        draftId.current ??= newDraftId();
        const onProgress = (pct: number) => patch(item.key, { progress: Math.min(99, pct) });
        const job =
          cfg.uploadMode === "local"
            ? uploadLocal(item, draftId.current, onProgress)
            : uploadToBlob(item, draftId.current, cfg.blobAccess, cfg.uploadMode === "blob-presigned", onProgress);
        job
          .then((result) => {
            patch(item.key, { status: "done", progress: 100, result });
            pumpRef.current();
          })
          .catch((err: Error) => {
            if (item.abort.signal.aborted) return;
            patch(item.key, { status: "error", error: err.message || "upload failed" });
            pumpRef.current();
          });
      }
    };
  }, [patch]);

  useEffect(() => {
    const ready = (cfg: Config) => {
      configRef.current = cfg;
      setConfig(cfg);
      pump();
    };
    fetch("/api/orders/config")
      .then((r) => r.json() as Promise<Config>)
      .then(ready)
      .catch(() => ready({ uploadMode: "blob", blobAccess: "private", checkout: "stripe", testMode: false }));
  }, [pump]);

  function addFiles(files: FileList | File[]) {
    const incoming = Array.from(files);
    const problems: string[] = [];
    const accepted: UploadItem[] = [];
    let count = uploads.length;
    let bytes = totalBytes;
    for (const file of incoming) {
      if (!isAcceptedClipName(file.name)) {
        problems.push(`${file.name} isn't a video or photo.`);
      } else if (file.size > MAX_FILE_BYTES) {
        problems.push(`${file.name} is ${formatBytes(file.size)}, over the ${formatBytes(MAX_FILE_BYTES)} limit. send it as a link instead.`);
      } else if (count + 1 > MAX_FILES) {
        problems.push(`that's more than ${MAX_FILES} files. send the rest as a link.`);
        break;
      } else if (bytes + file.size > MAX_TOTAL_BYTES) {
        problems.push(`${file.name} would take you over ${formatBytes(MAX_TOTAL_BYTES)} in total. send the rest as a link.`);
      } else {
        count += 1;
        bytes += file.size;
        accepted.push({
          key: `${file.name}-${file.size}-${file.lastModified}-${Math.random().toString(36).slice(2, 7)}`,
          file,
          progress: 0,
          status: "queued",
          abort: new AbortController(),
        });
      }
    }
    setRejected(problems);
    if (accepted.length) {
      commit([...uploadsRef.current, ...accepted]);
      setErrors((e) => ({ ...e, clips: "" }));
      pump();
    }
  }

  function removeUpload(item: UploadItem) {
    item.abort.abort();
    commit(uploadsRef.current.filter((u) => u.key !== item.key));
    pump();
  }

  function retryUpload(item: UploadItem) {
    patch(item.key, { status: "queued", error: undefined, progress: 0, abort: new AbortController() });
    pump();
  }

  function focusFirstError(errs: Record<string, string>) {
    const order = ["name", "email", "handle", "package", "song", "songStart", "clips", "clipsLink", "notes"];
    const first = order.find((k) => errs[k]);
    if (!first) return;
    const el = formRef.current?.querySelector<HTMLElement>(`[data-field="${first}"]`);
    el?.focus();
    el?.scrollIntoView({ block: "center" });
  }

  async function onSubmit(event: React.FormEvent) {
    event.preventDefault();
    setFormError(null);
    const done = uploads.filter((u) => u.status === "done" && u.result).map((u) => u.result!);
    const payload = {
      name,
      email,
      handle,
      package: pkg,
      song,
      songStart,
      vibes,
      notes,
      clipsLink,
      draftId: draftId.current ?? undefined,
      uploads: done,
    };
    const parsed = orderInputSchema.safeParse(payload);
    const errs: Record<string, string> = parsed.success ? {} : fieldErrors(parsed.error);
    if (busy > 0) errs.clips = `wait for your uploads to finish (${busy} still going).`;
    else if (failed > 0) errs.clips = "one of your uploads failed. try it again or remove it.";
    setErrors(errs);
    if (Object.values(errs).some(Boolean)) {
      focusFirstError(errs);
      return;
    }
    setSubmitting(true);
    try {
      const res = await fetch("/api/orders", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(payload),
      });
      const body = (await res.json().catch(() => ({}))) as { url?: string; errors?: Record<string, string>; formError?: string };
      if (res.ok && body.url) {
        window.location.assign(body.url);
        return;
      }
      if (body.errors) {
        setErrors(body.errors);
        focusFirstError(body.errors);
      }
      setFormError(body.formError ?? (body.errors ? null : "something went wrong sending your order. try again in a minute."));
    } catch {
      setFormError("couldn't reach the server. check your connection and try again.");
    }
    setSubmitting(false);
  }

  const invalid = (key: string) => (errors[key] ? { "aria-invalid": true as const, "aria-describedby": `${key}-error` } : {});

  return (
    <form ref={formRef} noValidate onSubmit={onSubmit} className="mt-10" aria-describedby={formError ? "form-error" : undefined}>
      {cancelledOrder ? (
        <div role="status" className="mb-10 rounded-[3px] border border-graphite bg-well p-4 text-bone/90">
          your payment didn&apos;t go through, so nothing was charged. order{" "}
          <span className="mono text-bone">{cancelledOrder}</span> is saved.{" "}
          <a href={`/api/orders/${cancelledOrder}/pay`} className="underline decoration-safelight decoration-2 hover:text-bone">
            try paying again
          </a>{" "}
          or fill this in fresh.
        </div>
      ) : null}

      <fieldset className="grid gap-6">
        <legend className="display mb-6 text-h3">you</legend>
        <div>
          <label htmlFor="name" className="block font-medium">
            name
          </label>
          <input id="name" data-field="name" name="name" autoComplete="name" className="field mt-2" value={name} onChange={(e) => setName(e.target.value)} {...invalid("name")} />
          <FieldError id="name-error" message={errors.name} />
        </div>
        <div>
          <label htmlFor="email" className="block font-medium">
            email
          </label>
          <p id="email-hint" className="text-small text-ash">
            i&apos;ll send your edit here.
          </p>
          <input
            id="email"
            data-field="email"
            name="email"
            type="email"
            inputMode="email"
            autoComplete="email"
            className="field mt-2"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            {...invalid("email")}
          />
          <FieldError id="email-error" message={errors.email} />
        </div>
        <div>
          <label htmlFor="handle" className="block font-medium">
            instagram or tiktok handle <span className="font-normal text-ash">(optional)</span>
          </label>
          <input
            id="handle"
            data-field="handle"
            name="handle"
            autoCapitalize="none"
            autoCorrect="off"
            placeholder="@yourname"
            className="field mt-2"
            value={handle}
            onChange={(e) => setHandle(e.target.value)}
            {...invalid("handle")}
          />
          <FieldError id="handle-error" message={errors.handle} />
        </div>
      </fieldset>

      <fieldset className="mt-14 grid gap-6">
        <legend className="display mb-6 text-h3">the edit</legend>
        <div role="radiogroup" aria-label="length" className="grid grid-cols-2 gap-3" data-field="package" tabIndex={-1}>
          {PACKAGE_IDS.map((id) => {
            const p = SITE.packages[id];
            const selected = pkg === id;
            return (
              <label
                key={id}
                className={`relative cursor-pointer rounded-[3px] border p-4 transition-colors ${
                  selected ? "border-safelight bg-safelight/[0.07]" : "border-graphite bg-well hover:border-[#3a3a40]"
                }`}
              >
                <input type="radio" name="package" value={id} checked={selected} onChange={() => setPkg(id)} className="peer sr-only" />
                <span className="absolute inset-0 rounded-[3px] peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-bone" aria-hidden />
                <span className="display block text-lead">{p.label}</span>
                <span className="mt-1 block text-small text-ash">up to {p.maxSeconds} s</span>
                <span className="mt-3 block text-label text-bone/70 mono">{timecode(p.maxSeconds)}</span>
                <span className="mt-1 block text-lead font-bold">
                  {formatPrice(p.priceCents)} <span className="text-label font-medium text-ash mono">{SITE.currency.toUpperCase()}</span>
                </span>
              </label>
            );
          })}
        </div>

        <div>
          <label htmlFor="song" className="block font-medium">
            song
          </label>
          <p className="text-small text-ash">a name and artist, or a spotify, youtube or tiktok link.</p>
          <input id="song" data-field="song" name="song" className="field mt-2" value={song} onChange={(e) => setSong(e.target.value)} {...invalid("song")} />
          <FieldError id="song-error" message={errors.song} />
        </div>

        <div>
          <label htmlFor="songStart" className="block font-medium">
            start the edit at <span className="font-normal text-ash">(optional)</span>
          </label>
          <p className="text-small text-ash">the part of the song you want, like 0:45. leave it empty and i&apos;ll pick.</p>
          <input
            id="songStart"
            data-field="songStart"
            name="songStart"
            inputMode="numeric"
            placeholder="0:45"
            className="field mt-2 max-w-[8rem] mono"
            value={songStart}
            onChange={(e) => setSongStart(e.target.value)}
            {...invalid("songStart")}
          />
          <FieldError id="songStart-error" message={errors.songStart} />
        </div>

        <div>
          <p id="vibe-label" className="font-medium">
            vibe <span className="font-normal text-ash">(pick any)</span>
          </p>
          <div className="mt-3 flex flex-wrap gap-2" role="group" aria-labelledby="vibe-label">
            {VIBES.map((vibe) => {
              const on = vibes.includes(vibe);
              return (
                <button
                  key={vibe}
                  type="button"
                  aria-pressed={on}
                  onClick={() => setVibes((v) => (on ? v.filter((x) => x !== vibe) : [...v, vibe]))}
                  className={`min-h-11 rounded-full border px-4 transition-colors ${
                    on ? "border-safelight bg-safelight text-ink" : "border-graphite bg-well text-bone hover:border-[#3a3a40]"
                  }`}
                >
                  {vibe}
                </button>
              );
            })}
          </div>
        </div>

        <div>
          <label htmlFor="notes" className="block font-medium">
            notes <span className="font-normal text-ash">(optional)</span>
          </label>
          <p className="text-small text-ash">anything i should know: a title for the edit, clips you love, people to feature.</p>
          <textarea
            id="notes"
            data-field="notes"
            name="notes"
            rows={4}
            className="field mt-2 min-h-[7rem] resize-y"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            {...invalid("notes")}
          />
          <FieldError id="notes-error" message={errors.notes} />
        </div>
      </fieldset>

      <fieldset className="mt-14">
        <legend className="display mb-3 text-h3">your clips</legend>
        <p className="text-bone/80">10 to 40 clips is ideal. upload them here, paste a link, or both.</p>

        <label
          htmlFor="files"
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            if (e.dataTransfer.files.length) addFiles(e.dataTransfer.files);
          }}
          className={`mt-5 flex min-h-36 cursor-pointer flex-col items-center justify-center rounded-[3px] border border-dashed px-4 py-8 text-center transition-colors ${
            dragOver ? "border-safelight bg-safelight/[0.06]" : errors.clips ? "border-safelight" : "border-[#46464d] bg-well hover:border-bone/60"
          }`}
        >
          <span className="text-lead font-bold">drop clips here or tap to choose</span>
          <span className="mt-2 text-label text-ash mono">
            up to {MAX_FILES} files, {formatBytes(MAX_FILE_BYTES)} each, {formatBytes(MAX_TOTAL_BYTES)} total
          </span>
          <input
            id="files"
            data-field="clips"
            type="file"
            multiple
            accept="video/*,image/*,.mov,.mp4,.m4v,.heic,.insv,.mts"
            className="sr-only"
            aria-describedby={errors.clips ? "clips-error" : undefined}
            onChange={(e) => {
              if (e.target.files?.length) addFiles(e.target.files);
              e.target.value = "";
            }}
          />
        </label>
        <FieldError id="clips-error" message={errors.clips} />
        {rejected.length ? (
          <ul className="mt-3 grid gap-1 text-small text-safelight" aria-live="polite">
            {rejected.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        ) : null}

        {uploads.length ? (
          <ul className="mt-5 grid gap-2" aria-label="your uploads">
            {uploads.map((u) => (
              <li key={u.key} className="rounded-[3px] bg-well px-3 py-2.5" data-status={u.status}>
                <div className="flex items-center justify-between gap-3 text-small">
                  <span className="min-w-0 truncate mono">{u.file.name}</span>
                  <span className="shrink-0 text-ash mono">
                    {u.status === "done" ? formatBytes(u.file.size) : u.status === "error" ? "failed" : `${Math.round(u.progress)}%`}
                  </span>
                </div>
                <div
                  className="mt-2 h-1 overflow-hidden rounded-full bg-graphite"
                  role="progressbar"
                  aria-label={`${u.file.name} upload`}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={Math.round(u.progress)}
                >
                  <div
                    className={`h-full transition-[width] duration-200 ${u.status === "error" ? "bg-ash" : u.status === "done" ? "bg-bone" : "bg-safelight"}`}
                    style={{ width: `${u.status === "error" ? 100 : u.progress}%` }}
                  />
                </div>
                <div className="mt-1.5 flex items-center justify-between gap-3 text-small">
                  <span className={u.status === "error" ? "text-safelight" : "text-ash"}>
                    {u.status === "queued" && "waiting"}
                    {u.status === "uploading" && "uploading"}
                    {u.status === "done" && "uploaded"}
                    {u.status === "error" && (u.error ?? "upload failed")}
                  </span>
                  <span className="flex gap-3">
                    {u.status === "error" ? (
                      <button type="button" className="underline hover:text-bone" onClick={() => retryUpload(u)}>
                        try again
                      </button>
                    ) : null}
                    <button type="button" className="text-ash underline hover:text-bone" onClick={() => removeUpload(u)}>
                      remove
                    </button>
                  </span>
                </div>
              </li>
            ))}
          </ul>
        ) : null}

        <div className="mt-8">
          <label htmlFor="clipsLink" className="block font-medium">
            or paste a link
          </label>
          <p className="text-small text-ash">google drive, wetransfer, icloud or dropbox. best for big batches.</p>
          <input
            id="clipsLink"
            data-field="clipsLink"
            name="clipsLink"
            type="url"
            inputMode="url"
            autoCapitalize="none"
            placeholder="https://"
            className="field mt-2"
            value={clipsLink}
            onChange={(e) => setClipsLink(e.target.value)}
            {...invalid("clipsLink")}
          />
          <FieldError id="clipsLink-error" message={errors.clipsLink} />
        </div>
      </fieldset>

      <div className="sticky bottom-0 z-20 -mx-4 mt-14 border-t border-graphite bg-ink/95 px-4 pt-4 pb-[max(1rem,env(safe-area-inset-bottom))] backdrop-blur sm:mx-0 sm:rounded-[3px] sm:border sm:px-5">
        {formError ? (
          <p id="form-error" role="alert" className="mb-3 text-small text-safelight">
            {formError}
          </p>
        ) : null}
        <div className="flex items-center justify-between gap-4">
          <div className="min-w-0">
            <p className="text-small text-ash">{pkg} edit</p>
            <p className="text-lead font-bold">
              {formatPrice(price)} <span className="text-label font-medium text-ash mono">{SITE.currency.toUpperCase()}</span>
            </p>
          </div>
          <button type="submit" className="btn-primary shrink-0" disabled={submitting} aria-busy={submitting}>
            {submitting ? "one sec..." : `pay ${priceText}`}
          </button>
        </div>
        <p className="mt-2 text-small text-ash" data-testid="checkout-note">
          {config?.checkout === "fake"
            ? "test checkout: no real payment is taken."
            : config?.testMode
              ? "test mode: pay with card 4242 4242 4242 4242, any future date, any cvc."
              : "you'll pay by card on stripe's checkout page."}
        </p>
      </div>
    </form>
  );
}
