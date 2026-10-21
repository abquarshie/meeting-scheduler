"use server";
import { attempt, logChange, ok, Refusal } from "@/lib/action";
import { isISODate } from "@/lib/dates";
import { prisma } from "@/lib/db";
import { nfc, talkLabel } from "@/lib/text";

// The talk list and outgoing speakers, as db.save_talk, import_talks, set_outgoing_speaker and friends.

function cleanPairs(rows: { number: string; title: string }[]) {
  const seen = new Set<string>();
  const out: { number: string; title: string }[] = [];
  for (const r of rows) {
    const number = nfc(r.number);
    if (!number || seen.has(number)) continue;
    seen.add(number);
    out.push({ number, title: nfc(r.title) });
  }
  return out;
}

/** The whole talk list as edited in the table: rows kept are saved, rows gone are removed. */
export async function saveTalks(rows: { number: string; title: string }[]) {
  return attempt(async (user) => {
    const kept = cleanPairs(rows);
    await prisma.$transaction(async (tx) => {
      const before = await tx.talks.findMany();
      const keep = new Set(kept.map((r) => r.number));
      const gone = before.filter((t) => !keep.has(t.number)).map((t) => t.number);
      if (gone.length) await tx.talks.deleteMany({ where: { number: { in: gone } } });
      const old = new Map(before.map((t) => [t.number, t.title ?? ""]));
      for (const r of kept) {
        if (old.get(r.number) === r.title) continue;
        await tx.talks.upsert({ where: { number: r.number }, create: r, update: { title: r.title } });
        await logChange(user, "Public talk saved", talkLabel(r.number, r.title), tx);
      }
      for (const n of gone) await logChange(user, "Public talk removed", `No. ${n}`, tx);
    });
    return ok(`Saved ${kept.length} talk(s).`);
  });
}

export async function importTalks(rows: { number: string; title: string }[], replace: boolean) {
  return attempt(async (user) => {
    const clean = cleanPairs(rows);
    if (!clean.length) throw new Refusal("No rows with a number were found in that file.");
    let added = 0;
    await prisma.$transaction(async (tx) => {
      const before = new Set((await tx.talks.findMany({ select: { number: true } })).map((t) => t.number));
      if (replace) await tx.talks.deleteMany({});
      for (const r of clean) {
        if (!before.has(r.number)) added++;
        await tx.talks.upsert({ where: { number: r.number }, create: r, update: { title: r.title } });
      }
      await logChange(user, "Public talks imported", `${clean.length} talk(s), ${added} new`, tx);
    });
    return ok(`Imported ${clean.length} talk(s), ${added} new.`);
  });
}

export async function setOutgoingSpeaker(studentId: number, numbers: string[]) {
  return attempt(async (user) => {
    const talks = [...new Set(numbers.map(nfc).filter(Boolean))].join(", ");
    await prisma.outgoing_speakers.upsert({
      where: { student_id: studentId },
      create: { student_id: studentId, talk_numbers: talks, active: 1 },
      update: { talk_numbers: talks, active: 1 },
    });
    await logChange(user, "Outgoing speaker approved", `id ${studentId}: ${talks}`);
    return ok("Saved.");
  });
}

export async function removeOutgoingSpeaker(studentId: number) {
  return attempt(async (user) => {
    await prisma.outgoing_speakers.updateMany({ where: { student_id: studentId }, data: { active: 0 } });
    await logChange(user, "Outgoing speaker removed", `id ${studentId}`);
    return ok("Removed.");
  });
}

export async function addEngagement(studentId: number, date: string, congregation: string, talkNumber: string) {
  return attempt(async (user) => {
    if (!isISODate(date)) throw new Refusal("Pick a date.");
    const data = { congregation: nfc(congregation), talk_number: nfc(talkNumber) };
    await prisma.outgoing_engagements.upsert({
      where: { student_id_meeting_date: { student_id: studentId, meeting_date: date } },
      create: { student_id: studentId, meeting_date: date, ...data }, update: data,
    });
    await logChange(user, "Outgoing engagement added", `id ${studentId}: ${date}`);
    return ok("Added.");
  });
}

export async function removeEngagement(id: number) {
  return attempt(async (user) => {
    await prisma.outgoing_engagements.deleteMany({ where: { id } });
    await logChange(user, "Outgoing engagement removed", `id ${id}`);
    return ok("Removed.");
  });
}
