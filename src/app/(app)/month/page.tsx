import type { Metadata } from "next";
import Link from "next/link";
import { MarkEventWeek } from "@/components/MarkEventWeek";
import { Bar, Note, PageHead } from "@/components/ui";
import { EVENT_TEXT, HALL_NAMES, MAIN_HALL, MIDWEEK } from "@/lib/constants";
import {
  eventLabel, fillCounts, getEvents, getMetas, getRows, getSettings, getWorkbook, key, meetingRows, savedMeetings,
  setting, workbookStatus,
} from "@/lib/data";
import { fmtDate, lastDayOfMonth, monthLabel, today } from "@/lib/dates";
import { talkText } from "@/lib/text";
import { CreateWeeks } from "./CreateWeeks";
import { MonthPick } from "./MonthPick";

export const metadata: Metadata = { title: "Month overview" };

type Line = { date: string; meeting: string; pct: number | null; open: number | null; aux: string; heading: string; href?: string };

export default async function MonthPage({ searchParams }: { searchParams: Promise<{ m?: string }> }) {
  const [{ m }, rows, metas, settings, workbook, events] = await Promise.all([
    searchParams, getRows(), getMetas(), getSettings(), getWorkbook(), getEvents(),
  ]);
  const thisMonth = today().slice(0, 7);
  const months = new Set([thisMonth, ...rows.map((r) => r.meeting_date.slice(0, 7)),
    ...workbook.weeks.filter((w) => w.start).map((w) => w.start!.slice(0, 7))]);
  const list = [...months].sort().reverse();
  const month = m && months.has(m) ? m : thisMonth;

  const lines: Line[] = [];
  for (const mt of savedMeetings(rows).filter((x) => x.date.startsWith(month))) {
    const r = meetingRows(rows, mt.date, mt.type);
    const meta = metas.get(key(mt.date, mt.type));
    const c = fillCounts(r);
    lines.push({
      date: mt.date, meeting: mt.type, pct: Math.round((100 * c.filled) / Math.max(c.needed, 1)), open: c.needed - c.filled,
      aux: r.some((x) => x.hall !== MAIN_HALL) ? "Yes" : "", heading: meta?.heading || talkText(meta),
      href: `/schedule?${new URLSearchParams({ date: mt.date, type: mt.type, mode: "edit" })}`,
    });
  }
  const toCreate: { date: string; label: string }[] = [];
  for (const w of workbookStatus(workbook.weeks, rows, settings, events)) {
    if (!w.meeting.startsWith(month) || w.status === "saved") continue;
    if (w.status === "no meeting") {
      lines.push({ date: w.meeting, meeting: MIDWEEK, pct: null, open: null, aux: "", heading: `${w.label} · ${eventLabel(events, w.meeting)}` });
      continue;
    }
    toCreate.push({ date: w.meeting, label: w.label });
    lines.push({ date: w.meeting, meeting: MIDWEEK, pct: null, open: null, aux: "", heading: `${w.label} · not created yet`,
      href: `/schedule?${new URLSearchParams({ date: w.meeting, type: MIDWEEK })}` });
  }
  // assemblies and conventions that line up with no workbook week
  const shown = new Set(lines.map((l) => l.date));
  for (const e of events) {
    if (e.start > lastDayOfMonth(month) || e.end < `${month}-01` || shown.has(e.start)) continue;
    lines.push({ date: e.start, meeting: "—", pct: null, open: null, aux: "",
      heading: EVENT_TEXT[e.kind].en + (e.start === e.end ? "" : ` – ${fmtDate(e.end)}`) });
  }
  lines.sort((a, b) => a.date.localeCompare(b.date) || a.meeting.localeCompare(b.meeting));
  const totalOpen = lines.reduce((n, l) => n + (l.open ?? 0), 0);

  return (
    <>
      <PageHead title="Month overview" sub="Every meeting this month, what is still open, and month-wide printing.">
        <MonthPick months={list.map((x) => ({ value: x, label: monthLabel(x) }))} value={month} />
      </PageHead>
      <div className="stack">
        {lines.length ? (
          <div className="card">
            <div className="table-wrap">
              <table className="table">
                <thead><tr><th>Date</th><th>Meeting</th><th>Filled</th><th className="r">Open slots</th><th>{HALL_NAMES.aux_1.replace(" 1", "")}</th><th>Heading</th></tr></thead>
                <tbody>
                  {lines.map((l, i) => (
                    <tr key={i}>
                      <td className="whitespace-nowrap">{l.href ? <Link href={l.href}>{fmtDate(l.date)}</Link> : fmtDate(l.date)}</td>
                      <td>{l.meeting}</td>
                      <td className="min-w-28">{l.pct === null ? "" : <div className="flex items-center gap-2"><Bar pct={l.pct} label="Filled" /><span className="num text-xs text-muted">{l.pct}%</span></div>}</td>
                      <td className="r num">{l.open ?? ""}</td>
                      <td>{l.aux}</td>
                      <td>{l.heading}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : <Note>Nothing scheduled this month yet.</Note>}
        {lines.length ? (totalOpen ? <Note tone="warn">{totalOpen} slot(s) still open this month.</Note>
          : !toCreate.length ? <Note tone="ok">Every slot this month is filled.</Note> : null) : null}

        {toCreate.length ? (
          <div className="card grid gap-3">
            <h2 className="section-title mb-0">Workbook weeks without a schedule</h2>
            <CreateWeeks weeks={toCreate} auxDefault={setting(settings, "use_aux", "1") === "1"} />
            <details className="rounded-xl border border-line px-3 py-2">
              <summary className="cursor-pointer text-sm font-semibold">Is one of these an assembly or convention week?</summary>
              <div className="mt-3"><MarkEventWeek defaultDay={toCreate[0].date} /></div>
            </details>
          </div>
        ) : null}

        <div><Link className="btn" href={`/print?month=${month}`}>Print this month</Link></div>
      </div>
    </>
  );
}
