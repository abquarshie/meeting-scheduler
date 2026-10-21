"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { removeEventWeek, removeTemplate, saveMeetingDays, savePrinting, saveRotation } from "@/actions/settings";
import { Icon } from "@/components/icons";
import { MarkEventWeek } from "@/components/MarkEventWeek";
import { download, pyUpload } from "@/components/py";
import { Note } from "@/components/ui";
import { useAct } from "@/components/useAct";
import { WEEKDAYS } from "@/lib/constants";
import { toCSV } from "@/lib/text";

const FORMS = {
  s89: {
    title: "Official S-89 blank", accept: "application/pdf,.pdf", file: "Blank S-89",
    caption: "Upload the fillable blank S-89 for each slip language and the app prints on the real form, with its exact wording. Without one it draws its own slip.",
    none: "no blank form uploaded.",
  },
  s140: {
    title: "S-140 template (Word)", accept: ".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document", file: "Blank S-140 (.docx)",
    caption: "Upload the blank once per language and the Printing page uses it every month. It is a .docx, not a PDF, and the published blank holds one week; the app repeats it for the month.",
    none: "no S-140 template uploaded.",
  },
} as const;

function TemplateRow({ kind, language, fileName }: { kind: "s89" | "s140"; language: string; fileName?: string }) {
  const router = useRouter();
  const [busy, act] = useAct();
  const [file, setFile] = useState<File | null>(null);
  const [round, setRound] = useState(0);
  const f = FORMS[kind];
  return (
    <div className="grid gap-2 rounded-xl border border-line p-3">
      <div className="flex items-center gap-3">
        <span className="flex-1 text-sm">{language}: {fileName ? <b>{fileName}</b> : <span className="text-muted">{f.none}</span>}</span>
        {fileName ? (
          <button type="button" className="btn small danger" disabled={busy} onClick={() => act(() => removeTemplate(`${kind}_${language}`))}>Remove</button>
        ) : null}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <input key={round} type="file" accept={f.accept} aria-label={`${f.file} (${language})`} className="input min-w-0 flex-1"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        <button type="button" className="btn" disabled={busy || !file}
          onClick={() => file && act(() => pyUpload("template_upload", file, { kind, lang: language }), () => { setFile(null); setRound(round + 1); router.refresh(); })}>
          <Icon name="upload" /> Upload
        </button>
      </div>
    </div>
  );
}

export function Templates({ languages, stored }: { languages: string[]; stored: Record<string, string> }) {
  return (
    <>
      {(["s89", "s140"] as const).map((kind) => (
        <div key={kind} className="card grid gap-3">
          <h2 className="section-title mb-0">{FORMS[kind].title}</h2>
          <div className="caption mt-0">{FORMS[kind].caption}</div>
          {languages.map((l) => <TemplateRow key={l} kind={kind} language={l} fileName={stored[`${kind}_${l}`] || (`${kind}_${l}` in stored ? "uploaded file" : undefined)} />)}
        </div>
      ))}
    </>
  );
}

export function Backup() {
  const router = useRouter();
  const [busy, act] = useAct();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<{ ok: true; text: string } | { ok: false; text: string } | null>(null);
  const [sure, setSure] = useState(false);
  const [round, setRound] = useState(0);
  const choose = async (f: File | null) => {
    setFile(f); setSure(false); setPreview(null);
    if (!f) return;
    try {
      const data = JSON.parse(await f.text());
      if (!data || typeof data !== "object" || Array.isArray(data)) throw new Error("This isn't a Meeting Scheduler backup.");
      setPreview({ ok: true, text: `Backup from ${data._created ?? "unknown date"}: ${(data.students ?? []).length} participants, ${(data.schedules ?? []).length} schedule rows.` });
    } catch (e) {
      setPreview({ ok: false, text: `That file can't be restored: ${(e as Error).message}` });
    }
  };
  return (
    <div className="card grid gap-3">
      <h2 className="section-title mb-0">Backup file</h2>
      <button type="button" className="btn primary w-fit" disabled={busy} onClick={() => act(() => download("backup", {}), () => router.refresh())}>
        <Icon name="download" /> Download full backup (.json)
      </button>
      <div className="caption mt-0">Includes participants, schedules, away dates, suspensions, the workbook, settings and the change log.</div>
      <label className="field"><span>Restore from a backup file</span>
        <input key={round} type="file" accept=".json,application/json" className="input" onChange={(e) => void choose(e.target.files?.[0] ?? null)} />
      </label>
      {preview ? <Note tone={preview.ok ? undefined : "error"}>{preview.text}</Note> : null}
      {preview?.ok && file ? (
        <>
          <label className="check"><input type="checkbox" checked={sure} onChange={(e) => setSure(e.target.checked)} /> I understand this replaces all current data</label>
          <button type="button" className="btn danger w-fit" disabled={busy || !sure}
            onClick={() => act(() => pyUpload("restore", file), () => { setFile(null); setPreview(null); setSure(false); setRound(round + 1); router.refresh(); })}>
            Restore this backup
          </button>
        </>
      ) : null}
    </div>
  );
}

export function Settings({ congregation, useAux, gaConvert, midweek, weekend, gap, events }: {
  congregation: string; useAux: boolean; gaConvert: boolean; midweek: string; weekend: string; gap: number;
  events: { id: number; text: string }[];
}) {
  const [busy, act] = useAct();
  const [p, setP] = useState({ congregation, useAux, gaConvert });
  const [days, setDays] = useState({ midweek, weekend });
  const [rest, setRest] = useState(gap);
  return (
    <>
      <form className="card form" onSubmit={(e) => { e.preventDefault(); act(() => savePrinting(p)); }}>
        <h2 className="section-title mb-0">Printing</h2>
        <label className="field"><span>Congregation name</span>
          <input className="input" value={p.congregation} onChange={(e) => setP({ ...p, congregation: e.target.value })} />
          <span className="msg hint">Printed at the top of every schedule sheet. The slip and schedule language is chosen in the sidebar.</span>
        </label>
        <label className="check"><input type="checkbox" checked={p.useAux} onChange={(e) => setP({ ...p, useAux: e.target.checked })} />
          Auxiliary classroom in use (the default for new midweek schedules; any week can still differ)</label>
        <label className="check"><input type="checkbox" checked={p.gaConvert} onChange={(e) => setP({ ...p, gaConvert: e.target.checked })} />
          Convert 3 ) N to ɛ ɔ ŋ when saving names (turn off if a name genuinely contains 3, ) or a capital N)</label>
        <button className="btn w-fit" disabled={busy}>Save printing settings</button>
      </form>
      <form className="card form" onSubmit={(e) => { e.preventDefault(); act(() => saveMeetingDays(days.midweek, days.weekend)); }}>
        <h2 className="section-title mb-0">Meeting days</h2>
        <div className="caption mt-0">Used to place workbook weeks on the right day in the month view.</div>
        <div className="row2">
          <label className="field"><span>Midweek meeting day</span>
            <select className="input" value={days.midweek} onChange={(e) => setDays({ ...days, midweek: e.target.value })}>{WEEKDAYS.map((d) => <option key={d}>{d}</option>)}</select>
          </label>
          <label className="field"><span>Weekend meeting day</span>
            <select className="input" value={days.weekend} onChange={(e) => setDays({ ...days, weekend: e.target.value })}>{WEEKDAYS.map((d) => <option key={d}>{d}</option>)}</select>
          </label>
        </div>
        <button className="btn w-fit" disabled={busy}>Save meeting days</button>
      </form>
      <form className="card form" onSubmit={(e) => { e.preventDefault(); act(() => saveRotation(rest)); }}>
        <h2 className="section-title mb-0">Rotation</h2>
        <label className="field max-w-sm"><span>Days before someone may take the same part again</span>
          <input type="number" className="input" min={1} max={90} value={rest} onChange={(e) => setRest(Number(e.target.value))} />
        </label>
        <div className="caption mt-0">Suggest and the red &quot;too soon&quot; marker use this many days since someone&apos;s last turn at a part. The rest of the colour-coding doesn&apos;t change; this only moves where the red/green line falls.</div>
        <button className="btn w-fit" disabled={busy}>Save rotation setting</button>
      </form>
      <div className="card grid gap-3">
        <h2 className="section-title mb-0">Assemblies &amp; conventions</h2>
        <div className="caption mt-0">A week with a circuit assembly or a convention has no regular midweek or weekend meeting. Marked here, it shows its own label everywhere that week appears, and is never offered as a schedule to create.</div>
        {events.length ? events.map((e) => (
          <div key={e.id} className="flex items-center gap-3 text-sm">
            <span className="flex-1">{e.text}</span>
            <button type="button" className="btn small" disabled={busy} onClick={() => act(() => removeEventWeek(e.id))}>Remove</button>
          </div>
        )) : <div className="empty">None marked.</div>}
        <MarkEventWeek />
      </div>
    </>
  );
}

export function ChangeLog({ log }: { log: { id: number; ts: string; user: string; action: string; details: string }[] }) {
  const [who, setWho] = useState<string[]>([]);
  if (!log.length) return <Note>No changes recorded yet.</Note>;
  const users = [...new Set(log.map((l) => l.user).filter(Boolean))].sort();
  const shown = who.length ? log.filter((l) => who.includes(l.user)) : log;
  return (
    <div className="card grid gap-3">
      {users.length > 1 ? (
        <div className="flex flex-wrap gap-x-4 gap-y-2">
          <span className="text-[13px] font-semibold">Who</span>
          {users.map((u) => (
            <label key={u} className="check"><input type="checkbox" checked={who.includes(u)}
              onChange={() => setWho(who.includes(u) ? who.filter((x) => x !== u) : [...who, u])} />{u}</label>
          ))}
        </div>
      ) : null}
      <div className="table-wrap max-h-[65vh] overflow-y-auto">
        <table className="table">
          <thead><tr><th>When</th><th>Who</th><th>What</th><th>Details</th></tr></thead>
          <tbody>{shown.map((l) => (
            <tr key={l.id}><td className="whitespace-nowrap">{l.ts}</td><td>{l.user}</td><td>{l.action}</td><td className="break-words">{l.details}</td></tr>
          ))}</tbody>
        </table>
      </div>
      <button type="button" className="btn w-fit" onClick={() => {
        const a = document.createElement("a");
        a.href = URL.createObjectURL(new Blob([toCSV(["When", "Who", "What", "Details"], shown.map((l) => [l.ts, l.user, l.action, l.details]))], { type: "text/csv;charset=utf-8" }));
        a.download = "change_log.csv";
        a.click();
        setTimeout(() => URL.revokeObjectURL(a.href), 10_000);
      }}><Icon name="download" /> Download change log (CSV)</button>
    </div>
  );
}
