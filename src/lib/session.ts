import { createHmac, timingSafeEqual } from "node:crypto";

// The sign-in cookie: base64url(JSON {n: name, e: expiry}) + "." + base64url(HMAC-SHA256 of that, SESSION_SECRET).
// api/py.py checks the same cookie with the same secret (signed_in_name), so keep the two in step.
export const COOKIE = "ms_session";
export const SESSION_DAYS = 30;

function secret(): string {
  const s = process.env.SESSION_SECRET;
  if (!s || s.length < 16) throw new Error("SESSION_SECRET is not set (any long random string, at least 16 characters).");
  return s;
}

const b64 = (b: Buffer) => b.toString("base64url");
const sign = (body: string) => b64(createHmac("sha256", secret()).update(body).digest());

export function makeToken(name: string, days = SESSION_DAYS): string {
  const body = b64(Buffer.from(JSON.stringify({ n: name, e: Math.floor(Date.now() / 1000) + days * 86400 })));
  return `${body}.${sign(body)}`;
}

export function readToken(token: string | undefined): string | null {
  if (!token || token.length > 1000 || !token.includes(".")) return null;
  const [body, sig] = [token.slice(0, token.lastIndexOf(".")), token.slice(token.lastIndexOf(".") + 1)];
  const want = Buffer.from(sign(body)), got = Buffer.from(sig);
  if (want.length !== got.length || !timingSafeEqual(want, got)) return null;
  try {
    const p = JSON.parse(Buffer.from(body, "base64url").toString("utf8")) as { n?: string; e?: number };
    if (!p.e || p.e < Date.now() / 1000) return null;
    return String(p.n ?? "");
  } catch {
    return null;
  }
}
