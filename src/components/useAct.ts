"use client";
import { useTransition } from "react";
import { useToast } from "./Toaster";

type R = { ok: boolean; message?: string; error?: string };

/** Runs a server action (or a call to the Python function) and says how it went in a toast. */
export function useAct(): [boolean, (work: () => Promise<R>, then?: () => void) => void] {
  const toast = useToast();
  const [busy, start] = useTransition();
  return [busy, (work, then) => start(async () => {
    const r = await work();
    if (r.ok) {
      if (r.message) toast(r.message);
      then?.();
    } else toast(r.error ?? "Something went wrong.", { tone: "warn" });
  })];
}
