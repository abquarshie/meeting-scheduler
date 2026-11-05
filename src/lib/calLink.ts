import "server-only";
import { createHmac, timingSafeEqual } from "node:crypto";

// A participant's calendar feed lives at /cal/<id>-<signature>.ics, so a phone can subscribe without signing in.
// The signature is made with SESSION_SECRET; changing that secret retires every calendar link.

function sig(id: number): string {
  const s = process.env.SESSION_SECRET;
  if (!s || s.length < 16) throw new Error("SESSION_SECRET is not set.");
  return createHmac("sha256", s).update(`calendar|${id}`).digest("base64url").slice(0, 20);
}

export function calPath(id: number): string {
  return `/cal/${id}-${sig(id)}.ics`;
}

export function readCalToken(token: string): number | null {
  const m = String(token).replace(/\.ics$/, "").match(/^(\d{1,9})-([A-Za-z0-9_-]{20})$/);
  if (!m) return null;
  const id = Number(m[1]);
  const want = Buffer.from(sig(id)), got = Buffer.from(m[2]);
  return want.length === got.length && timingSafeEqual(want, got) ? id : null;
}
