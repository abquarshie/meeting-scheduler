import "server-only";
import { revalidatePath } from "next/cache";
import { requireUser } from "./auth";
import { prisma, type Tx } from "./db";

export type Result = { ok: true; message: string } | { ok: false; error: string };

export class Refusal extends Error {}

export function ok(message: string): Result {
  revalidatePath("/", "layout"); // every page reads the same data, so all of them refresh
  return { ok: true, message };
}

/** Runs a server action's work as the signed-in person, turning a refusal or a database error into a message. */
export async function attempt(work: (user: string) => Promise<Result>): Promise<Result> {
  try {
    return await work(await requireUser());
  } catch (e) {
    if (e instanceof Refusal) return { ok: false, error: e.message };
    const digest = (e as { digest?: string })?.digest;
    if (typeof digest === "string" && digest.startsWith("NEXT_REDIRECT")) throw e; // signed out: let it redirect
    console.error(e);
    return { ok: false, error: "That didn't save. Please try again; if it keeps happening, the database may be unreachable." };
  }
}

/** A line in the change log, in the same table and format as db.log_change. */
export async function logChange(user: string, action: string, details = "", tx: Tx | typeof prisma = prisma) {
  const ts = new Date().toISOString().slice(0, 19); // isoformat(timespec="seconds"), server time (UTC)
  await tx.audit_log.create({ data: { ts, user, action, details } });
}

export async function gaOn(tx: Tx | typeof prisma = prisma): Promise<boolean> {
  const row = await tx.settings.findUnique({ where: { key: "ga_convert" } });
  return row?.value === "1";
}

export async function setSetting(k: string, value: string, tx: Tx | typeof prisma = prisma) {
  await tx.settings.upsert({ where: { key: k }, create: { key: k, value }, update: { value } });
}
