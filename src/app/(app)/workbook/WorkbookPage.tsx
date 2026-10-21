"use client";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Confirm } from "@/components/Sheet";
import { Icon } from "@/components/icons";
import { py, pyUpload } from "@/components/py";
import { Note } from "@/components/ui";
import { useAct } from "@/components/useAct";
import { ROLES } from "@/lib/constants";
import type { WorkbookPart, WorkbookWeek } from "@/lib/data";
import { today, weekDatesText } from "@/lib/dates";

const SECTIONS = ["Treasures", "Ministry", "Living"];

type Upload = {
  message: string; dropped: string[]; empty: string[]; broken: { week: string; title: string }[];
  guessed: { week: string; no: number; title: string }[]; notEnglish: boolean;
};

export function WorkbookPage({ weeks, file, skipPast: savedSkip, datesSure }: {
  weeks: WorkbookWeek[]; file: string; skipPast: boolean; datesSure: boolean;
}) {
  const router = useRouter();
  const [busy, act] = useAct();
  const [skipPast, setSkipPast] = useState(savedSkip);
  const [pdf, setPdf] = useState<File | null>(null);
  const [report, setReport] = useState<Upload | null>(null);
  const [removing, setRemoving] = useState(false);
  const done = () => router.refresh();

  const upload = () => pdf && act(async () => {
    const r = await pyUpload<Upload>("workbook_upload", pdf, { skipPast: skipPast ? "1" : "0" });
    if (r.ok) setReport(r);
    return r;
  }, () => { setPdf(null); done(); });

  return (
    <div className="stack">
      <div className="card grid gap-3">
        <div className="text-sm">Upload the Life and Ministry Meeting Workbook PDF. Numbered parts with their minutes are read for each week, and you can correct them below.</div>
        {weeks.length ? (
          <div className="note flex flex-wrap items-center gap-3">
            <span className="flex-1">Workbook in use: <b>{file || "uploaded workbook"}</b> ({weeks.length} week(s)). Uploading another replaces it.</span>
            <button type="button" className="btn small danger" onClick={() => setRemoving(true)}><Icon name="trash" /> Remove</button>
          </div>
        ) : null}
        <label className="check"><input type="checkbox" checked={skipPast} onChange={(e) => setSkipPast(e.target.checked)} />
          Start from the current week</label>
        <span className="msg hint -mt-2">Weeks that finished before today are left out. Untick to keep the whole workbook, for example to fill in a week you missed.</span>
        <input type="file" accept="application/pdf,.pdf" className="input" onChange={(e) => setPdf(e.target.files?.[0] ?? null)} />
        <button type="button" className="btn primary w-fit" disabled={busy || !pdf} onClick={upload}><Icon name="upload" /> Read this workbook</button>
        {report ? <UploadReport r={report} /> : null}
      </div>
      {weeks.length ? (
        <>
          <WeekDates key={`${file}|${weeks[0].start}`} weeks={weeks} skipPast={skipPast} datesSure={datesSure} done={done} />
          <WeeksFound weeks={weeks} />
          <ReviewWeek weeks={weeks} done={done} />
        </>
      ) : null}
      <Confirm open={removing} button="Remove" onCancel={() => setRemoving(false)}
        message="Remove the workbook? Schedules will use the standard part list until another workbook is uploaded. Saved schedules are not changed."
        onConfirm={() => { setRemoving(false); act(() => py("workbook_remove", {}), done); }} />
    </div>
  );
}

function UploadReport({ r }: { r: Upload }) {
  return (
    <div className="grid gap-2">
      {r.dropped.length ? <Note>{r.dropped.length} week(s) already finished and were left out: {r.dropped.join(", ")}</Note> : null}
      {r.empty.length ? <Note tone="warn">No parts found under: {r.empty.join(", ")}</Note> : null}
      {r.broken.length ? (
        <Note tone="error">The text in this PDF could not be read properly: {r.broken.length} part title(s) came out garbled, so part numbers may be missing too. This is a problem with the file&apos;s fonts, not its contents. Example: {JSON.stringify(r.broken[0].title.slice(0, 60))}</Note>
      ) : null}
      {r.guessed.length ? (
        <Note tone="warn">{r.guessed.length} field-ministry part(s) didn&apos;t match a known part type, so they default to Initial Presentation. Only people with that privilege will be offered for them. Set the Role below if that&apos;s wrong: {r.guessed.slice(0, 4).map((g) => `${g.week} no. ${g.no}`).join(", ")}{r.guessed.length > 4 ? "…" : ""}</Note>
      ) : null}
      {r.notEnglish ? <Note>The week headings aren&apos;t in English, so sections are guessed from part numbers and durations. Check them below.</Note> : null}
    </div>
  );
}

function WeekDates({ weeks, skipPast, datesSure, done }: { weeks: WorkbookWeek[]; skipPast: boolean; datesSure: boolean; done: () => void }) {
  const [busy, act] = useAct();
  const [first, setFirst] = useState(weeks[0].start ?? today());
  return (
    <div className="card grid gap-3">
      <h2 className="section-title mb-0">Week dates</h2>
      {!datesSure ? <Note tone="warn">The week dates were guessed. Check the first week below; every other week follows from it.</Note> : null}
      <div className="flex flex-wrap items-end gap-2">
        <label className="field"><span>First week ({weeks[0].label}) begins on</span>
          <input type="date" className="input" value={first} onChange={(e) => setFirst(e.target.value)} />
          <span className="msg hint">The Monday of the first week in the workbook.</span>
        </label>
        <button type="button" className="btn mb-6" disabled={busy || !first} onClick={() => act(() => py("workbook_dates", { first, skipPast }), done)}>Apply dates</button>
      </div>
    </div>
  );
}

function WeeksFound({ weeks }: { weeks: WorkbookWeek[] }) {
  const unnamed = weeks.map((w) => w.label).filter((l) => /^Week \d+( \(\d+\))?$/.test(l));
  return (
    <div className="card grid gap-3">
      <h2 className="section-title mb-0">Weeks found</h2>
      <div className="table-wrap">
        <table className="table">
          <thead><tr><th>Week</th><th>Reading</th><th>Dates</th><th className="r">Parts</th><th>Numbers</th><th>Missing</th></tr></thead>
          <tbody>{weeks.map((w) => (
            <tr key={w.label}>
              <td className="whitespace-nowrap">{w.label}</td><td>{w.book ?? ""}</td><td className="whitespace-nowrap">{weekDatesText(w.start, w.end)}</td>
              <td className="r num">{w.parts.length}</td><td>{w.parts.map((p) => p.part_no).join(", ")}</td>
              <td className={w.gaps?.length ? "font-semibold text-warn" : ""}>{w.gaps?.join(", ") || "—"}</td>
            </tr>
          ))}</tbody>
        </table>
      </div>
      {unnamed.length ? (
        <Note tone="warn">The date line above these weeks wasn&apos;t recognised, so they are numbered instead: {unnamed.join(", ")}. The parts are still right; rename them below so the S-140 shows the real heading.</Note>
      ) : null}
      {weeks.some((w) => w.gaps?.length) ? <Note tone="warn">Some weeks have missing part numbers. Open the week below, compare with the workbook text, and add the missing rows.</Note> : null}
    </div>
  );
}

type EditRow = { part_no: string; title: string; minutes: string; section: string; role: string };
const toRow = (p: WorkbookPart): EditRow => ({
  part_no: p.part_no ? String(p.part_no) : "", title: p.title, minutes: p.minutes ? String(p.minutes) : "", section: p.section, role: p.role,
});

function ReviewWeek({ weeks, done }: { weeks: WorkbookWeek[]; done: () => void }) {
  const [busy, act] = useAct();
  const [label, setLabel] = useState(weeks[0].label);
  const week = weeks.find((w) => w.label === label) ?? weeks[0];
  const [heading, setHeading] = useState(week.label);
  const [rows, setRows] = useState<EditRow[]>(week.parts.map(toRow));
  useEffect(() => { setHeading(week.label); setRows(week.parts.map(toRow)); }, [week]);
  const set = (i: number, patch: Partial<EditRow>) => setRows(rows.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  const newHeading = heading.trim().normalize("NFC");
  return (
    <div className="card grid gap-3">
      <h2 className="section-title mb-0">Review and correct a week</h2>
      <label className="field"><span>Week</span>
        <select className="input" value={week.label} onChange={(e) => setLabel(e.target.value)}>
          {weeks.map((w) => <option key={w.label}>{w.label}</option>)}
        </select>
      </label>
      <div className="flex flex-wrap items-end gap-2">
        <label className="field min-w-56 flex-1"><span>Week heading</span>
          <input className="input" value={heading} onChange={(e) => setHeading(e.target.value)} />
          <span className="msg hint">Shown on the S-140 and in the week lists.</span>
        </label>
        <button type="button" className="btn mb-6" disabled={busy || !newHeading || newHeading === week.label}
          onClick={() => act(() => py("workbook_rename", { week: week.label, label: newHeading }), () => { setLabel(newHeading); done(); })}>Rename</button>
      </div>
      <div className="grid gap-4 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <div className="grid content-start gap-2">
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th className="w-16">No.</th><th>Title</th><th className="w-16">Min</th><th>Section</th><th>Role</th><th className="w-10" /></tr></thead>
              <tbody>{rows.map((r, i) => (
                <tr key={i}>
                  <td><input className="input cell-input" inputMode="numeric" aria-label="Number" value={r.part_no} onChange={(e) => set(i, { part_no: e.target.value })} /></td>
                  <td><input className="input cell-input min-w-48" aria-label="Title" value={r.title} onChange={(e) => set(i, { title: e.target.value })} /></td>
                  <td><input className="input cell-input" inputMode="numeric" aria-label="Minutes" value={r.minutes} onChange={(e) => set(i, { minutes: e.target.value })} /></td>
                  <td><select className="input cell-input" aria-label="Section" value={r.section} onChange={(e) => set(i, { section: e.target.value })}>
                    <option value="">—</option>{SECTIONS.map((s) => <option key={s}>{s}</option>)}</select></td>
                  <td><select className="input cell-input" aria-label="Role" value={r.role} onChange={(e) => set(i, { role: e.target.value })}>
                    <option value="">—</option>{ROLES.map((s) => <option key={s}>{s}</option>)}</select></td>
                  <td><button type="button" className="btn ghost small" aria-label="Remove part" onClick={() => setRows(rows.filter((_, j) => j !== i))}><Icon name="close" /></button></td>
                </tr>
              ))}</tbody>
            </table>
          </div>
          <div className="btns">
            <button type="button" className="btn" onClick={() => setRows([...rows, { part_no: "", title: "", minutes: "", section: "", role: "" }])}><Icon name="add" /> Add a part</button>
            <button type="button" className="btn primary" disabled={busy} onClick={() => act(() => py("workbook_week", { week: week.label, parts: rows }), done)}>
              <Icon name="save" /> Save corrections for this week
            </button>
          </div>
          <div className="caption mt-0">Rows without a title, section or role are left out when saving.</div>
        </div>
        <label className="field"><span>Workbook text for this week</span>
          <textarea className="input min-h-[420px] font-mono text-xs" readOnly value={week.text ?? ""} />
        </label>
      </div>
    </div>
  );
}
