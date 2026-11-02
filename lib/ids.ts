import { randomInt } from "node:crypto";

// No 0/O, 1/I/L: easy to read out over a DM.
const ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ";

export function newOrderId(): string {
  let id = "";
  for (let i = 0; i < 5; i++) id += ALPHABET[randomInt(ALPHABET.length)];
  return `VS-${id}`;
}

export function isOrderId(value: string): boolean {
  return /^VS-[23456789ABCDEFGHJKMNPQRSTUVWXYZ]{5}$/.test(value);
}
