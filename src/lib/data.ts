import "server-only";
import { EVENT_KINDS, EVENT_TEXT, GROUPS, MIDWEEK, PRIVILEGES, SAME_ROLE_GAP_DAYS, WEEKDAYS } from "./constants";
import { addDays, fmtDate, today, weekStart } from "./dates";
import { prisma } from "./db";
import { nfc } from "./text";

// Reading the Python app's tables, in the shapes the pages want. Mirrors the read helpers in db.py and workbook.py.

export type Person = {
  id: number; name: string; gender: string; privileges: string[]; groups: string[]; family: string | null;
  active: boolean; suspended: boolean; suspendedUntil: string | null;
};

export function parsePrivileges(value: string | null): string[] {
  const out: string[] = [];
  for (const item of (value ?? "").split(",")) {
    const p = item.trim();
    if ((PRIVILEGES as readonly string[]).includes(p) && !out.includes(p)) out.push(p);
  }
  return out;
}

export async function getPeople(): Promise<Person[]> {
  const rows = await prisma.students.findMany();
  return rows
    .map((r) => ({
      id: r.id, name: r.name, gender: r.gender ?? "", privileges: parsePrivileges(r.privileges),
      groups: (r.groups ?? "").split(",").map((g) => g.trim()).filter((g) => (GROUPS as readonly string[]).includes(g)),
      family: nfc(r.family) || null, active: r.active === 1, suspended: Boolean(r.suspended),
      suspendedUntil: r.suspended_until || null,
    }))
    .sort((a, b) => a.name.toLowerCase().localeCompare(b.name.toLowerCase()));
}

/** Suspended with no end date, or the end date hasn't passed yet (db.is_suspended). */
export function isSuspended(p: Person, onDate: string): boolean {
  if (!p.suspended) return false;
  return !p.suspendedUntil || onDate <= p.suspendedUntil;
}

export function suspensionText(p: Person, on = today()): string {
  if (!isSuspended(p, on)) return "";
  return p.suspendedUntil ? `Suspended until ${fmtDate(p.suspendedUntil)}` : "Suspended";
}

export function familyNames(people: Person[]): string[] {
  return [...new Set(people.map((p) => p.family).filter((f): f is string => Boolean(f)))]
    .sort((a, b) => a.toLowerCase().localeCompare(b.toLowerCase()));
}

export type Row = {
  id: number; meeting_date: string; meeting_type: string; part_no: number | null; part_name: string | null;
  minutes: number | null; section: string | null; role: string | null; student_part: number; needs_assistant: number;
  student_id: number | null; assistant_id: number | null; sort_order: number; hall: string; visitor: string | null;
  visitor_congregation: string | null; person: string | null; assistant: string | null;
};

/** Every saved part with the names joined in, newest meeting first (db._schedules). */
export async function getRows(): Promise<Row[]> {
  const rows = await prisma.$queryRaw<Row[]>`
    SELECT sc.id, sc.meeting_date, sc.meeting_type, sc.part_no, sc.part_name, sc.minutes, sc.section, sc.role,
           COALESCE(sc.student_part, 0) AS student_part, COALESCE(sc.needs_assistant, 0) AS needs_assistant,
           sc.student_id, sc.assistant_id, COALESCE(sc.sort_order, 0) AS sort_order,
           COALESCE(sc.hall, 'main_hall') AS hall, sc.visitor, sc.visitor_congregation,
           COALESCE(sc.visitor, s.name, sc.assigned_person) AS person,
           COALESCE(a.name, sc.assistant_name) AS assistant
      FROM schedules sc
      LEFT JOIN students s ON s.id = sc.student_id
      LEFT JOIN students a ON a.id = sc.assistant_id
     ORDER BY sc.meeting_date DESC, sc.meeting_type, sc.sort_order, sc.id`;
  return rows.map((r) => ({ ...r, person: r.person || null, assistant: r.assistant || null }));
}

export type MeetingKey = `${string}|${string}`;
export const key = (date: string, type: string) => `${date}|${type}` as MeetingKey;

/** [(date, type)] newest first, one per saved meeting. */
export function savedMeetings(rows: Row[]): { date: string; type: string }[] {
  const seen = new Set<string>();
  const out: { date: string; type: string }[] = [];
  for (const r of rows) {
    const k = key(r.meeting_date, r.meeting_type);
    if (!seen.has(k)) { seen.add(k); out.push({ date: r.meeting_date, type: r.meeting_type }); }
  }
  return out;
}

export function meetingRows(rows: Row[], date: string, type: string): Row[] {
  return rows.filter((r) => r.meeting_date === date && r.meeting_type === type);
}

/** (filled, needed): a part plus, where the part calls for one, its assistant (db.fill_counts). */
export function fillCounts(rows: Row[]): { filled: number; needed: number } {
  let filled = 0, needed = 0;
  for (const r of rows) {
    needed += 1 + (r.needs_assistant === 1 ? 1 : 0);
    filled += (r.person ? 1 : 0) + (r.needs_assistant === 1 && r.assistant ? 1 : 0);
  }
  return { filled, needed };
}

export type Meta = {
  heading: string; opening_song: string; middle_song: string; closing_song: string; aux: number | null;
  talk_number: string; talk_title: string; book: string; aux_group: string;
};

export async function getMetas(): Promise<Map<MeetingKey, Meta>> {
  const rows = await prisma.meetings.findMany();
  return new Map(rows.map((m) => [key(m.meeting_date, m.meeting_type), {
    heading: m.heading ?? "", opening_song: m.opening_song ?? "", middle_song: m.middle_song ?? "",
    closing_song: m.closing_song ?? "", aux: m.aux, talk_number: m.talk_number ?? "", talk_title: m.talk_title ?? "",
    book: m.book ?? "", aux_group: m.aux_group ?? "",
  }]));
}

export async function getSettings(): Promise<Map<string, string>> {
  const rows = await prisma.settings.findMany();
  return new Map(rows.map((r) => [r.key, r.value ?? ""]));
}

export function setting(settings: Map<string, string>, k: string, fallback = ""): string {
  const v = settings.get(k);
  return v === undefined ? fallback : v;
}

export function gapDays(settings: Map<string, string>): number {
  const n = Number.parseInt(setting(settings, "same_role_gap_days", String(SAME_ROLE_GAP_DAYS)), 10);
  return Number.isFinite(n) ? n : SAME_ROLE_GAP_DAYS;
}

export type WorkbookPart = { part_no: number | null; title: string; minutes: number | null; section: string; role: string };
export type WorkbookWeek = {
  label: string; start?: string; end?: string; book?: string; songs?: string[]; parts: WorkbookPart[]; gaps?: number[];
  text?: string;
};

export async function getWorkbook(): Promise<{ weeks: WorkbookWeek[]; file: string }> {
  const [rows, file] = await Promise.all([
    prisma.workbook_weeks.findMany({ orderBy: { position: "asc" } }),
    prisma.settings.findUnique({ where: { key: "workbook_file" } }),
  ]);
  const weeks = rows.map((r) => {
    let data: Partial<WorkbookWeek> = {};
    try { data = JSON.parse(r.data ?? "{}"); } catch { /* a damaged row reads as empty */ }
    return { ...data, parts: data.parts ?? [], label: r.label };
  });
  return { weeks, file: file?.value ?? "" };
}

export type EventPeriod = { id: number; start: string; end: string; kind: "assembly" | "convention" };

export async function getEvents(): Promise<EventPeriod[]> {
  const rows = await prisma.no_meeting_periods.findMany({ orderBy: { start_date: "asc" } });
  return rows.map((r) => ({
    id: r.id, start: r.start_date, end: r.end_date,
    kind: (EVENT_KINDS as readonly string[]).includes(r.kind ?? "") ? (r.kind as "assembly" | "convention") : "assembly",
  }));
}

export function eventFor(events: EventPeriod[], date: string): EventPeriod["kind"] | null {
  return events.find((e) => e.start <= date && date <= e.end)?.kind ?? null;
}

export function eventLabel(events: EventPeriod[], date: string): string | null {
  const kind = eventFor(events, date);
  return kind ? EVENT_TEXT[kind].en : null;
}

/** {Monday: kind} for every marked week (db.event_weeks). */
export function eventWeeks(events: EventPeriod[]): Map<string, string> {
  const out = new Map<string, string>();
  for (const e of events) {
    for (let d = weekStart(e.start); d <= e.end; d = addDays(d, 7)) if (!out.has(d)) out.set(d, e.kind);
  }
  return out;
}

function meetingDayOffset(settings: Map<string, string>, type: string): number {
  const name = setting(settings, type === MIDWEEK ? "midweek_day" : "weekend_day", type === MIDWEEK ? "Wednesday" : "Sunday");
  const i = WEEKDAYS.indexOf(name);
  return i >= 0 ? i : type === MIDWEEK ? 2 : 6;
}

export type WorkbookStatus = { label: string; meeting: string; status: "saved" | "no meeting" | "to create" };

/** Every dated workbook week with its midweek meeting date and whether it is saved, an assembly or convention week,
 * or still to create (workbook.midweek_workbook_weeks). */
export function workbookStatus(weeks: WorkbookWeek[], rows: Row[], settings: Map<string, string>,
  events: EventPeriod[]): WorkbookStatus[] {
  const saved = savedMeetings(rows).filter((m) => m.type === MIDWEEK).map((m) => m.date);
  const offset = meetingDayOffset(settings, MIDWEEK);
  return weeks.filter((w) => w.start).map((w) => {
    const meeting = addDays(w.start!, offset);
    const status = saved.some((d) => w.start! <= d && d <= (w.end ?? w.start!)) ? "saved"
      : eventFor(events, meeting) ? "no meeting" : "to create";
    return { label: w.label, meeting, status };
  });
}

/** Everyone away on any date in the range. */
export async function awayBetween(start: string, end: string): Promise<Set<number>> {
  const rows = await prisma.unavailable.findMany({ where: { meeting_date: { gte: start, lte: end } } });
  return new Set(rows.map((r) => r.student_id));
}

export async function templateNames(): Promise<Map<string, string>> {
  const rows = await prisma.templates.findMany({ select: { name: true, file_name: true } });
  return new Map(rows.map((r) => [r.name, r.file_name ?? ""]));
}

/** person -> latest assignment date up to today or overall, for the participants list. */
export function lastAssignment(rows: Row[]): Map<number, string> {
  const out = new Map<number, string>();
  for (const r of rows) {
    for (const id of [r.student_id, r.assistant_id]) {
      if (id !== null && (out.get(id) ?? "") < r.meeting_date) out.set(id, r.meeting_date);
    }
  }
  return out;
}
