import "server-only";
import { prisma, type Tx } from "./db";

// Participants' WhatsApp numbers, for reminders. Kept as one JSON row in settings ("participant_phones":
// {"<student id>": "024 123 4567"}) rather than a new column, so the Python app's tables stay exactly as they are
// and the numbers travel with every backup of the settings table.

const KEY = "participant_phones";

export async function getPhones(db: Tx | typeof prisma = prisma): Promise<Record<string, string>> {
  const row = await db.settings.findUnique({ where: { key: KEY } });
  try {
    const v = JSON.parse(row?.value || "{}");
    return v && typeof v === "object" ? v : {};
  } catch {
    return {};
  }
}

/** Saves (or with "" removes) one participant's number, merged in one statement so two saves never clash. */
export async function setPhone(id: number, phone: string, db: Tx | typeof prisma = prisma) {
  const clean = cleanPhone(phone);
  if (clean) {
    const one = JSON.stringify({ [String(id)]: clean });
    await db.$executeRaw`
      INSERT INTO settings (key, value) VALUES (${KEY}, ${one})
      ON CONFLICT (key) DO UPDATE SET value = (COALESCE(NULLIF(settings.value, ''), '{}')::jsonb || ${one}::jsonb)::text`;
  } else {
    await db.$executeRaw`
      UPDATE settings SET value = (COALESCE(NULLIF(value, ''), '{}')::jsonb - ${String(id)}::text)::text WHERE key = ${KEY}`;
  }
}

export function cleanPhone(v: unknown): string {
  return String(v ?? "").replace(/[^\d+ ()-]/g, "").replace(/\s+/g, " ").trim().slice(0, 24);
}

/** Digits as WhatsApp wants them, with Ghana's 233 for a leading 0; "" when it isn't a usable number. */
export function waNumber(phone: string | null | undefined): string {
  let d = String(phone ?? "").replace(/[^\d+]/g, "");
  if (d.startsWith("+")) d = d.slice(1);
  else if (d.startsWith("00")) d = d.slice(2);
  else if (d.startsWith("0") && d.length === 10) d = `233${d.slice(1)}`;
  d = d.replace(/\D/g, "");
  return d.length >= 9 && d.length <= 15 ? d : "";
}
