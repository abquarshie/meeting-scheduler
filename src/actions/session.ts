"use server";
import { redirect } from "next/navigation";
import { logChange } from "@/lib/action";
import { checkSignIn, endSession, startSession } from "@/lib/auth";
import { cleared, failed, lockedFor, MAX_TRIES } from "@/lib/lockout";
import { nfc } from "@/lib/text";

export async function signInAction(_: string | null, form: FormData): Promise<string | null> {
  const name = nfc(form.get("name"));
  let wait: number;
  try {
    wait = await lockedFor();
  } catch (e) {
    console.error(e);
    return "Sign-in is unavailable right now. Please try again in a moment.";
  }
  if (wait > 0) return `Too many wrong passwords. Try again in ${Math.ceil(wait / 1000)} seconds.`;
  const problem = checkSignIn(name, String(form.get("password") ?? ""));
  if (problem) {
    await new Promise((r) => setTimeout(r, 600)); // slows down anyone guessing the password
    if (!name) return problem; // a missing name isn't a guess
    const n = await failed().catch((e) => { console.error(e); return 0; });
    if (n >= MAX_TRIES) return "Too many wrong passwords. Wait a minute and try again.";
    return `${problem} ${Math.max(MAX_TRIES - n, 1)} tries left.`;
  }
  await cleared().catch((e) => console.error(e));
  await startSession(name);
  try {
    await logChange(name, "Signed in", name);
  } catch (e) {
    console.error(e); // the change log line isn't worth refusing the sign-in over
  }
  const next = String(form.get("next") ?? "");
  redirect(next.startsWith("/") && !next.startsWith("//") ? next : "/");
}

export async function signOutAction() {
  await endSession();
  redirect("/login");
}
