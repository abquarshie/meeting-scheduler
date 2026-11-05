// Who has a part in the coming days, as one reminder per person, and the same parts as a calendar (.ics) feed.
// Pure functions, so they can be checked on their own.
import { HALL_NAMES, MAIN_HALL, MIDWEEK } from "./constants";
import { longDate } from "./dates";

export type PartRow = {
  id: number; meeting_date: string; meeting_type: string; part_name: string | null; part_no: number | null;
  student_id: number | null; assistant_id: number | null; person: string | null; assistant: string | null;
  hall: string; visitor: string | null; role?: string | null; talk_title?: string | null;
};

export type Duty = { rowId: number; date: string; type: string; part: string; hall: string; with: string | null; assisting: boolean };
export type Reminder = { id: number; name: string; duties: Duty[] };

const meetingWord = (type: string) => (type === MIDWEEK ? "midweek meeting" : "weekend meeting");
// Parts that carry a theme, and the name to show before it: "Public Talk - Why Fear the True God".
const THEMED: Record<string, string> = {
  "Public Talk": "Public Talk", "Treasures Talk": "Treasures Talk", "Living Part": "Living as Christians",
  "Student Talk": "Talk",
};
const PUBLIC_TALK = "Public Talk";
const bare = (s: string) => s.trim().replace(/^[“"‘']+|[”"’']+$/g, "").trim();

/** The part's name, with its theme when it has one. Midweek themes are the workbook titles; the public talk's is
 *  the talk title saved on the weekend meeting. */
export function partName(r: Pick<PartRow, "part_name" | "role" | "talk_title">): string {
  const title = (r.part_name ?? "").trim();
  const label = r.role ? THEMED[r.role] : undefined;
  if (r.role === PUBLIC_TALK) {
    const theme = bare(r.talk_title ?? "");
    return theme ? `${PUBLIC_TALK} - ${theme}` : PUBLIC_TALK;
  }
  if (label && title && !title.toLowerCase().includes(label.toLowerCase())) return `${label} - ${bare(title)}`;
  return title || "a part";
}
const firstName = (name: string) => name.trim().split(/\s+/)[0] ?? name;

/** Everyone with a part or assisting in the rows given, earliest first. Visiting speakers are left out. */
export function remindersFrom(rows: PartRow[]): Reminder[] {
  const by = new Map<number, Reminder>();
  const add = (id: number | null, name: string | null, d: Duty) => {
    if (!id || !name) return;
    const r = by.get(id) ?? { id, name, duties: [] };
    r.duties.push(d);
    by.set(id, r);
  };
  for (const r of rows) {
    if (r.visitor) continue;
    const base = { rowId: r.id, date: r.meeting_date, type: r.meeting_type, part: partName(r), hall: r.hall || MAIN_HALL };
    add(r.student_id, r.person, { ...base, with: r.assistant, assisting: false });
    add(r.assistant_id, r.assistant, { ...base, with: r.person, assisting: true });
  }
  for (const r of by.values()) r.duties.sort((a, b) => a.date.localeCompare(b.date) || a.rowId - b.rowId);
  return [...by.values()].sort((a, b) => a.duties[0].date.localeCompare(b.duties[0].date) || a.name.localeCompare(b.name));
}

function dutyLine(d: Duty): string {
  const hall = d.hall !== MAIN_HALL ? ` (${HALL_NAMES[d.hall] ?? d.hall})` : "";
  if (d.assisting) return `you are assisting ${d.with ?? "a student"} with "${d.part}"${hall}`;
  return `you have "${d.part}"${hall}${d.with ? `, with ${d.with} assisting` : ""}`;
}

/** The WhatsApp message for one person. */
export function reminderText(r: Reminder, congregation: string): string {
  const byMeeting = new Map<string, Duty[]>();
  for (const d of r.duties) byMeeting.set(`${d.date}|${d.type}`, [...(byMeeting.get(`${d.date}|${d.type}`) ?? []), d]);
  const lines = [...byMeeting.values()].map((ds) =>
    `• ${longDate(ds[0].date)}, ${meetingWord(ds[0].type)}: ${ds.map(dutyLine).join("; ")}.`);
  return [`Hello ${firstName(r.name)} 👋`, "", `A reminder of your assignment${r.duties.length > 1 ? "s" : ""}${congregation ? ` at ${congregation}` : ""}:`,
    ...lines, "", "Thank you, and please let us know quickly if you can't make it."].join("\n");
}

const KINGDOM_HALL = "Kingdom Hall";

// ---- calendar -------------------------------------------------------------------------------------------------------

/** "18:30", "6:30pm", "6.30 pm", "7pm" -> [18, 30]; null when it can't be read. */
export function parseTime(text: string | null | undefined): [number, number] | null {
  const m = String(text ?? "").trim().toLowerCase().match(/^(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm)?$/);
  if (!m) return null;
  let h = Number(m[1]);
  const min = Number(m[2] ?? 0);
  if (m[3] === "pm" && h < 12) h += 12;
  if (m[3] === "am" && h === 12) h = 0;
  return h < 24 && min < 60 ? [h, min] : null;
}

const esc = (s: string) => s.replace(/\\/g, "\\\\").replace(/;/g, "\\;").replace(/,/g, "\\,").replace(/\r?\n/g, "\\n");
const two = (n: number) => String(n).padStart(2, "0");
/** Long lines folded at 75 octets (RFC 5545), counting bytes so Ga letters aren't split badly. */
function fold(line: string): string {
  const out: string[] = [];
  let cur = "", bytes = 0;
  for (const ch of line) {
    const b = Buffer.byteLength(ch);
    if (bytes + b > (out.length ? 74 : 75)) { out.push(cur); cur = ""; bytes = 0; }
    cur += ch; bytes += b;
  }
  out.push(cur);
  return out.join("\r\n ");
}

/** One person's parts as an iCalendar feed. Times are local Ghana time (UTC, all year), so they're written in UTC. */
export function calendar(r: Reminder | null, name: string, opts: { midweek: string; weekend: string; congregation: string }): string {
  const stamp = new Date().toISOString().replace(/[-:]/g, "").slice(0, 15) + "Z";
  const lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Meeting Scheduler//EN", "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
    `X-WR-CALNAME:${esc(`Meeting assignments: ${name}`)}`, "X-WR-TIMEZONE:Africa/Accra", "REFRESH-INTERVAL;VALUE=DURATION:PT12H"];
  for (const d of r?.duties ?? []) {
    const day = d.date.replace(/-/g, "");
    const t = parseTime(d.type === MIDWEEK ? opts.midweek : opts.weekend);
    lines.push("BEGIN:VEVENT", `UID:ms-${d.rowId}-${d.assisting ? "a" : "p"}@meeting-scheduler`, `DTSTAMP:${stamp}`);
    if (t) {
      const end = t[0] * 60 + t[1] + 105; // a meeting is about 1 h 45
      lines.push(`DTSTART:${day}T${two(t[0])}${two(t[1])}00Z`, `DTEND:${day}T${two(Math.floor(end / 60) % 24)}${two(end % 60)}00Z`);
    } else {
      lines.push(`DTSTART;VALUE=DATE:${day}`);
    }
    const summary = d.assisting ? `Assisting ${d.with ?? ""}: ${d.part}` : d.part;
    lines.push(`SUMMARY:${esc(summary.trim())}`,
      `DESCRIPTION:${esc(`${meetingWord(d.type)[0].toUpperCase()}${meetingWord(d.type).slice(1)}${opts.congregation ? `, ${opts.congregation}` : ""}: ${dutyLine(d)}.`)}`);
    lines.push(`LOCATION:${esc(KINGDOM_HALL)}`);
    // a nudge the evening before
    lines.push("BEGIN:VALARM", "ACTION:DISPLAY", `DESCRIPTION:${esc(summary.trim())}`, "TRIGGER:-PT18H", "END:VALARM", "END:VEVENT");
  }
  lines.push("END:VCALENDAR");
  return lines.map(fold).join("\r\n") + "\r\n";
}
