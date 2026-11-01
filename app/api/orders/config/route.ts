import { connection } from "next/server";
import { checkoutMode, isStripeTestMode } from "@/lib/payments";
import { uploadMode } from "@/lib/store";

/** Tells the order form how to upload and what to say about payment. */
export async function GET() {
  await connection();
  return Response.json(
    {
      uploadMode: uploadMode(),
      blobAccess: process.env.BLOB_ACCESS === "public" ? "public" : "private",
      checkout: checkoutMode(),
      testMode: isStripeTestMode(),
    },
    { headers: { "cache-control": "no-store" } },
  );
}
