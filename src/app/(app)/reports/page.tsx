import type { Metadata } from "next";
import { Note, PageHead } from "@/components/ui";
import { CATEGORIES, HALL_NAMES, MAIN_HALL, ROLES } from "@/lib/constants";
import { getPeople, getRows, suspensionText } from "@/lib/data";
import { addDays, fmtDate, isISODate, today } from "@/lib/dates";
import { CsvButton, Filters, PersonPick } from "./Controls";

export const metadata: Metadata = { title: "Reports" };

const SPANS = ["3", "6", "12", "custom"] as const;

type SP = { span?: string; from?: string; to?: string; future?: string; all?: string; cat?: string; person?: string };

export default async function ReportsPage({ searchParams }: { searchParams: Promise<SP> }) {
  const [sp, people, rows] = await Promise.all([searchParams, getPeople(), getRows()]);
  const head = <PageHead title="Reports" sub="How often each person had a part, to spot anyone left out." />;
  if (!people.length) return <>{head}<Note>No participants yet.</Note></>;

  const now = today();
  const span = (SPANS as readonly string[]).includes(sp.span ?? "") ? sp.span! : "6";
  let start: string, end: string;
  if (span === "custom") {
    start = isISODate(sp.from) ? sp.from : addDays(now, -182);
    end = isISODate(sp.to) ? sp.to : now;
  } else {
    start = addDays(now, -Math.round(Number(span) * 30.4));
    end = now;
  }
  const future = sp.future === "1";
  if (future) end = "9999-12-31";
  const activeOnly = sp.all !== "1";
  const cats = sp.cat ? sp.cat.split(",").filter((c) => (CATEGORIES as readonly string[]).includes(c)) : [...CATEGORIES];

  const period = rows.filter((r) => start <= r.meeting_date && r.meeting_date <= end);
  const chosen = people.filter((p) => (!activeOnly || p.active) && cats.includes(p.gender));
  const report = chosen.map((p) => {
    const own = period.filter((r) => r.student_id === p.id);
    const assisting = period.filter((r) => r.assistant_id === p.id);
    const dates = [...own, ...assisting].map((r) => r.meeting_date).sort();
    const roles: Record<string, number> = {};
    for (const r of own) if (r.role) roles[r.role] = (roles[r.role] ?? 0) + 1;
    return {
      name: p.name, category: p.gender, group: p.groups.join(", ") || "Adult",
      status: !p.active ? "Inactive" : suspensionText(p, now) || "Active",
      parts: own.length, assisting: assisting.length, total: own.length + assisting.length,
      last: dates.length ? fmtDate(dates[dates.length - 1]) : "", roles,
    };
  }).sort((a, b) => a.total - b.total || a.name.localeCompare(b.name));
  const roleCols = ROLES.filter((r) => report.some((x) => x.roles[r]));
  const none = report.filter((r) => r.total === 0);

  const header = ["Name", "Category", "Group", "Status", "Parts", "Assisting", "Total", "Last", ...roleCols];
  const csvRows = report.map((r) => [r.name, r.category, r.group, r.status, r.parts, r.assisting, r.total, r.last, ...roleCols.map((c) => r.roles[c] ?? 0)]);

  const personId = Number(sp.person) || people[0].id;
  const history = rows
    .filter((r) => r.student_id === personId || r.assistant_id === personId)
    .sort((a, b) => b.meeting_date.localeCompare(a.meeting_date))
    .slice(0, 100)
    .map((r) => ({
      date: r.meeting_date,
      part: r.assistant_id === personId && r.student_id !== personId ? `${r.part_name} (assistant)` : r.part_name ?? "",
      room: HALL_NAMES[r.hall || MAIN_HALL] ?? "",
    }));

  return (
    <>
      {head}
      <div className="stack">
        <Filters span={span} from={start} to={span === "custom" ? end : now} future={future} activeOnly={activeOnly} cats={cats}
          caption={`From ${fmtDate(start)}${future ? "" : ` to ${fmtDate(end)}`}`} />
        {!report.length ? <Note>Nobody matches these filters.</Note> : (
          <div className="card grid gap-3">
            {none.length ? <Note tone="warn">{none.length} person(s) had no assignment in this period: {none.map((r) => r.name).join(", ")}</Note> : null}
            <div className="table-wrap max-h-[65vh] overflow-y-auto">
              <table className="table">
                <thead><tr>{header.map((h, i) => <th key={h} className={i >= 4 && i !== 7 ? "r" : ""}>{h}</th>)}</tr></thead>
                <tbody>{report.map((r) => (
                  <tr key={r.name}>
                    <td className="whitespace-nowrap font-medium">{r.name}</td><td>{r.category}</td><td>{r.group}</td><td className="whitespace-nowrap">{r.status}</td>
                    <td className="r num">{r.parts}</td><td className="r num">{r.assisting}</td><td className="r num font-semibold">{r.total}</td>
                    <td className="whitespace-nowrap">{r.last}</td>
                    {roleCols.map((c) => <td key={c} className="r num">{r.roles[c] ?? 0}</td>)}
                  </tr>
                ))}</tbody>
              </table>
            </div>
            <CsvButton header={header} rows={csvRows} name={`assignment_report_${start}_${future ? "9999-12-31" : end}.csv`} />
          </div>
        )}
        <div className="card grid gap-3">
          <h2 className="section-title mb-0">Person history</h2>
          <PersonPick people={people.map((p) => ({ id: p.id, name: p.name }))} value={personId} />
          {!history.length ? <div className="empty">No assignments yet.</div> : (
            <div className="table-wrap max-h-[60vh] overflow-y-auto">
              <table className="table">
                <thead><tr><th>Date</th><th>Part</th><th>Room</th></tr></thead>
                <tbody>{history.map((h, i) => <tr key={i}><td className="whitespace-nowrap">{fmtDate(h.date)}</td><td>{h.part}</td><td>{h.room}</td></tr>)}</tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
