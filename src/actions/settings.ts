"use server";
import { attempt, logChange, ok, Refusal, setSetting } from "@/lib/action";
import { LANGUAGES, SAME_ROLE_GAP_DAYS, WEEKDAYS } from "@/lib/constants";
import { prisma } from "@/lib/db";
import { nfc } from "@/lib/text";

export async function setLanguage(language: string) {
  return attempt(async () => {
    if (!(LANGUAGES as readonly string[]).includes(language)) throw new Refusal("Unknown language.");
    await setSetting("slip_language", language);
    return ok(`Slips and printouts will be in ${language}.`);
  });
}

export async function savePrinting(input: { congregation: string; useAux: boolean; gaConvert: boolean }) {
  return attempt(async () => {
    await prisma.$transaction(async (tx) => {
      await setSetting("congregation", nfc(input.congregation), tx);
      await setSetting("use_aux", input.useAux ? "1" : "0", tx);
      await setSetting("ga_convert", input.gaConvert ? "1" : "0", tx);
    });
    return ok("Saved.");
  });
}

export async function saveMeetingDays(midweek: string, weekend: string) {
  return attempt(async (user) => {
    if (!WEEKDAYS.includes(midweek) || !WEEKDAYS.includes(weekend)) throw new Refusal("Pick a day.");
    await setSetting("midweek_day", midweek);
    await setSetting("weekend_day", weekend);
    await logChange(user, "Meeting days changed", `midweek ${midweek}, weekend ${weekend}`);
    return ok("Saved.");
  });
}

export async function saveRotation(days: number) {
  return attempt(async (user) => {
    const n = Math.round(days);
    if (!Number.isFinite(n) || n < 1 || n > 90) throw new Refusal(`Use a number from 1 to 90 (the default is ${SAME_ROLE_GAP_DAYS}).`);
    await setSetting("same_role_gap_days", String(n));
    await logChange(user, "Rotation rest period changed", `${n} day(s)`);
    return ok("Saved.");
  });
}

export async function saveLetterDetails(input: Record<string, string>) {
  return attempt(async () => {
    const keys = ["meeting_time", "hall_address", "talk_coordinator_signoff", "talk_coordinator_phone", "talk_coordinator_email"];
    await prisma.$transaction(async (tx) => {
      for (const k of keys) await setSetting(k, nfc(input[k]), tx);
    });
    return ok("Saved.");
  });
}

export async function removeEventWeek(id: number) {
  return attempt(async (user) => {
    await prisma.no_meeting_periods.deleteMany({ where: { id } });
    await logChange(user, "Assembly/convention week removed", `id ${id}`);
    return ok("Removed.");
  });
}

export async function removeTemplate(name: string) {
  return attempt(async (user) => {
    if (!/^(s89|s140)_(English|Ga)$/.test(name)) throw new Refusal("Unknown form.");
    await prisma.templates.deleteMany({ where: { name } });
    await logChange(user, "Blank form removed", name);
    return ok("Removed.");
  });
}
