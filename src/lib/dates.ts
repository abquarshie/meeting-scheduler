// Dates are stored as ISO text (YYYY-MM-DD), as the Python app writes them. These helpers work on that text in UTC,
// so a server's time zone never shifts a day.

const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
  "November", "December"];
const DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

export function isISODate(s: unknown): s is string {
  if (typeof s !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(s)) return false;
  return toISO(parse(s)) === s;
}

export function parse(iso: string): Date {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d));
}

export function toISO(d: Date): string {
  return d.toISOString().slice(0, 10);
}

export function today(): string {
  return toISO(new Date());
}

export function addDays(iso: string, n: number): string {
  const d = parse(iso);
  d.setUTCDate(d.getUTCDate() + n);
  return toISO(d);
}

export function daysBetween(a: string, b: string): number {
  return Math.round((parse(b).getTime() - parse(a).getTime()) / 86_400_000);
}

/** 0 = Monday … 6 = Sunday, as Python's weekday(). */
export function weekday(iso: string): number {
  return (parse(iso).getUTCDay() + 6) % 7;
}

/** The Monday of the meeting week this day falls in. */
export function weekStart(iso: string): string {
  return addDays(iso, -weekday(iso));
}

const short = (d: Date) => MONTHS[d.getUTCMonth()].slice(0, 3);

/** "21 October 2026", or "21 Oct" when short. */
export function fmtDate(iso: string | null | undefined, isShort = false): string {
  if (!iso || !isISODate(iso)) return iso ?? "";
  const d = parse(iso);
  return isShort ? `${d.getUTCDate()} ${short(d)}` : `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}`;
}

/** "Wednesday 21 October". */
export function longDate(iso: string): string {
  const d = parse(iso);
  return `${DAYS[d.getUTCDay()]} ${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}`;
}

/** "Wed 21 Oct". */
export function shortDay(iso: string): string {
  const d = parse(iso);
  return `${DAYS[d.getUTCDay()].slice(0, 3)} ${d.getUTCDate()} ${short(d)}`;
}

/** "2026-10" -> "October 2026". */
export function monthLabel(ym: string): string {
  const [y, m] = ym.split("-").map(Number);
  return `${MONTHS[m - 1]} ${y}`;
}

export function lastDayOfMonth(ym: string): string {
  const [y, m] = ym.split("-").map(Number);
  return toISO(new Date(Date.UTC(y, m, 0)));
}

/** "Week 2 of October (5–11 Oct)", as utils.week_label. */
export function weekLabel(iso: string): string {
  const mon = weekStart(iso);
  const sun = addDays(mon, 6);
  const m = parse(mon), s = parse(sun);
  const n = Math.floor((m.getUTCDate() - 1) / 7) + 1;
  const span = m.getUTCMonth() === s.getUTCMonth()
    ? `${m.getUTCDate()}–${s.getUTCDate()} ${short(s)}`
    : `${m.getUTCDate()} ${short(m)} – ${s.getUTCDate()} ${short(s)}`;
  return `Week ${n} of ${MONTHS[m.getUTCMonth()]} (${span})`;
}

/** "this week", "last week", "next week", "3 weeks ago", "in 2 weeks". */
export function relativeWeek(other: string, meeting: string): string {
  const n = Math.round(daysBetween(weekStart(meeting), weekStart(other)) / 7);
  if (n === 0) return "this week";
  if (n === -1) return "last week";
  if (n === 1) return "next week";
  return n < 0 ? `${-n} weeks ago` : `in ${n} weeks`;
}

/** "in 3 days", "today", "tomorrow". */
export function daysAway(iso: string): string {
  const n = daysBetween(today(), iso);
  return n === 0 ? "today" : n === 1 ? "tomorrow" : `in ${n} days`;
}

/** "14–20 Sep 2026" for a workbook week's dates, as workbook.week_dates_text. */
export function weekDatesText(start?: string, end?: string): string {
  if (!start || !end) return "no dates";
  const s = parse(start), e = parse(end);
  return s.getUTCMonth() === e.getUTCMonth()
    ? `${s.getUTCDate()}–${e.getUTCDate()} ${short(e)} ${e.getUTCFullYear()}`
    : `${s.getUTCDate()} ${short(s)}–${e.getUTCDate()} ${short(e)} ${e.getUTCFullYear()}`;
}

/** Collapse consecutive days into ranges: "3–9 Oct, 20 Oct". */
export function awaySummary(dates: string[]): string {
  const days = [...dates].sort();
  const out: string[] = [];
  let start: string | null = null, prev: string | null = null;
  for (const d of [...days, null]) {
    if (start === null) { start = prev = d; continue; }
    if (d !== null && prev !== null && daysBetween(prev, d) === 1) { prev = d; continue; }
    out.push(start === prev ? fmtDate(start, true) : `${fmtDate(start, true)}–${fmtDate(prev, true)}`);
    start = prev = d;
  }
  return out.join(", ");
}
