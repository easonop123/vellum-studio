import { issueSignedToken } from "@vercel/blob";
import { handleUpload, handleUploadPresigned, type HandleUploadBody, type HandleUploadPresignedBody } from "@vercel/blob/client";
import { ALLOWED_CONTENT_TYPES, isAcceptedClipName, MAX_FILE_BYTES } from "@/lib/limits";

/**
 * Lets the browser upload a clip straight to Vercel Blob (the file never
 * passes through this server). Two flavours, depending on how Vercel
 * connected the store:
 *  - BLOB_READ_WRITE_TOKEN set: classic client token (`upload()` in the browser)
 *  - only BLOB_STORE_ID (OIDC): a presigned URL scoped to one file (`uploadPresigned()`)
 * Either way: only clips/<draft>/<file> paths, only video and photo types,
 * never more than the per-file cap, and the link expires in an hour.
 */
function checkUpload(pathname: string, clientPayload: string | null) {
  const match = /^clips\/([a-zA-Z0-9-]{8,64})\/[^/]+$/.exec(pathname);
  if (!match) throw new Error("uploads have to go in your order's folder");
  let draftId: unknown;
  try {
    draftId = clientPayload ? (JSON.parse(clientPayload) as { draftId?: unknown }).draftId : undefined;
  } catch {
    draftId = undefined;
  }
  if (draftId !== match[1]) throw new Error("upload doesn't match this order form");
  if (!isAcceptedClipName(pathname)) throw new Error("only video and photo files");
}

export async function POST(request: Request) {
  const body = (await request.json()) as HandleUploadBody | HandleUploadPresignedBody;
  try {
    if (body.type === "blob.generate-presigned-url") {
      const json = await handleUploadPresigned({
        body: body as HandleUploadPresignedBody,
        request,
        // Only used to verify upload-finished callbacks, which this site doesn't ask for.
        webhookPublicKey: process.env.BLOB_WEBHOOK_PUBLIC_KEY ?? "not-used",
        getSignedToken: async (pathname, clientPayload) => {
          checkUpload(pathname, clientPayload);
          const validUntil = Date.now() + 60 * 60 * 1000;
          const token = await issueSignedToken({
            pathname,
            operations: ["put"],
            validUntil,
            allowedContentTypes: ALLOWED_CONTENT_TYPES,
            maximumSizeInBytes: MAX_FILE_BYTES,
          });
          return {
            token,
            urlOptions: {
              validUntil,
              allowedContentTypes: ALLOWED_CONTENT_TYPES,
              maximumSizeInBytes: MAX_FILE_BYTES,
              addRandomSuffix: true,
            },
          };
        },
      });
      return Response.json(json);
    }

    const json = await handleUpload({
      body: body as HandleUploadBody,
      request,
      onBeforeGenerateToken: async (pathname, clientPayload) => {
        checkUpload(pathname, clientPayload);
        return {
          allowedContentTypes: ALLOWED_CONTENT_TYPES,
          maximumSizeInBytes: MAX_FILE_BYTES,
          addRandomSuffix: true,
          validUntil: Date.now() + 60 * 60 * 1000,
        };
      },
      // The order form reports finished uploads itself, so nothing to do here.
      onUploadCompleted: async () => {},
    });
    return Response.json(json);
  } catch (error) {
    const message = error instanceof Error ? error.message : "upload refused";
    return Response.json({ error: message }, { status: 400 });
  }
}
