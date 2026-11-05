"use client";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  addAway, addPerson, clearAway, deletePerson, setSuspension, updatePerson, upcomingFor, type PersonInput,
} from "@/actions/participants";
import { Confirm } from "@/components/Sheet";
import { Note } from "@/components/ui";
import { useAct } from "@/components/useAct";
import { CATEGORIES, GROUPS, PRIVILEGES } from "@/lib/constants";
import type { Person } from "@/lib/data";
import { addDays, awaySummary, fmtDate, today } from "@/lib/dates";

const NO_FAMILY = "— none —";

function suspendedNow(p: Person) {
  return p.suspended && (!p.suspendedUntil || today() <= p.suspendedUntil);
}

function PersonForm({ initial, families, submit, button, withActive }: {
  initial: PersonInput; families: string[]; button: string; withActive?: boolean;
  submit: (p: PersonInput) => void;
}) {
  const [p, setP] = useState(initial);
  const [newFamily, setNewFamily] = useState("");
  const toggle = (list: string[], v: string) => (list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);
  return (
    <form className="form" onSubmit={(e) => { e.preventDefault(); submit({ ...p, family: newFamily.trim() || p.family }); }}>
      <label className="field"><span>Full name</span>
        <input className="input" value={p.name} onChange={(e) => setP({ ...p, name: e.target.value })} required />
      </label>
      <div className="row2">
        <label className="field"><span>Category</span>
          <select className="input" value={p.gender} onChange={(e) => setP({ ...p, gender: e.target.value })}>
            {CATEGORIES.map((c) => <option key={c}>{c}</option>)}
          </select>
        </label>
        <div className="field"><span>Group</span>
          <div className="flex flex-wrap gap-3 pt-2">
            {GROUPS.map((g) => (
              <label key={g} className="check"><input type="checkbox" checked={p.groups.includes(g)}
                onChange={() => setP({ ...p, groups: toggle(p.groups, g) })} />{g}</label>
            ))}
          </div>
          <span className="msg hint">Leave empty for an adult publisher.</span>
        </div>
      </div>
      <div className="row2 rounded-xl border border-line p-3">
        <label className="field"><span>Family</span>
          <select className="input" value={p.family ?? NO_FAMILY} onChange={(e) => setP({ ...p, family: e.target.value === NO_FAMILY ? null : e.target.value })}>
            <option>{NO_FAMILY}</option>
            {families.map((f) => <option key={f}>{f}</option>)}
          </select>
        </label>
        <label className="field"><span>…or start a new family</span>
          <input className="input" placeholder="e.g. Mensah family" value={newFamily} onChange={(e) => setNewFamily(e.target.value)} />
        </label>
      </div>
      <div className="field"><span>Privileges</span>
        <div className="grid gap-x-4 gap-y-2 sm:grid-cols-2 lg:grid-cols-3">
          {PRIVILEGES.map((v) => (
            <label key={v} className="check"><input type="checkbox" checked={p.privileges.includes(v)}
              onChange={() => setP({ ...p, privileges: toggle(p.privileges, v) })} />{v}</label>
          ))}
        </div>
      </div>
      {withActive ? (
        <label className="check"><input type="checkbox" checked={p.active ?? true} onChange={(e) => setP({ ...p, active: e.target.checked })} />
          Active (shown when assigning parts)</label>
      ) : null}
      <button className="btn primary w-fit">{button}</button>
    </form>
  );
}

export function People({ people, families, tab, selected, last, used, away }: {
  people: Person[]; families: string[]; tab: string; selected: number;
  last: Record<number, string>; used: Record<number, number>; away: Record<number, string[]>;
}) {
  const router = useRouter();
  const path = usePathname();
  const [busy, act] = useAct();
  const [addKey, setAddKey] = useState(0);
  const go = (t: string, id?: number) => router.replace(`${path}?tab=${t}${id ? `&id=${id}` : ""}`);
  const tabs: [string, string][] = [["add", "Add"], ["edit", "Edit / deactivate"], ["list", "List"]];

  return (
    <>
      <nav className="tabs" aria-label="Sections">
        {tabs.map(([k, l]) => <button key={k} type="button" aria-current={tab === k ? "page" : undefined} onClick={() => go(k)}>{l}</button>)}
      </nav>
      {tab === "add" ? (
        <div className="card">
          <PersonForm key={addKey} families={families} button="Add participant"
            initial={{ name: "", gender: "Brother", privileges: [], groups: [], family: null }}
            submit={(p) => act(() => addPerson(p), () => { setAddKey((k) => k + 1); router.refresh(); })} />
        </div>
      ) : tab === "edit" ? (
        people.length ? <Edit key={selected} people={people} families={families} id={selected} used={used} away={away}
          pick={(id) => go("edit", id)} busy={busy} act={act} /> : <Note>No participants yet.</Note>
      ) : <List people={people} last={last} />}
    </>
  );
}

function Edit({ people, families, id, used, away, pick, busy, act }: {
  people: Person[]; families: string[]; id: number; used: Record<number, number>; away: Record<number, string[]>;
  pick: (id: number) => void; busy: boolean; act: ReturnType<typeof useAct>[1];
}) {
  const router = useRouter();
  const p = people.find((x) => x.id === id) ?? people[0];
  const [sus, setSus] = useState(suspendedNow(p));
  const [openEnded, setOpenEnded] = useState(!p.suspendedUntil);
  const [until, setUntil] = useState(p.suspendedUntil ?? addDays(today(), 90));
  const [clash, setClash] = useState<{ date: string; type: string; part: string }[]>([]);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [confirm, setConfirm] = useState(false);
  const refresh = () => router.refresh();

  useEffect(() => {
    if (!sus) { setClash([]); return; }
    let live = true;
    void upcomingFor(p.id, openEnded ? null : until).then((r) => { if (live) setClash(r); });
    return () => { live = false; };
  }, [sus, openEnded, until, p.id]);

  const status = suspendedNow(p) ? (p.suspendedUntil ? `Suspended until ${fmtDate(p.suspendedUntil)}` : "Suspended") : "";
  const awayDays = away[p.id] ?? [];
  return (
    <div className="stack">
      <label className="field max-w-md"><span>Participant</span>
        <select className="input" value={p.id} onChange={(e) => pick(Number(e.target.value))}>
          {people.map((x) => <option key={x.id} value={x.id}>{x.name}{x.active ? "" : " (inactive)"}</option>)}
        </select>
      </label>
      <div className="card">
        <PersonForm key={p.id} families={families} button="Save changes" withActive
          initial={{ name: p.name, gender: p.gender || "Brother", privileges: p.privileges, groups: p.groups, family: p.family, active: p.active }}
          submit={(x) => act(() => updatePerson(p.id, x), refresh)} />
      </div>

      <details className="card" open={Boolean(status)} key={`s${p.id}`}>
        <summary>Suspension</summary>
        <div className="form">
          {status ? <Note tone="warn">{status}</Note> : null}
          <label className="check"><input type="checkbox" checked={sus} onChange={(e) => setSus(e.target.checked)} /> Suspended (no parts or assisting)</label>
          {sus ? (
            <>
              <label className="check"><input type="checkbox" checked={openEnded} onChange={(e) => setOpenEnded(e.target.checked)} /> No end date</label>
              {!openEnded ? <label className="field max-w-xs"><span>Suspended until (inclusive)</span>
                <input className="input" type="date" value={until} onChange={(e) => setUntil(e.target.value)} /></label> : null}
              {clash.length ? <Note>Already scheduled in this period; reassign these: {clash.map((c) => `${fmtDate(c.date)} ${c.type.split(" ")[0].toLowerCase()}: ${c.part}`).join("; ")}</Note> : null}
            </>
          ) : null}
          <button type="button" className="btn w-fit" disabled={busy}
            onClick={() => act(() => setSuspension(p.id, sus, sus && !openEnded ? until : null), refresh)}>Save suspension</button>
        </div>
      </details>

      <details className="card" key={`a${p.id}`}>
        <summary>Away dates (dropped from those meetings)</summary>
        <div className="form">
          {awayDays.length ? <div className="text-sm">Currently away: {awaySummary(awayDays)}</div> : <div className="empty">No away dates.</div>}
          <div className="row2">
            <label className="field"><span>First day</span><input className="input" type="date" value={start} onChange={(e) => setStart(e.target.value)} /></label>
            <label className="field"><span>Last day</span><input className="input" type="date" value={end} min={start} onChange={(e) => setEnd(e.target.value)} /></label>
          </div>
          <div className="btns">
            <button type="button" className="btn" disabled={busy || !start}
              onClick={() => act(() => addAway(p.id, start, end || start), () => { setStart(""); setEnd(""); refresh(); })}>Add period</button>
            {awayDays.length ? <button type="button" className="btn danger" disabled={busy} onClick={() => act(() => clearAway(p.id), refresh)}>Clear all</button> : null}
          </div>
        </div>
      </details>

      <details className="card" key={`d${p.id}`}>
        <summary>Delete permanently</summary>
        {used[p.id] ? (
          <Note>{p.name} appears in {used[p.id]} saved assignment(s). Untick Active instead so the history stays intact.</Note>
        ) : <button type="button" className="btn danger" onClick={() => setConfirm(true)}>Delete participant</button>}
      </details>
      <Confirm open={confirm} busy={busy} onCancel={() => setConfirm(false)}
        message={`${p.name} will be removed for good. They have no saved assignments, so no schedule changes.`}
        onConfirm={() => act(() => deletePerson(p.id), () => { setConfirm(false); router.replace("/participants?tab=list"); router.refresh(); })} />
    </div>
  );
}

function List({ people, last }: { people: Person[]; last: Record<number, string> }) {
  const [show, setShow] = useState("Everyone");
  if (!people.length) return <Note>No participants yet.</Note>;
  const filters = ["Everyone", "Families", "Adults", ...GROUPS, "Suspended"];
  let rows = people;
  if (show === "Families") rows = rows.filter((p) => p.family);
  else if (show === "Adults") rows = rows.filter((p) => !p.groups.length);
  else if (show === "Suspended") rows = rows.filter(suspendedNow);
  else if ((GROUPS as readonly string[]).includes(show)) rows = rows.filter((p) => p.groups.includes(show));
  const status = (p: Person) => (!p.active ? "Inactive" : suspendedNow(p) ? (p.suspendedUntil ? `Suspended until ${fmtDate(p.suspendedUntil)}` : "Suspended") : "Active");
  const table = (list: Person[], family: boolean) => (
    <div className="table-wrap">
      <table className="table">
        <thead><tr><th>Name</th><th>Category</th><th>Group</th>{family ? <th>Family</th> : null}<th>Privileges</th><th>Last assignment</th><th>Status</th></tr></thead>
        <tbody>
          {list.map((p) => (
            <tr key={p.id}>
              <td className="whitespace-nowrap"><a href={`/participants?tab=edit&id=${p.id}`}>{p.name}</a></td>
              <td>{p.gender}</td><td>{p.groups.join(", ") || "Adult"}</td>{family ? <td>{p.family ?? ""}</td> : null}
              <td className="text-xs">{p.privileges.join(", ")}</td><td className="whitespace-nowrap">{last[p.id] ? fmtDate(last[p.id]) : ""}</td>
              <td className="whitespace-nowrap">{status(p)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
  const byFamily = new Map<string, Person[]>();
  if (show === "Families") for (const p of rows) byFamily.set(p.family!, [...(byFamily.get(p.family!) ?? []), p]);
  return (
    <div className="stack">
      <div className="flex flex-wrap gap-1.5">
        {filters.map((f) => <button key={f} type="button" className={`btn small ${show === f ? "primary" : ""}`} onClick={() => setShow(f)}>{f}</button>)}
      </div>
      {!rows.length ? <Note>Nobody in this group yet.</Note> : show === "Families" ? (
        [...byFamily.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([f, list]) => (
          <div key={f} className="card"><div className="mb-2 font-semibold">{f} · {list.length} member(s)</div>{table(list, false)}</div>
        ))
      ) : <div className="card"><div className="caption mt-0 mb-2">{rows.length} participant(s)</div>{table(rows, true)}</div>}
    </div>
  );
}
