"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { saveLetterDetails } from "@/actions/settings";
import {
  addEngagement, importTalks, removeEngagement, removeOutgoingSpeaker, saveTalks, setOutgoingSpeaker,
} from "@/actions/talks";
import { Icon } from "@/components/icons";
import { download, pyGet } from "@/components/py";
import { useToast } from "@/components/Toaster";
import { Note, Tabs } from "@/components/ui";
import { useAct } from "@/components/useAct";
import { WEEKEND } from "@/lib/constants";
import { fmtDate, today } from "@/lib/dates";
import { parseCSV, talkLabel, toCSV } from "@/lib/text";

type Talk = { number: string; title: string };
type Speaker = {
  id: number; name: string; talks: string[];
  engagements: { id: number; date: string; congregation: string; talk: string }[];
};

const TABS = [
  ["letters", "Invitation letters"], ["outgoing", "Outgoing speakers"], ["checklist", "Annual checklist"],
  ["list", "Talk list"], ["details", "Letter details"],
] as const;

export function Talks({ tab, guests, defaultGuest, letter, talks, brothers, speakers }: {
  tab: string; guests: { id: number; date: string; label: string; congregation: string }[]; defaultGuest: number;
  letter: Record<string, string>; talks: Talk[]; brothers: { id: number; name: string }[]; speakers: Speaker[];
}) {
  return (
    <>
      <Tabs current={`/talks?tab=${tab}`} tabs={TABS.map(([k, l]) => ({ href: `/talks?tab=${k}`, label: l }))} />
      {tab === "outgoing" ? <Outgoing talks={talks} brothers={brothers} speakers={speakers} />
        : tab === "checklist" ? <Checklist />
          : tab === "list" ? <TalkList talks={talks} />
            : tab === "details" ? <LetterDetails letter={letter} />
              : <Letters guests={guests} defaultGuest={defaultGuest} letter={letter} />}
    </>
  );
}

function Letters({ guests, defaultGuest, letter }: {
  guests: { id: number; date: string; label: string; congregation: string }[]; defaultGuest: number; letter: Record<string, string>;
}) {
  const [busy, act] = useAct();
  const [id, setId] = useState(defaultGuest);
  const guest = guests.find((g) => g.id === id);
  const missing = [["public meeting time", "meeting_time"], ["Kingdom Hall address", "hall_address"],
    ["Talk Coordinator sign-off name", "talk_coordinator_signoff"]].filter(([, k]) => !letter[k]).map(([l]) => l);
  return (
    <div className="card grid gap-3">
      <h2 className="section-title mb-0">Invitation letter</h2>
      <div className="caption mt-0">A letter to a guest speaker&apos;s congregation, asking them to release him for the visit.</div>
      {!guest ? (
        <Note>No weekend meeting has a guest speaker yet. Type the visiting speaker&apos;s name into the Public Talk part when creating the weekend schedule.</Note>
      ) : (
        <>
          <label className="field"><span>Guest speaker</span>
            <select className="input" value={id} onChange={(e) => setId(Number(e.target.value))}>
              {guests.map((g) => <option key={g.id} value={g.id}>{g.label}</option>)}
            </select>
          </label>
          {missing.length ? (
            <Note tone="warn">Fill in the {missing.join(", ")} in the <Link href="/talks?tab=details">Letter details</Link> tab first.</Note>
          ) : !guest.congregation ? (
            <>
              <Note tone="warn">This speaker&apos;s congregation isn&apos;t recorded yet. Fill in &quot;His congregation&quot; next to his name on the schedule.</Note>
              <Link className="btn w-fit" href={`/schedule?date=${guest.date}&type=${encodeURIComponent(WEEKEND)}&mode=edit`}><Icon name="edit" /> Open this schedule</Link>
            </>
          ) : (
            <button type="button" className="btn primary w-fit" disabled={busy} onClick={() => act(() => download("invitation", { row: guest.id }))}>
              <Icon name="download" /> Letter to {guest.congregation}
            </button>
          )}
        </>
      )}
    </div>
  );
}

/** A filterable tick list, for picking the talks a speaker has prepared. */
function TalkPicker({ talks, value, onChange }: { talks: Talk[]; value: string[]; onChange: (v: string[]) => void }) {
  const [filter, setFilter] = useState("");
  if (!talks.length) return <div className="caption mt-0">No talks in the list yet. Add them in the <Link href="/talks?tab=list">Talk list</Link> tab.</div>;
  const f = filter.trim().toLowerCase();
  const shown = talks.filter((t) => !f || talkLabel(t.number, t.title).toLowerCase().includes(f));
  return (
    <div className="field"><span>Talks he has prepared ({value.length})</span>
      <input className="input" placeholder="Filter by number or title" value={filter} onChange={(e) => setFilter(e.target.value)} />
      <div className="max-h-56 overflow-y-auto rounded-xl border border-line p-2">
        {shown.map((t) => (
          <label key={t.number} className="check py-1"><input type="checkbox" checked={value.includes(t.number)}
            onChange={() => onChange(value.includes(t.number) ? value.filter((n) => n !== t.number) : [...value, t.number])} />
            {talkLabel(t.number, t.title)}</label>
        ))}
        {!shown.length ? <div className="empty">No talk matches.</div> : null}
      </div>
    </div>
  );
}

function SpeakerCard({ s, talks }: { s: Speaker; talks: Talk[] }) {
  const [busy, act] = useAct();
  const titles = new Map(talks.map((t) => [t.number, t.title]));
  const [chosen, setChosen] = useState(s.talks.filter((n) => titles.has(n)));
  const [date, setDate] = useState(today());
  const [cong, setCong] = useState("");
  const [talk, setTalk] = useState("");
  return (
    <div className="rounded-xl border border-line p-3">
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <div className="font-semibold">{s.name}</div>
          <div className="caption mt-0.5">{s.talks.map((n) => talkLabel(n, titles.get(n))).join(", ") || "No talks listed yet."}</div>
        </div>
        <button type="button" className="btn small danger" disabled={busy} onClick={() => act(() => removeOutgoingSpeaker(s.id))}>Remove</button>
      </div>
      <details className="mt-2">
        <summary className="cursor-pointer text-sm font-semibold text-brand-ink">Edit prepared talks</summary>
        <div className="mt-2 grid gap-2">
          <TalkPicker talks={talks} value={chosen} onChange={setChosen} />
          {talks.length ? <button type="button" className="btn w-fit" disabled={busy} onClick={() => act(() => setOutgoingSpeaker(s.id, chosen))}>Save talks</button> : null}
        </div>
      </details>
      <details className="mt-2">
        <summary className="cursor-pointer text-sm font-semibold text-brand-ink">Going-out dates ({s.engagements.length})</summary>
        <div className="mt-2 grid gap-2">
          {s.engagements.map((e) => (
            <div key={e.id} className="flex items-center gap-2 text-sm">
              <span className="flex-1">{fmtDate(e.date)}{e.congregation ? ` — ${e.congregation}` : ""}{e.talk ? ` (${talkLabel(e.talk, titles.get(e.talk))})` : ""}</span>
              <button type="button" className="btn small" disabled={busy} onClick={() => act(() => removeEngagement(e.id))}>Remove</button>
            </div>
          ))}
          {!s.engagements.length ? <div className="empty">None recorded.</div> : null}
          <div className="row3 items-end">
            <label className="field"><span>Date</span><input type="date" className="input" value={date} onChange={(e) => setDate(e.target.value)} /></label>
            <label className="field"><span>Congregation</span><input className="input" placeholder="e.g. Dansoman Beach Ga" value={cong} onChange={(e) => setCong(e.target.value)} /></label>
            <label className="field"><span>Talk</span>
              <select className="input" value={talk} onChange={(e) => setTalk(e.target.value)}>
                <option value="">Not specified</option>
                {s.talks.map((n) => <option key={n} value={n}>{talkLabel(n, titles.get(n))}</option>)}
              </select>
            </label>
          </div>
          <button type="button" className="btn w-fit" disabled={busy}
            onClick={() => act(() => addEngagement(s.id, date, cong, talk), () => { setCong(""); setTalk(""); })}><Icon name="add" /> Add date</button>
        </div>
      </details>
    </div>
  );
}

function Outgoing({ talks, brothers, speakers }: { talks: Talk[]; brothers: { id: number; name: string }[]; speakers: Speaker[] }) {
  const [busy, act] = useAct();
  const approved = new Set(speakers.map((s) => s.id));
  const candidates = brothers.filter((b) => !approved.has(b.id));
  const [pick, setPick] = useState(candidates[0]?.id ?? 0);
  const [chosen, setChosen] = useState<string[]>([]);
  const current = candidates.some((c) => c.id === pick) ? pick : candidates[0]?.id ?? 0;
  if (!brothers.length) return <Note>No active brothers yet.</Note>;
  return (
    <div className="stack">
      <div className="caption mt-0">Brothers approved to give public talks at other congregations, and the talks they have ready. Marking a date one is going out keeps the local schedule from giving him a part that day.</div>
      <div className="card grid gap-3">
        <h2 className="section-title mb-0">Approved speakers</h2>
        {!speakers.length ? <div className="empty">Nobody is marked as an approved outgoing speaker yet.</div> : null}
        {speakers.map((s) => <SpeakerCard key={`${s.id}:${s.talks.join(",")}`} s={s} talks={talks} />)}
      </div>
      <div className="card grid gap-3">
        <h2 className="section-title mb-0">Approve a speaker</h2>
        {!candidates.length ? <div className="empty">Every active brother is already listed above.</div> : (
          <>
            <label className="field"><span>Brother</span>
              <select className="input" value={current} onChange={(e) => setPick(Number(e.target.value))}>
                {candidates.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </label>
            <TalkPicker talks={talks} value={chosen} onChange={setChosen} />
            <button type="button" className="btn primary w-fit" disabled={busy}
              onClick={() => act(() => setOutgoingSpeaker(current, chosen), () => setChosen([]))}>Approve as outgoing speaker</button>
          </>
        )}
      </div>
      <div className="card grid gap-3">
        <h2 className="section-title mb-0">Outgoing speakers letter</h2>
        <div className="caption mt-0">A letter for another congregation, listing our approved outgoing speakers and the talks they have ready.</div>
        {!speakers.length ? <div className="empty">Approve a speaker above and the letter can be printed.</div> : (
          <button type="button" className="btn w-fit" disabled={busy} onClick={() => act(() => download("outgoing_letter", {}))}>
            <Icon name="download" /> Download outgoing speakers letter
          </button>
        )}
      </div>
    </div>
  );
}

function Checklist() {
  const [busy, act] = useAct();
  const [years, setYears] = useState(3);
  const [data, setData] = useState<{ years: number[]; rows: { number: string; title: string; years: Record<string, string> }[] } | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let live = true;
    void pyGet<{ years: number[]; rows: { number: string; title: string; years: Record<string, string> }[] }>("checklist", { years })
      .then((r) => { if (!live) return; if (r.ok) { setData(r); setError(""); } else setError(r.error); });
    return () => { live = false; };
  }, [years]);
  const span = data ? (data.years.length === 1 ? `${data.years[0]}` : `${data.years[0]}–${data.years[data.years.length - 1]}`) : "";
  return (
    <div className="card grid gap-3">
      <div className="caption mt-0">Every talk, one row per number, with a column per year. A blank cell means it hasn&apos;t been given that year, so it&apos;s safe to assign again. Nothing here is ever deleted.</div>
      <label className="field w-40"><span>Years to show</span>
        <input type="number" className="input" min={1} max={6} value={years} onChange={(e) => setYears(Math.max(1, Math.min(6, Number(e.target.value) || 1)))} />
      </label>
      {error ? <Note tone="error">{error}</Note> : !data ? <div className="empty">Loading…</div> : !data.rows.length ? (
        <Note>No talks in the list yet. Add them in the <Link href="/talks?tab=list">Talk list</Link> tab.</Note>
      ) : (
        <>
          <div className="table-wrap max-h-[60vh] overflow-y-auto">
            <table className="table">
              <thead><tr><th>No.</th><th>Title</th>{data.years.map((y) => <th key={y}>{y}</th>)}</tr></thead>
              <tbody>{data.rows.map((r) => (
                <tr key={r.number}><td className="num">{r.number}</td><td>{r.title}</td>{data.years.map((y) => <td key={y} className="text-xs">{r.years[String(y)]}</td>)}</tr>
              ))}</tbody>
            </table>
          </div>
          <button type="button" className="btn w-fit" disabled={busy} onClick={() => act(() => download("checklist_pdf", { years }))}>
            <Icon name="download" /> Download checklist ({span})
          </button>
        </>
      )}
    </div>
  );
}

function saveText(text: string, name: string) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text], { type: "text/csv;charset=utf-8" }));
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 10_000);
}

function TalkList({ talks }: { talks: Talk[] }) {
  const toast = useToast();
  const [busy, act] = useAct();
  const [rows, setRows] = useState<Talk[]>(talks);
  const [file, setFile] = useState<File | null>(null);
  const [replace, setReplace] = useState(false);
  useEffect(() => { setRows(talks); }, [talks]);
  const set = (i: number, patch: Partial<Talk>) => setRows(rows.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  const importFile = async () => {
    if (!file) return;
    const table = parseCSV(await file.text());
    const header = (table[0] ?? []).map((h) => h.trim().toLowerCase());
    const n = header.indexOf("number"), t = header.indexOf("title");
    if (n < 0 || t < 0) { toast("Couldn't read that CSV: it needs a 'number' and a 'title' column.", { tone: "warn" }); return; }
    act(() => importTalks(table.slice(1).map((r) => ({ number: r[n] ?? "", title: r[t] ?? "" })), replace), () => setFile(null));
  };
  return (
    <div className="stack">
      <div className="card grid gap-3">
        <div className="caption mt-0">The outlines your congregation uses. Once they are here, creating a weekend schedule is picking one from the list.</div>
        <div className="table-wrap max-h-[60vh] overflow-y-auto">
          <table className="table">
            <thead><tr><th className="w-24">No.</th><th>Title</th><th className="w-10" /></tr></thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i}>
                  <td><input className="input cell-input" aria-label="Number" value={r.number} onChange={(e) => set(i, { number: e.target.value })} /></td>
                  <td><input className="input cell-input" aria-label="Title" value={r.title} onChange={(e) => set(i, { title: e.target.value })} /></td>
                  <td><button type="button" className="btn ghost small" aria-label="Remove talk" onClick={() => setRows(rows.filter((_, j) => j !== i))}><Icon name="close" /></button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="btns">
          <button type="button" className="btn" onClick={() => setRows([...rows, { number: "", title: "" }])}><Icon name="add" /> Add a talk</button>
          <button type="button" className="btn primary" disabled={busy} onClick={() => act(() => saveTalks(rows))}><Icon name="save" /> Save talks</button>
        </div>
        <div className="caption mt-0">Rows without a number are left out when saving.</div>
      </div>
      <div className="card grid gap-3">
        <h2 className="section-title mb-0">Load a list</h2>
        <div className="caption mt-0">A CSV with a <code>number</code> and a <code>title</code> column. Re-importing the same numbers updates their titles, so corrections are one upload rather than a hunt through the table.</div>
        <input type="file" accept=".csv,text/csv" className="input" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        <label className="check"><input type="checkbox" checked={replace} onChange={(e) => setReplace(e.target.checked)} /> Replace the whole list (otherwise the file is merged in)</label>
        <div className="btns">
          <button type="button" className="btn primary" disabled={busy || !file} onClick={importFile}><Icon name="upload" /> Import talks</button>
          {talks.length ? (
            <button type="button" className="btn" onClick={() => saveText(toCSV(["number", "title"], talks.map((t) => [t.number, t.title])), "public_talks.csv")}>
              <Icon name="download" /> Download the list as CSV
            </button>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function LetterDetails({ letter }: { letter: Record<string, string> }) {
  const [busy, act] = useAct();
  const [v, setV] = useState(letter);
  const field = (k: string, label: string, placeholder: string, hint?: string) => (
    <label className="field"><span>{label}</span>
      <input className="input" placeholder={placeholder} value={v[k] ?? ""} onChange={(e) => setV({ ...v, [k]: e.target.value })} />
      {hint ? <span className="msg hint">{hint}</span> : null}
    </label>
  );
  return (
    <form className="card form" onSubmit={(e) => { e.preventDefault(); act(() => saveLetterDetails(v)); }}>
      <div className="caption mt-0">Printed on the invitation letter and the outgoing speakers letter.</div>
      <div className="row2">
        {field("meeting_time", "Public meeting time", "e.g. 6:30pm")}
        {field("hall_address", "Kingdom Hall address", "e.g. Hansen Road Near Palledium")}
      </div>
      {field("talk_coordinator_signoff", "Talk Coordinator sign-off name", "", "Signs every letter. Update this here whenever the Talk Coordinator changes.")}
      <div className="row2">
        {field("talk_coordinator_phone", "Talk Coordinator phone", "e.g. 055 307 8753", "For the other congregation to reach out with questions.")}
        {field("talk_coordinator_email", "Talk Coordinator email", "e.g. niio@jwpub.org")}
      </div>
      <button className="btn primary w-fit" disabled={busy}>Save letter details</button>
    </form>
  );
}
