"use server";
import { redirect } from "next/navigation";
import { logChange } from "@/lib/action";
import { checkSignIn, endSession, startSession } from "@/lib/auth";
import { nfc } from "@/lib/text";

export async function signInAction(_: string | null, form: FormData): Promise<string | null> {
  const name = nfc(form.get("name"));
  const problem = checkSignIn(name, String(form.get("password") ?? ""));
  if (problem) {
    await new Promise((r) => setTimeout(r, 600)); // slows down anyone guessing the password
    return problem;
  }
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
