import "server-only";
import { createHmac, timingSafeEqual } from "node:crypto";

// A participant's calendar feed lives at /cal/<id>-<signature>.ics, so a phone can subscribe without signing in.
// The signature is made with SESSION_SECRET; changing that secret retires every calendar link.
// New links carry 10 characters of it (60 bits: far too many to guess). Links sent earlier carry 20 and keep working.

const SHORT = 10, LONG = 20;

function sig(id: number): string {
  const s = process.env.SESSION_SECRET;
  if (!s || s.length < 16) throw new Error("SESSION_SECRET is not set.");
  return createHmac("sha256", s).update(`calendar|${id}`).digest("base64url").slice(0, LONG);
}

export function calPath(id: number): string {
  return `/cal/${id}-${sig(id).slice(0, SHORT)}.ics`;
}

export function readCalToken(token: string): number | null {
  const m = String(token).replace(/\.ics$/, "").match(/^(\d{1,9})-([A-Za-z0-9_-]+)$/);
  if (!m || (m[2].length !== SHORT && m[2].length !== LONG)) return null;
  const id = Number(m[1]);
  const want = Buffer.from(sig(id).slice(0, m[2].length)), got = Buffer.from(m[2]);
  return timingSafeEqual(want, got) ? id : null;
}
