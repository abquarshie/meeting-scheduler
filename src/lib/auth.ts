import "server-only";
import { timingSafeEqual } from "node:crypto";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { cache } from "react";
import { COOKIE, makeToken, readToken, SESSION_DAYS } from "./session";
import { nfc } from "./text";

// Sign-in works as the Streamlit app's auth.py: everyone types their name and the shared password (APP_PASSWORD),
// or their own password when APP_USERS lists them. Everyone who signs in can do everything, except a user whose
// APP_USERS entry ends in ":weekend" ("Kofi=his-password:weekend"): he works on weekend meetings only. The role is
// read from the environment on every request (api/py.py does the same), so changing it takes effect at once.
// The name is what the change log records.

export type Role = "full" | "weekend";
const WEEKEND_SUFFIX = ":weekend";

function users(): Map<string, { password: string; role: Role }> {
  const out = new Map<string, { password: string; role: Role }>();
  for (const pair of (process.env.APP_USERS ?? "").split(";")) {
    const at = pair.indexOf("=");
    if (at <= 0) continue;
    const value = pair.slice(at + 1);
    const weekend = value.endsWith(WEEKEND_SUFFIX);
    out.set(nfc(pair.slice(0, at)), {
      password: weekend ? value.slice(0, -WEEKEND_SUFFIX.length) : value, role: weekend ? "weekend" : "full",
    });
  }
  return out;
}

export function roleOf(name: string): Role {
  return users().get(nfc(name))?.role ?? "full";
}

export function signInConfigured(): boolean {
  return Boolean(process.env.APP_PASSWORD) || users().size > 0;
}

function same(given: string, expected: string | undefined): boolean {
  if (!expected) return false;
  const a = Buffer.from(given.normalize("NFC")), b = Buffer.from(expected.normalize("NFC"));
  return a.length === b.length && timingSafeEqual(a, b);
}

export function checkSignIn(nameIn: string, password: string): string | null {
  const name = nfc(nameIn);
  if (!name) return "Enter your name so changes can be credited to you.";
  if (!signInConfigured()) return "Sign-in isn't set up yet: add APP_PASSWORD to the app's environment variables.";
  const own = users().get(name);
  const ok = own !== undefined ? same(password, own.password) : same(password, process.env.APP_PASSWORD);
  return ok ? null : "Wrong name or password.";
}

export async function startSession(name: string): Promise<void> {
  (await cookies()).set(COOKIE, makeToken(nfc(name)), {
    httpOnly: true, sameSite: "lax", secure: process.env.NODE_ENV === "production", path: "/",
    maxAge: SESSION_DAYS * 86400,
  });
}

export async function endSession(): Promise<void> {
  (await cookies()).delete(COOKIE);
}

/** Who is signed in, or null. */
export const getUser = cache(async (): Promise<string | null> => readToken((await cookies()).get(COOKIE)?.value));

export async function requireUser(): Promise<string> {
  const user = await getUser();
  if (user === null) redirect("/login");
  return user;
}

/** The signed-in user's role ("full" when signed out, since those pages redirect to sign-in anyway). */
export async function getRole(): Promise<Role> {
  const user = await getUser();
  return user === null ? "full" : roleOf(user);
}

/** For pages a weekend-only user can't open: sends him Home. */
export async function requireFull(): Promise<string> {
  const user = await requireUser();
  if (roleOf(user) === "weekend") redirect("/");
  return user;
}
