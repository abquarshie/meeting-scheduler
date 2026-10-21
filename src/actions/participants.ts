"use server";
import { attempt, gaOn, logChange, needId, ok, Refusal, strings } from "@/lib/action";
import { requireUser } from "@/lib/auth";
import { CATEGORIES, GROUPS, PRIVILEGES } from "@/lib/constants";
import { addDays, isISODate, today } from "@/lib/dates";
import { prisma } from "@/lib/db";
import { gaSubstitutes, nfc } from "@/lib/text";

// The same writes as db.add_student, update_student, set_suspension, set_unavailable and delete_student.

export type PersonInput = { name: string; gender: string; privileges: string[]; groups: string[]; family: string | null; active?: boolean };

async function clean(input: PersonInput) {
  const ga = await gaOn();
  const name = gaSubstitutes(nfc(input.name), ga);
  if (!name) throw new Refusal("Enter a name.");
  if (!(CATEGORIES as readonly string[]).includes(input.gender)) throw new Refusal("Choose a category.");
  const privileges = PRIVILEGES.filter((p) => strings(input.privileges).includes(p));
  const groups = GROUPS.filter((g) => strings(input.groups).includes(g));
  const family = input.family ? gaSubstitutes(nfc(input.family), ga) || null : null;
  return { name, gender: input.gender, privileges: privileges.join(", "), groups: groups.join(", "), family };
}

export async function addPerson(input: PersonInput) {
  return attempt(async (user) => {
    const p = await clean(input);
    const same = await prisma.students.count({ where: { name: { equals: p.name, mode: "insensitive" } } });
    await prisma.students.create({ data: { ...p, active: 1 } });
    await logChange(user, "Participant added", p.name);
    return ok(same ? `There was already someone called ${p.name}; added anyway.` : `Added ${p.name}.`);
  });
}

export async function updatePerson(id: number, input: PersonInput) {
  return attempt(async (user) => {
    needId(id);
    const p = await clean(input);
    await prisma.$transaction(async (tx) => {
      await tx.students.update({ where: { id }, data: { ...p, active: input.active ? 1 : 0 } });
      // keep the name snapshot on old schedules in step with the rename
      await tx.schedules.updateMany({ where: { student_id: id }, data: { assigned_person: p.name } });
      await tx.schedules.updateMany({ where: { assistant_id: id }, data: { assistant_name: p.name } });
      await logChange(user, "Participant edited", `${p.name} (active=${input.active ? "True" : "False"})`, tx);
    });
    return ok("Saved. Existing schedules show the updated name.");
  });
}

export async function setSuspension(id: number, suspended: boolean, until: string | null) {
  return attempt(async (user) => {
    needId(id);
    if (suspended && until && !isISODate(until)) throw new Refusal("Pick a valid end date.");
    await prisma.students.update({ where: { id }, data: { suspended: suspended ? 1 : 0, suspended_until: suspended ? until : null } });
    await logChange(user, `Suspension ${suspended ? "set" : "lifted"}`, `id ${id}${until && suspended ? ` until ${until}` : ""}`);
    return ok(suspended ? "Suspension saved." : "Suspension lifted.");
  });
}

/** Meetings this person is already on from today (to the end date, if any): to reassign when suspending. */
export async function upcomingFor(id: number, until: string | null) {
  await requireUser();
  if (!Number.isSafeInteger(id) || (until !== null && !isISODate(until))) return [];
  try {
    const rows = await prisma.schedules.findMany({
      where: { OR: [{ student_id: id }, { assistant_id: id }], meeting_date: { gte: today(), ...(until ? { lte: until } : {}) } },
      orderBy: { meeting_date: "asc" }, select: { meeting_date: true, meeting_type: true, part_name: true },
    });
    return rows.map((r) => ({ date: r.meeting_date ?? "", type: r.meeting_type ?? "", part: r.part_name ?? "" }));
  } catch (e) {
    console.error(e); // only a hint on the page, so a failed read just shows none
    return [];
  }
}

export async function addAway(id: number, start: string, end: string) {
  return attempt(async (user) => {
    needId(id);
    if (!isISODate(start) || !isISODate(end || start)) throw new Refusal("Pick the first and last day.");
    const last = end && end >= start ? end : start;
    const days: string[] = [];
    for (let d = start; d <= last; d = addDays(d, 1)) days.push(d);
    if (days.length > 400) throw new Refusal("That period is over a year long.");
    await prisma.$transaction(async (tx) => {
      await tx.unavailable.createMany({ data: days.map((d) => ({ student_id: id, meeting_date: d })), skipDuplicates: true });
      const total = await tx.unavailable.count({ where: { student_id: id } });
      await logChange(user, "Away dates changed", `id ${id}: ${total} day(s)`, tx);
    });
    return ok("Away period added.");
  });
}

export async function clearAway(id: number) {
  return attempt(async (user) => {
    await prisma.unavailable.deleteMany({ where: { student_id: needId(id) } });
    await logChange(user, "Away dates changed", `id ${id}: 0 day(s)`);
    return ok("Away dates cleared.");
  });
}

export async function deletePerson(id: number) {
  return attempt(async (user) => {
    needId(id);
    const used = await prisma.schedules.count({ where: { OR: [{ student_id: id }, { assistant_id: id }] } });
    if (used) throw new Refusal("This person has saved assignments. Untick Active instead so the history stays intact.");
    const p = await prisma.students.delete({ where: { id } });
    await logChange(user, "Participant deleted", `id ${id}`);
    return ok(`${p.name} deleted.`);
  });
}
