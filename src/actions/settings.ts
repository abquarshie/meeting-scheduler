"use server";
import { attempt, attemptFull, logChange, needId, ok, Refusal, setSetting } from "@/lib/action";
import { LANGUAGES, SAME_ROLE_GAP_DAYS, WEEKDAYS } from "@/lib/constants";
import { prisma } from "@/lib/db";
import { nfc } from "@/lib/text";
import { parseTime } from "@/lib/reminders";

export async function setLanguage(language: string) {
  return attemptFull(async () => {
    if (!(LANGUAGES as readonly string[]).includes(language)) throw new Refusal("Unknown language.");
    await setSetting("slip_language", language);
    return ok(`Slips and printouts will be in ${language}.`);
  });
}

export async function savePrinting(input: { congregation: string; useAux: boolean; gaConvert: boolean }) {
  return attemptFull(async () => {
    await prisma.$transaction(async (tx) => {
      await setSetting("congregation", nfc(input.congregation), tx);
      await setSetting("use_aux", input.useAux ? "1" : "0", tx);
      await setSetting("ga_convert", input.gaConvert ? "1" : "0", tx);
    });
    return ok("Saved.");
  });
}

export async function saveMeetingDays(midweek: string, weekend: string) {
  return attemptFull(async (user) => {
    if (!WEEKDAYS.includes(midweek) || !WEEKDAYS.includes(weekend)) throw new Refusal("Pick a day.");
    await prisma.$transaction(async (tx) => {
      await setSetting("midweek_day", midweek, tx);
      await setSetting("weekend_day", weekend, tx);
    });
    await logChange(user, "Meeting days changed", `midweek ${midweek}, weekend ${weekend}`);
    return ok("Saved.");
  });
}

export async function saveRotation(days: number) {
  return attemptFull(async (user) => {
    const n = Math.round(Number(days));
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
  return attemptFull(async (user) => {
    await prisma.no_meeting_periods.deleteMany({ where: { id: needId(id) } });
    await logChange(user, "Assembly/convention week removed", `id ${id}`);
    return ok("Removed.");
  });
}

export async function removeTemplate(name: string) {
  return attemptFull(async (user) => {
    if (!/^(s89|s140)_(English|Ga)$/.test(name)) throw new Refusal("Unknown form.");
    await prisma.templates.deleteMany({ where: { name } });
    await logChange(user, "Blank form removed", name);
    return ok("Removed.");
  });
}

/** The meeting times the calendar feeds use, e.g. "18:30" or "6:30pm". Empty makes them all-day entries. */
export async function saveCalendarTimes(midweek: string, weekend: string) {
  return attemptFull(async (user) => {
    const m = nfc(midweek).slice(0, 20), w = nfc(weekend).slice(0, 20);
    for (const [label, t] of [["midweek", m], ["weekend", w]] as const) {
      if (t && !parseTime(t)) throw new Refusal(`Write the ${label} time like 18:30 or 6:30pm.`);
    }
    await prisma.$transaction(async (tx) => {
      await setSetting("midweek_time", m, tx);
      await setSetting("weekend_time", w, tx);
    });
    await logChange(user, "Calendar times changed", `midweek ${m || "—"}, weekend ${w || "—"}`);
    return ok("Saved. Calendars pick up the new times the next time they refresh.");
  });
}
