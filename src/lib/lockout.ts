import "server-only";
import { prisma } from "./db";

// Wrong passwords are counted in the settings table (signin_fails, signin_locked), so the lockout holds across all of
// Vercel's short-lived instances. Five wrong tries lock sign-in for a minute, for everyone.

export const MAX_TRIES = 5;
export const LOCK_MS = 60_000;

/** Milliseconds until sign-in opens again, or 0. */
export async function lockedFor(): Promise<number> {
  const row = await prisma.settings.findUnique({ where: { key: "signin_locked" } });
  const until = row?.value ? Date.parse(row.value) : NaN;
  return Number.isFinite(until) ? Math.max(until - Date.now(), 0) : 0;
}

/** Counts one wrong password (in one statement, so parallel guesses all count) and returns the count. */
export async function failed(): Promise<number> {
  const rows = await prisma.$queryRaw<{ value: string }[]>`
    INSERT INTO settings (key, value) VALUES ('signin_fails', '1')
    ON CONFLICT (key) DO UPDATE SET value = (COALESCE(NULLIF(settings.value, '')::int, 0) + 1)::text
    RETURNING value`;
  const n = Number(rows[0]?.value ?? 1);
  if (n >= MAX_TRIES) {
    const until = new Date(Date.now() + LOCK_MS).toISOString();
    await prisma.$transaction([
      prisma.settings.upsert({ where: { key: "signin_locked" }, create: { key: "signin_locked", value: until }, update: { value: until } }),
      prisma.settings.update({ where: { key: "signin_fails" }, data: { value: "0" } }),
    ]);
  }
  return n;
}

export async function cleared() {
  await prisma.settings.updateMany({ where: { key: { in: ["signin_fails", "signin_locked"] } }, data: { value: "" } });
}
