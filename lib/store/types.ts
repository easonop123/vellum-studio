import type { OrderInput, UploadedClip } from "@/lib/order-schema";
import type { PackageId } from "@/lib/site";

export type CheckoutKind = "stripe" | "fake";

/** Written once when the form is submitted. Never changed afterwards. */
export interface OrderRecord {
  id: string;
  createdAt: string;
  name: string;
  email: string;
  handle: string;
  package: PackageId;
  song: string;
  songStart: string;
  vibes: OrderInput["vibes"];
  notes: string;
  clipsLink: string;
  draftId?: string;
  uploads: UploadedClip[];
  amountCents: number;
  currency: string;
  checkout: CheckoutKind;
}

export interface PaymentInfo {
  paidAt: string;
  method: CheckoutKind;
  sessionId?: string;
  amountTotal?: number | null;
  currency?: string | null;
  livemode?: boolean;
}

export type OrderStatus = "unpaid" | "paid" | "delivered";

export interface OrderView extends OrderRecord {
  status: OrderStatus;
  payment?: PaymentInfo;
  deliveredAt?: string;
  clipsDeletedAt?: string;
}

export interface StoredClip {
  pathname: string;
  size: number;
  uploadedAt: Date;
}

export interface OrderStore {
  readonly kind: "blob" | "file";
  create(record: OrderRecord): Promise<void>;
  get(id: string): Promise<OrderView | null>;
  list(): Promise<OrderView[]>;
  /** Idempotent: returns "already" if the order was paid before. */
  markPaid(id: string, info: PaymentInfo): Promise<"marked" | "already" | "missing">;
  setDelivered(id: string, delivered: boolean): Promise<void>;
  markClipsDeleted(id: string): Promise<void>;

  // clips
  readonly uploadMode: "blob" | "local";
  clipExists(pathname: string): Promise<{ size: number } | null>;
  /** URL the admin's browser can open to get the file. */
  clipUrl(pathname: string, opts?: { download?: boolean }): Promise<string>;
  clipStream(pathname: string): Promise<ReadableStream<Uint8Array> | null>;
  listClips(): Promise<StoredClip[]>;
  deleteClips(pathnames: string[]): Promise<void>;
}

export function deriveStatus(paid: boolean, delivered: boolean): OrderStatus {
  if (delivered) return "delivered";
  return paid ? "paid" : "unpaid";
}

export class ConfigError extends Error {}
