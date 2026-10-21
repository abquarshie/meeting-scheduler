import "server-only";
import { timingSafeEqual } from "node:crypto";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { cache } from "react";
import { COOKIE, makeToken, readToken, SESSION_DAYS } from "./session";
import { nfc } from "./text";

// Sign-in works as the Streamlit app's auth.py: everyone types their name and the shared password (APP_PASSWORD),
// or their own password when APP_USERS lists them. Everyone who signs in can do everything; the name is what the
// change log records.

function users(): Map<string, string> {
  const out = new Map<string, string>();
  for (const pair of (process.env.APP_USERS ?? "").split(";")) {
    const at = pair.indexOf("=");
    if (at > 0) out.set(nfc(pair.slice(0, at)), pair.slice(at + 1));
  }
  return out;
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
  const ok = own !== undefined ? same(password, own) : same(password, process.env.APP_PASSWORD);
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
