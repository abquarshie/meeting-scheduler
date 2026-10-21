import type { Metadata } from "next";
import { Note, PageHead } from "@/components/ui";
import { LANGUAGES, MIDWEEK, WEEKEND } from "@/lib/constants";
import { eventWeeks, getEvents, getMetas, getPeople, getRows, getSettings, key, meetingRows, savedMeetings, setting, templateNames } from "@/lib/data";
import { fmtDate, monthLabel, relativeWeek, today, weekLabel, weekStart } from "@/lib/dates";
import { talkText } from "@/lib/text";
import { Printing } from "./Printing";

export const metadata: Metadata = { title: "Slips and printing" };

const partLabel = (r: { part_name: string | null; part_no: number | null; minutes: number | null; hall: string }) => {
  if (r.part_name === "Public Talk Speaker") return "Public Talk & Closing Prayer";
  let label = r.part_name ?? "";
  if (r.minutes && !label.toLowerCase().includes("min")) label += ` (${r.minutes} min)`;
  if (r.part_no) label = `${r.part_no}. ${label}`;
  if (r.hall !== "main_hall") label += r.hall === "aux_1" ? " · Auxiliary classroom 1" : " · Auxiliary classroom 2";
  return label;
};

export default async function PrintPage({ searchParams }: { searchParams: Promise<{ meeting?: string; month?: string }> }) {
  const [sp, rows, metas, people, settings, templates, events] = await Promise.all([
    searchParams, getRows(), getMetas(), getPeople(), getSettings(), templateNames(), getEvents(),
  ]);
  const meetings = savedMeetings(rows);
  if (!meetings.length) {
    return <><PageHead title="Slips and printing" /><Note>No schedules have been created yet.</Note></>;
  }
  const language = (LANGUAGES as readonly string[]).includes(setting(settings, "slip_language")) ? setting(settings, "slip_language") : "English";
  const months = [...new Set(meetings.map((m) => m.date.slice(0, 7)))].sort().reverse();
  const scope = sp.month ? "month" : "meeting";
  const now = today();
  const firstAhead = [...meetings].filter((m) => m.date >= now).sort((a, b) => a.date.localeCompare(b.date))[0] ?? meetings[0];
  const meeting = meetings.find((m) => key(m.date, m.type) === sp.meeting) ?? firstAhead;
  const month = scope === "month" && months.includes(sp.month!) ? sp.month! : meeting.date.slice(0, 7);
  const chosen = (scope === "month" ? meetings.filter((m) => m.date.startsWith(month)) : [meeting])
    .sort((a, b) => a.date.localeCompare(b.date) || a.type.localeCompare(b.type));

  const meta = metas.get(key(meeting.date, meeting.type));
  const summary = scope === "meeting" ? {
    heading: meta?.heading ?? "", talk: meeting.type === WEEKEND ? talkText(meta) || "— title not entered —" : "",
    rows: meetingRows(rows, meeting.date, meeting.type).sort((a, b) => a.sort_order - b.sort_order).map((r) => ({
      part: partLabel(r), person: r.person ?? "— unassigned —", assistant: r.needs_assistant === 1 ? r.assistant ?? "— needed —" : "",
    })),
  } : null;
  const chosenRows = rows.filter((r) => chosen.some((m) => m.date === r.meeting_date && m.type === r.meeting_type));
  const slipCount = chosenRows.filter((r) => r.student_part === 1 && r.person).length;
  const slipAux = chosenRows.filter((r) => r.student_part === 1 && r.person && r.hall !== "main_hall").length;

  // weeks for the weekly card: every week with a meeting, and assembly/convention weeks
  const weeks = [...new Set([...meetings.map((m) => weekStart(m.date)), ...eventWeeks(events).keys()])].sort();
  const thisWeek = weekStart(now);
  const weekOptions = weeks.map((w) => {
    const rel = relativeWeek(w, thisWeek);
    return { value: w, label: weekLabel(w) + (["this week", "last week", "next week"].includes(rel) ? ` · ${rel}` : "") };
  });
  const allMonths = months.map((m) => ({ value: m, label: monthLabel(m) }));
  // who has something in each month, for the one-person card
  const monthPeople: Record<string, { id: number; label: string }[]> = {};
  for (const m of months) {
    const counts = new Map<number, number>();
    for (const r of rows) if (r.meeting_date.startsWith(m)) for (const id of [r.student_id, r.assistant_id]) if (id !== null) counts.set(id, (counts.get(id) ?? 0) + 1);
    monthPeople[m] = people.filter((p) => counts.has(p.id)).map((p) => ({ id: p.id, label: `${p.name} (${counts.get(p.id)})` }));
  }

  return (
    <>
      <PageHead title="Slips and printing" sub="Slips, schedule sheets, the S-140, the CSV and monthly messages, for one meeting or a whole month." />
      <Printing
        scope={scope} language={language}
        meetings={meetings.map((m) => ({ value: key(m.date, m.type), label: `${fmtDate(m.date)} · ${m.type}` }))}
        meeting={key(meeting.date, meeting.type)} months={allMonths} month={month}
        chosen={chosen.map((m) => key(m.date, m.type))} chosenText={chosen.map((m) => `${fmtDate(m.date)} · ${m.type}`).join(", ")}
        summary={summary} editHref={`/schedule?${new URLSearchParams({ date: meeting.date, type: meeting.type, mode: "edit" })}`}
        slipCount={slipCount} slipAux={slipAux} hasS89={templates.has(`s89_${language}`)} hasS140={templates.has(`s140_${language}`)}
        weekendMonths={[...new Set(meetings.filter((m) => m.type === WEEKEND).map((m) => m.date.slice(0, 7)))].sort()}
        weekendMeetings={meetings.filter((m) => m.type === WEEKEND).map((m) => key(m.date, m.type))}
        midweekMonths={[...new Set(meetings.filter((m) => m.type === MIDWEEK).map((m) => m.date.slice(0, 7)))].sort().reverse()}
        weeks={weekOptions} defaultWeek={weeks.find((w) => w >= thisWeek) ?? weeks[weeks.length - 1]}
        monthPeople={monthPeople} />
    </>
  );
}
