"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Icon } from "@/components/icons";
import { download, pyGet, pyUrl } from "@/components/py";
import { useToast } from "@/components/Toaster";
import { Note } from "@/components/ui";
import { useAct } from "@/components/useAct";
import { MIDWEEK, WEEKEND } from "@/lib/constants";
import { monthLabel } from "@/lib/dates";

type Opt = { value: string; label: string };

export function Printing(props: {
  scope: "meeting" | "month"; language: string; meetings: Opt[]; meeting: string; months: Opt[]; month: string;
  chosen: string[]; chosenText: string; editHref: string;
  summary: null | { heading: string; talk: string; rows: { part: string; person: string; assistant: string }[] };
  slipCount: number; slipAux: number; hasS89: boolean; hasS140: boolean;
  weekendMonths: string[]; weekendMeetings: string[]; midweekMonths: string[];
  weeks: Opt[]; defaultWeek: string; monthPeople: Record<string, { id: number; label: string }[]>;
}) {
  const router = useRouter();
  const path = usePathname();
  const [tab, setTab] = useState("print");
  const { scope, summary } = props;
  return (
    <div className="stack">
      <div className="card grid gap-3">
        <div className="seg w-fit" role="group" aria-label="Print">
          <button type="button" aria-pressed={scope === "meeting"} onClick={() => router.replace(`${path}?meeting=${encodeURIComponent(props.meeting)}`)}>One meeting</button>
          <button type="button" aria-pressed={scope === "month"} onClick={() => router.replace(`${path}?month=${props.month}`)}>A whole month</button>
        </div>
        {scope === "meeting" ? (
          <select className="input" aria-label="Meeting" value={props.meeting} onChange={(e) => router.replace(`${path}?meeting=${encodeURIComponent(e.target.value)}`)}>
            {props.meetings.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
          </select>
        ) : (
          <>
            <select className="input" aria-label="Month" value={props.month} onChange={(e) => router.replace(`${path}?month=${e.target.value}`)}>
              {props.months.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
            </select>
            <div className="caption mt-0">{props.chosenText}</div>
          </>
        )}
      </div>

      {summary ? (
        <div className="card">
          {summary.heading ? <div className="mb-1 text-sm text-muted">{summary.heading}</div> : null}
          {summary.talk ? <div className="mb-2 text-sm"><b>Public talk:</b> {summary.talk}</div> : null}
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Part</th><th>Assigned to</th><th>Assistant</th></tr></thead>
              <tbody>{summary.rows.map((r, i) => <tr key={i}><td>{r.part}</td><td>{r.person}</td><td>{r.assistant}</td></tr>)}</tbody>
            </table>
          </div>
          <Link className="btn mt-3" href={props.editHref}><Icon name="edit" /> Edit this schedule</Link>
        </div>
      ) : null}

      <nav className="tabs mb-0" aria-label="Sections">
        {[["print", "Slips & sheets"], ["export", "S-140 & CSV"], ["messages", "Messages"]].map(([k, l]) => (
          <button key={k} type="button" aria-current={tab === k ? "page" : undefined} onClick={() => setTab(k)}>{l}</button>
        ))}
      </nav>
      {tab === "print" ? <SlipsAndSheets {...props} /> : tab === "export" ? <Export {...props} /> : <Messages {...props} />}
    </div>
  );
}

function SlipsAndSheets(p: Parameters<typeof Printing>[0]) {
  const [busy, act] = useAct();
  const [twoUp, setTwoUp] = useState(true);
  const [weekendMonths, setWeekendMonths] = useState<string[]>(p.scope === "month" && p.weekendMonths.includes(p.month) ? [p.month] : []);
  const stem = p.scope === "month" ? p.month : p.chosen[0]?.split("|")[0];
  const midweek = p.chosen.filter((m) => m.endsWith(MIDWEEK));
  let weekend = p.chosen.filter((m) => m.endsWith(WEEKEND));
  let weekendStem = stem;
  if (weekendMonths.length) {
    const sorted = [...weekendMonths].sort();
    weekend = p.weekendMeetings.filter((m) => sorted.includes(m.slice(0, 7))).sort();
    weekendStem = sorted[0] === sorted[sorted.length - 1] ? sorted[0] : `${sorted[0]}_to_${sorted[sorted.length - 1]}`;
  }
  return (
    <>
      <div className="card grid gap-3">
        <h2 className="section-title mb-0">S-89 assignment slips</h2>
        {!p.slipCount ? <div className="empty">No student parts are assigned, so there are no slips to print.</div>
          : !p.hasS89 ? <Note tone="error">No blank S-89 has been uploaded for {p.language}. Add one under Admin → Official S-89 blank.</Note> : (
            <>
              {p.slipAux ? <div className="caption mt-0">{p.slipCount - p.slipAux} main hall and {p.slipAux} auxiliary classroom slip(s); each has its room ticked.</div> : null}
              <button type="button" className="btn primary w-fit" disabled={busy}
                onClick={() => act(() => download("slips", { meetings: p.chosen.join(","), lang: p.language, stem }))}>
                <Icon name="download" /> Download {p.slipCount} slip(s) ({p.language})
              </button>
            </>
          )}
      </div>
      <div className="card grid gap-3">
        <h2 className="section-title mb-0">Printable schedule</h2>
        {midweek.length > 1 ? (
          <label className="check"><input type="checkbox" checked={twoUp} onChange={(e) => setTwoUp(e.target.checked)} /> Two midweek weeks per sheet</label>
        ) : null}
        {p.weekendMonths.length ? (
          <div className="field"><span>Months on the weekend schedule</span>
            <div className="flex flex-wrap gap-x-4 gap-y-2">
              {p.weekendMonths.map((m) => (
                <label key={m} className="check"><input type="checkbox" checked={weekendMonths.includes(m)}
                  onChange={() => setWeekendMonths((x) => (x.includes(m) ? x.filter((y) => y !== m) : [...x, m]))} />{monthLabel(m)}</label>
              ))}
            </div>
            <span className="msg hint">None ticked: just the meetings chosen above. Ticked months print as one continuous list under a single header.</span>
          </div>
        ) : null}
        <div className="caption mt-0">The midweek and weekend sheets download separately.</div>
        <div className="btns">
          <button type="button" className="btn" disabled={busy || !midweek.length}
            onClick={() => act(() => download("sheet", { meetings: midweek.join(","), lang: p.language, compact: twoUp && midweek.length > 1 ? 1 : 0, stem }))}>
            <Icon name="print" /> Midweek schedule ({midweek.length})
          </button>
          <button type="button" className="btn" disabled={busy || !weekend.length}
            onClick={() => act(() => download("sheet", { meetings: weekend.join(","), lang: p.language, stem: weekendStem }))}>
            <Icon name="print" /> Weekend schedule ({weekend.length})
          </button>
        </div>
      </div>
    </>
  );
}

function Export(p: Parameters<typeof Printing>[0]) {
  const [busy, act] = useAct();
  const [month, setMonth] = useState(p.midweekMonths.includes(p.month) ? p.month : p.midweekMonths[0]);
  return (
    <>
      <div className="card grid gap-3">
        <h2 className="section-title mb-0">S-140</h2>
        {!p.midweekMonths.length ? <div className="empty">Save a midweek schedule to fill the S-140.</div>
          : !p.hasS140 ? <Note tone="warn">No {p.language} S-140 template. Upload the blank .docx under Admin.</Note> : (
            <div className="flex flex-wrap items-end gap-2">
              <label className="field"><span>Month</span>
                <select className="input" value={month} onChange={(e) => setMonth(e.target.value)}>
                  {p.midweekMonths.map((m) => <option key={m} value={m}>{monthLabel(m)}</option>)}
                </select>
              </label>
              <button type="button" className="btn primary" disabled={busy}
                onClick={() => act(() => download("s140", { month, lang: p.language }))}><Icon name="download" /> S-140 for {monthLabel(month)}</button>
            </div>
          )}
      </div>
      <div className="card grid gap-3">
        <h2 className="section-title mb-0">Spreadsheet</h2>
        <button type="button" className="btn w-fit" disabled={busy} onClick={() => act(() => download("csv", {}))}><Icon name="download" /> All schedules as CSV</button>
      </div>
    </>
  );
}

function Card({ params, stem }: { params: Record<string, string | number>; stem: string }) {
  const toast = useToast();
  const [busy, act] = useAct();
  const [text, setText] = useState<string | null>(null);
  const src = pyUrl("card", { ...params, inline: 1 });
  useEffect(() => { setText(null); }, [src]);
  const copy = async () => {
    try {
      const blob = fetch(src).then((r) => r.blob());
      await navigator.clipboard.write([new ClipboardItem({ "image/png": blob })]);
      toast("Copied. Paste it into a WhatsApp chat.");
    } catch {
      toast("This browser can't copy images. Use Download image.", { tone: "warn" });
    }
  };
  return (
    <div className="grid gap-4 md:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={src} alt={`Card: ${stem}`} className="w-full rounded-xl border border-line bg-subtle" />
      <div className="grid content-start gap-2">
        <button type="button" className="btn primary" disabled={busy} onClick={() => act(() => download("card", params))}><Icon name="download" /> Download image</button>
        <button type="button" className="btn" onClick={copy}><Icon name="copy" /> Copy image</button>
        <div className="caption mt-0">On a phone: download, then share the picture from your gallery to WhatsApp. On a computer: copy, then paste it straight into a WhatsApp chat.</div>
        <details className="rounded-xl border border-line px-3 py-2" onToggle={(e) => {
          if ((e.target as HTMLDetailsElement).open && text === null) {
            void pyGet<{ text: string }>("message_text", params).then((r) => setText(r.ok ? r.text : r.error));
          }
        }}>
          <summary className="cursor-pointer text-sm font-semibold">Text version</summary>
          <pre className="mt-2 max-h-80 overflow-auto whitespace-pre-wrap text-xs">{text ?? "Loading…"}</pre>
        </details>
      </div>
    </div>
  );
}

function Messages(p: Parameters<typeof Printing>[0]) {
  const [week, setWeek] = useState(p.defaultWeek);
  const months = Object.keys(p.monthPeople).sort().reverse();
  const [month, setMonth] = useState(months.includes(p.month) ? p.month : months[0]);
  const people = p.monthPeople[month] ?? [];
  const [person, setPerson] = useState<number | null>(null);
  const chosen = people.find((x) => x.id === person) ?? people[0];
  return (
    <>
      <div className="card grid gap-3">
        <h2 className="section-title mb-0">Weekly assignments</h2>
        <div className="caption mt-0">Pick a week: every part in it, midweek and weekend, on one card to share on WhatsApp. A part with nobody yet shows —.</div>
        <select className="input" aria-label="Week" value={week} onChange={(e) => setWeek(e.target.value)}>
          {p.weeks.map((w) => <option key={w.value} value={w.value}>{w.label}</option>)}
        </select>
        <Card params={{ week, lang: p.language }} stem={`assignments_${week}`} />
      </div>
      <div className="card grid gap-3">
        <h2 className="section-title mb-0">One person&apos;s month</h2>
        <div className="caption mt-0">Everything one person has in a month, parts and assisting, on a card of their own.</div>
        <div className="row2">
          <select className="input" aria-label="Month" value={month} onChange={(e) => { setMonth(e.target.value); setPerson(null); }}>
            {months.map((m) => <option key={m} value={m}>{monthLabel(m)}</option>)}
          </select>
          {people.length ? (
            <select className="input" aria-label="Participant" value={chosen?.id} onChange={(e) => setPerson(Number(e.target.value))}>
              {people.map((x) => <option key={x.id} value={x.id}>{x.label}</option>)}
            </select>
          ) : null}
        </div>
        {chosen ? <Card params={{ kind: "person", person: chosen.id, month, lang: p.language }} stem={chosen.label} />
          : <div className="empty">Nobody from the participants list has an assignment that month.</div>}
      </div>
    </>
  );
}
