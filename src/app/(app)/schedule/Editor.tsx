"use client";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Icon } from "@/components/icons";
import { py } from "@/components/py";
import { Confirm } from "@/components/Sheet";
import { Bar, Note } from "@/components/ui";
import { useAct } from "@/components/useAct";
import { CATEGORIES, MEETING_TYPES, MIDWEEK, SECTION_COLORS, SECTION_TITLES } from "@/lib/constants";
import { fmtDate } from "@/lib/dates";
import { talkLabel } from "@/lib/text";

type Slot = {
  hall: string; allow_visitor: boolean; part_no: number | null; title: string; role: string; section: string;
  minutes: number | null; student_part: boolean; needs_assistant: boolean;
};
type Pick = { sid: number | null; aid: number | null; visitor: string; cong: string; isVisitor: boolean };
type Issue = { level: "error" | "warning"; slots: number[]; text: string };
type Meta = Record<"heading" | "book" | "opening_song" | "middle_song" | "closing_song" | "aux_group" | "talk_number" | "talk_title", string>;
type PersonInfo = { name: string; gender: string; family: string | null; active: boolean };
type EditorData = {
  weekLabel: string; relative: string; event: string | null; eventGa?: string;
  saved: boolean; slots: Slot[]; slotLabels: string[]; picks: Pick[]; meta: Meta; aux: boolean; symposium: boolean;
  workbook: null | {
    weeks: { label: string; dates: string }[]; matched: string | null; differs: boolean; use: boolean;
    week: string | null; savedCount: number; workbookCount: number;
    parts: { "No.": number | null; Title: string; Min: number | string; Section: string }[]; gaps: number[]; text: string;
  };
  people: Record<string, PersonInfo>;
  options: { ids: number[]; labels: Record<string, string>; eligible: number[]; mixed: boolean }[];
  assistantOrder: number[]; assistantLabels: Record<string, string>; unavailable: string[];
  snapshot: { note: string; reason: string } | null; issues: Issue[];
  talks: { number: string; title: string }[]; activeCount: number;
};
type Choices = { aux?: boolean; symposium?: boolean; useWorkbook?: boolean; week?: string | null };

const slotKey = (s: Slot) => `${s.hall}|${s.role}|${s.part_no ?? s.title.toLowerCase()}`;

function sameFamily(people: Record<string, PersonInfo>, a: number | null, b: number | null) {
  if (a === null || b === null) return false;
  const fa = people[a]?.family;
  return Boolean(fa) && fa === people[b]?.family;
}

export function Editor({ date, type, mode, saved }: {
  date: string; type: string; mode: "new" | "edit"; saved: { date: string; type: string }[];
}) {
  const router = useRouter();
  const [busy, act] = useAct();
  const [data, setData] = useState<EditorData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [picks, setPicks] = useState<Pick[]>([]);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [issues, setIssues] = useState<Issue[]>([]);
  const [categories, setCategories] = useState<Record<number, string>>({});
  const [confirm, setConfirm] = useState<null | "undo" | "delete">(null);
  const [choices, setChoices] = useState<Choices>({});
  const touched = useRef(false); // picks changed since the last load: carry them over when the parts list changes

  const go = (d: string, t: string, m = mode) => {
    const q = new URLSearchParams({ date: d, type: t });
    if (m === "edit") q.set("mode", "edit");
    router.replace(`/schedule?${q.toString()}`);
  };

  const load = useCallback(async (next: Choices, carry?: { slots: Slot[]; picks: Pick[] }) => {
    const r = await py<EditorData>("editor", { date, type, ...next });
    if (!r.ok) { setError(r.error); return; }
    setError(null);
    let p = r.picks;
    if (carry) {
      const old = new Map(carry.slots.map((s, i) => [slotKey(s), carry.picks[i]]));
      p = r.slots.map((s, i) => old.get(slotKey(s)) ?? r.picks[i]);
    }
    setData(r);
    setPicks(p);
    setMeta((m) => (carry && m ? { ...r.meta, ...m } : r.meta));
    setIssues(r.issues);
  }, [date, type]);

  useEffect(() => { void load({}); }, [load]);

  const change = (next: Choices) => {
    const merged = { ...choices, ...next };
    setChoices(merged);
    void load(merged, data && touched.current ? { slots: data.slots, picks } : undefined);
  };

  // the checks, re-run shortly after every change so a clash shows the moment it is made
  const checkSeq = useRef(0);
  useEffect(() => {
    if (!data || data.event || !touched.current) return;
    const seq = ++checkSeq.current;
    const t = setTimeout(async () => {
      const r = await py<{ issues: Issue[] }>("check", { date, type, slots: data.slots, picks, symposium: data.symposium });
      if (r.ok && seq === checkSeq.current) setIssues(r.issues);
    }, 350);
    return () => clearTimeout(t);
  }, [picks, data, date, type]);

  const setPick = (i: number, patch: Partial<Pick>) => {
    touched.current = true;
    setPicks((ps) => ps.map((p, j) => (j === i ? { ...p, ...patch } : p)));
  };

  const issuesAt = useMemo(() => {
    const m = new Map<number, Issue[]>();
    for (const x of issues) for (const i of x.slots) m.set(i, [...(m.get(i) ?? []), x]);
    return m;
  }, [issues]);

  const header = (
    <div className="card mb-4 grid gap-3">
      <div className="seg w-fit" role="group" aria-label="Mode">
        <button type="button" aria-pressed={mode === "new"} onClick={() => go(date, type, "new")}>Create new</button>
        <button type="button" aria-pressed={mode === "edit"} onClick={() => go(saved[0]?.date ?? date, saved[0]?.type ?? type, "edit")}>Edit saved</button>
      </div>
      {mode === "edit" ? (
        saved.length ? (
          <label className="field"><span>Saved schedule</span>
            <select className="input" value={`${date}|${type}`} onChange={(e) => { const [d, t] = e.target.value.split("|"); go(d, t); }}>
              {!saved.some((m) => m.date === date && m.type === type) ? <option value={`${date}|${type}`}>{fmtDate(date)} · {type}</option> : null}
              {saved.map((m) => <option key={`${m.date}|${m.type}`} value={`${m.date}|${m.type}`}>{fmtDate(m.date)} · {m.type}</option>)}
            </select>
          </label>
        ) : <Note>No saved schedules yet.</Note>
      ) : (
        <div className="row2">
          <label className="field"><span>Meeting type</span>
            <select className="input" value={type} onChange={(e) => go(date, e.target.value)}>
              {MEETING_TYPES.map((t) => <option key={t}>{t}</option>)}
            </select>
          </label>
          <label className="field"><span>Meeting date</span>
            <input className="input" type="date" value={date} onChange={(e) => e.target.value && go(e.target.value, type)} />
          </label>
        </div>
      )}
      {data ? (
        <div className="text-sm text-muted">
          <b className="text-ink">{data.weekLabel}</b>{data.relative ? ` · ${data.relative}` : ""}
        </div>
      ) : null}
    </div>
  );

  if (error) return <>{header}<Note tone="error">{error}</Note></>;
  if (!data || !meta) return <>{header}<div className="empty">Loading…</div></>;
  if (data.event) {
    return (
      <>
        {header}
        <div className="card">
          <h2 className="mt-0 text-lg font-bold">{data.event}</h2>
          <div className="text-sm text-muted">In Ga: {data.eventGa}</div>
          <p>This week is marked as an assembly or convention week, so there is no midweek or weekend meeting to schedule.</p>
          <div className="caption">To schedule it after all, remove the mark under Admin → Settings → Assemblies &amp; conventions.
            A meeting cleared when the week was marked can then be brought back with Undo on this page.</div>
        </div>
      </>
    );
  }
  if (data.activeCount === 0) return <>{header}<Note tone="warn">Add participants on the Participants page first.</Note></>;

  const { slots, people, options, symposium } = data;
  const visitorOk = (s: Slot) => s.allow_visitor && !(symposium && s.role === "Public Talk");
  const talkSlots = slots.map((s, i) => (s.role === "Public Talk" ? i : -1)).filter((i) => i >= 0);
  const lastTalk = talkSlots.length ? talkSlots[talkSlots.length - 1] : -1;

  // progress: a part plus its assistant where one is needed (utils.fill_progress)
  let needed = 0, filled = 0;
  slots.forEach((s, i) => {
    const p = picks[i];
    needed += 1 + (s.needs_assistant ? 1 : 0);
    filled += (visitorOk(s) && p.isVisitor ? (p.visitor.trim() ? 1 : 0) : (p.sid !== null ? 1 : 0))
      + (s.needs_assistant && !(visitorOk(s) && p.isVisitor) && p.aid !== null ? 1 : 0);
  });
  const errors = issues.filter((x) => x.level === "error");
  const warnings = issues.filter((x) => x.level === "warning");

  const suggest = () => act(async () => {
    const r = await py<{ picks: Record<string, [number | null, number | null]> }>("suggest", { date, type, slots, picks });
    if (!r.ok) return r;
    touched.current = true;
    setPicks((ps) => ps.map((p, i) => {
      const s = r.picks[String(i)];
      if (!s || p.sid !== null || (visitorOk(slots[i]) && p.isVisitor)) return p;
      return { ...p, sid: s[0], aid: slots[i].needs_assistant ? s[1] : null };
    }));
    return { ok: true, message: "Suggestions filled in. Check them, then save." };
  });

  const save = () => act(async () => {
    const r = await py("save", { date, type, slots, picks, symposium, aux: data.aux, meta });
    if (r.ok) {
      touched.current = false;
      setChoices({});
      await load({});
      router.refresh();
    }
    return r;
  });

  const doConfirm = () => act(async () => {
    const r = await py(confirm === "undo" ? "undo" : "delete", { date, type });
    setConfirm(null);
    if (r.ok) {
      touched.current = false;
      setChoices({});
      await load({});
      router.refresh();
    }
    return r;
  });

  const talkInputs = () => {
    const known = data.talks.find((t) => t.number === meta.talk_number.trim());
    const typing = !known && (meta.talk_number || meta.talk_title || !data.talks.length);
    return (
      <div className="mt-2 grid gap-2 rounded-xl border border-line p-3">
        <div className="text-sm font-semibold">Public talk</div>
        {data.talks.length ? (
          <select className="input" value={known ? known.number : typing ? "__type" : ""}
            onChange={(e) => {
              const v = e.target.value;
              if (v === "__type" || v === "") setMeta({ ...meta, talk_number: "", talk_title: "" });
              else setMeta({ ...meta, talk_number: v, talk_title: data.talks.find((t) => t.number === v)?.title ?? "" });
            }}>
            <option value="">— Choose a talk —</option>
            {data.talks.map((t) => <option key={t.number} value={t.number}>{talkLabel(t.number, t.title)}</option>)}
            <option value="__type">Not in the list (type it in)</option>
          </select>
        ) : <div className="caption mt-0">No talks stored yet. Add them under Public talks → Talk list and they appear here.</div>}
        {!known ? (
          <div className="grid gap-2 sm:grid-cols-[110px_minmax(0,1fr)]">
            <input className="input" placeholder="Talk no." value={meta.talk_number}
              onChange={(e) => setMeta({ ...meta, talk_number: e.target.value })} aria-label="Talk number" />
            <input className="input" placeholder="Title of the public talk" value={meta.talk_title}
              onChange={(e) => setMeta({ ...meta, talk_title: e.target.value })} aria-label="Talk title" />
          </div>
        ) : null}
      </div>
    );
  };

  const renderSlot = (i: number) => {
    const s = slots[i], p = picks[i], opt = options[i];
    const label = data.slotLabels[i];
    const notes = (issuesAt.get(i) ?? []).map((x, k) => <div key={k} className={`slot-issue ${x.level}`}>⚠ {x.text}</div>);
    if (visitorOk(s)) {
      const visitorBox = (
        <label className="check">
          <input type="checkbox" checked={p.isVisitor} onChange={(e) => setPick(i, { isVisitor: e.target.checked })} />
          Visiting speaker (another congregation)
        </label>
      );
      if (p.isVisitor) {
        return (
          <div className="slot" key={i}>
            <div className="slot-title">{label}</div>
            {visitorBox}
            <div className="grid gap-2 sm:grid-cols-[3fr_2fr]">
              <input className="input" placeholder="Speaker's name, e.g. Jonathan Adjei" value={p.visitor}
                onChange={(e) => setPick(i, { visitor: e.target.value })} aria-label="Speaker's name" />
              {s.role === "Public Talk" ? (
                <input className="input" placeholder="His congregation" value={p.cong}
                  onChange={(e) => setPick(i, { cong: e.target.value })} aria-label="His congregation" />
              ) : null}
            </div>
            {notes}
            {i === lastTalk ? talkInputs() : null}
          </div>
        );
      }
      return (
        <div className="slot" key={i}>
          <div className="slot-title">{label}</div>
          {visitorBox}
          {personSelect(i, s, p, opt)}
          {notes}
          {i === lastTalk ? talkInputs() : null}
        </div>
      );
    }
    return (
      <div className="slot" key={i}>
        {s.needs_assistant ? (
          <div className="grid gap-x-3 sm:grid-cols-2">
            <div className="slot-title">{label}</div>
            <div className="slot-title max-sm:hidden">Assistant</div>
          </div>
        ) : <div className="slot-title">{label}</div>}
        {personSelect(i, s, p, opt)}
        {notes}
        {i === lastTalk ? talkInputs() : null}
      </div>
    );
  };

  function personSelect(i: number, s: Slot, p: Pick, opt: EditorData["options"][number]) {
    let ids = opt.ids;
    let category: string | null = null;
    if (opt.mixed) {
      category = categories[i] ?? (p.sid !== null ? people[p.sid]?.gender : null) ?? CATEGORIES[1];
      ids = ids.filter((id) => people[id]?.gender === category || id === p.sid);
    }
    const gone = p.sid !== null && !opt.eligible.includes(p.sid);
    const main = (
      <div className="grid gap-1.5">
        {opt.mixed ? (
          <div className="seg w-fit" role="group" aria-label="Category">
            {CATEGORIES.map((c) => (
              <button key={c} type="button" aria-pressed={category === c}
                onClick={() => setCategories((x) => ({ ...x, [i]: c }))}>{c}</button>
            ))}
          </div>
        ) : null}
        <select className="input" aria-label={data!.slotLabels[i]} value={p.sid ?? ""}
          onChange={(e) => setPick(i, { sid: e.target.value ? Number(e.target.value) : null })}>
          <option value="">— Unassigned —</option>
          {ids.map((id) => <option key={id} value={id}>{opt.labels[id] ?? people[id]?.name}</option>)}
        </select>
        {gone ? <div className="msg hint">{people[p.sid!]?.name ?? "This person"} is no longer available. Choose someone else.</div> : null}
      </div>
    );
    if (!s.needs_assistant) return main;
    // the assistant: same category or family as the student (a parent can assist their child), family first
    let pool = data!.assistantOrder.filter((id) => id !== p.sid && (p.sid === null
      || people[id]?.gender === people[p.sid]?.gender || sameFamily(people, id, p.sid)));
    if (p.aid !== null && !pool.includes(p.aid)) pool = [...pool, p.aid];
    pool = [...pool].sort((a, b) => Number(!sameFamily(people, a, p.sid)) - Number(!sameFamily(people, b, p.sid)));
    return (
      <div className="grid gap-x-3 gap-y-1.5 sm:grid-cols-2">
        {main}
        <div className="grid gap-1.5 self-end">
          <span className="slot-title sm:hidden">Assistant</span>
          <select className="input" aria-label={`Assistant for ${data!.slotLabels[i]}`} value={p.aid ?? ""}
            onChange={(e) => setPick(i, { aid: e.target.value ? Number(e.target.value) : null })}>
            <option value="">— Unassigned —</option>
            {pool.map((id) => <option key={id} value={id}>{data!.assistantLabels[id] ?? people[id]?.name}</option>)}
          </select>
        </div>
      </div>
    );
  }

  // one block per workbook section; single parts sit two to a row
  const groups: { section: string; items: number[] }[] = [];
  slots.forEach((s, i) => {
    if (!groups.length || groups[groups.length - 1].section !== s.section) groups.push({ section: s.section, items: [] });
    groups[groups.length - 1].items.push(i);
  });
  const wide = (s: Slot) => s.needs_assistant || s.allow_visitor || s.role === "Public Talk";

  const wbk = data.workbook;
  return (
    <>
      {header}
      <div className="stack">
        {mode === "new" && data.saved ? <Note>A schedule is already saved for this date. It&apos;s loaded below, and saving will replace it.</Note> : null}

        {type === MIDWEEK ? (
          <div className="card grid gap-3">
            {wbk ? (
              <>
                {!wbk.matched ? <Note tone="warn">No workbook week covers {fmtDate(date)}. Check the week dates on the Workbook PDF page, or pick the week yourself below.</Note> : null}
                {wbk.differs ? <Note tone="warn">The saved schedule has {wbk.savedCount} numbered part(s), but the workbook week <b>{wbk.matched}</b> has {wbk.workbookCount}, or the titles differ. Tick the box below to switch to the workbook parts; names carry over where the part number and role match.</Note> : null}
                <label className="check">
                  <input type="checkbox" checked={wbk.use} onChange={(e) => change({ useWorkbook: e.target.checked })} />
                  Use parts from the uploaded workbook
                </label>
                {wbk.use ? (
                  <label className="field"><span>Workbook week</span>
                    <select className="input" value={wbk.week ?? ""} onChange={(e) => change({ week: e.target.value || null })}>
                      {!wbk.week ? <option value="">Choose the workbook week</option> : null}
                      {wbk.weeks.map((w) => <option key={w.label} value={w.label}>{w.label} · {w.dates}</option>)}
                    </select>
                  </label>
                ) : null}
                {wbk.week ? (
                  <details className="rounded-xl border border-line px-3 py-2" open={wbk.differs}>
                    <summary className="cursor-pointer text-sm font-semibold">Cross-check with the workbook: {wbk.week} ({wbk.parts.length} parts)</summary>
                    {wbk.gaps.length ? <Note tone="error">Part number(s) not found in the workbook text: {wbk.gaps.join(", ")}. Add them on the Workbook PDF page, under Review and correct a week.</Note> : null}
                    <div className="table-wrap mt-2">
                      <table className="table">
                        <thead><tr><th>No.</th><th>Title</th><th>Min</th><th>Section</th></tr></thead>
                        <tbody>{wbk.parts.map((r, k) => <tr key={k}><td>{r["No."]}</td><td>{r.Title}</td><td>{r.Min}</td><td>{r.Section}</td></tr>)}</tbody>
                      </table>
                    </div>
                    {wbk.text ? <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap rounded-lg bg-subtle p-2 text-xs">{wbk.text}</pre> : null}
                  </details>
                ) : null}
              </>
            ) : <div className="caption mt-0">Using the standard 8-part list. Upload the workbook PDF to get this week&apos;s real part numbers and titles.</div>}
            <label className="check">
              <input type="checkbox" checked={data.aux} onChange={(e) => change({ aux: e.target.checked })} />
              Auxiliary classroom this week
            </label>
            {data.aux ? (
              <label className="field max-w-xs"><span>Group using the auxiliary classroom</span>
                <input className="input" placeholder="e.g. 1" value={meta.aux_group} onChange={(e) => setMeta({ ...meta, aux_group: e.target.value })} />
              </label>
            ) : null}
          </div>
        ) : (
          <div className="card grid gap-2">
            <label className="check">
              <input type="checkbox" checked={symposium} onChange={(e) => change({ symposium: e.target.checked })} />
              Symposium: one talk shared by two speakers
            </label>
            {symposium ? <div className="caption mt-0">Both speakers are brothers from the congregation. Guest speakers don&apos;t give symposiums.</div> : null}
          </div>
        )}

        <div className="flex flex-wrap items-center justify-between gap-2">
          {data.unavailable.length ? (
            <details className="text-sm">
              <summary className="cursor-pointer font-semibold text-muted">{data.unavailable.length} not available this week</summary>
              <div className="mt-1">{data.unavailable.join(", ")}</div>
              <div className="caption">Away, going out to speak elsewhere, suspended or inactive. They are left out of the lists below.</div>
            </details>
          ) : <span />}
          <button type="button" className="btn" onClick={suggest} disabled={busy}
            title="Fills only the empty slots. Anyone already chosen stays, and is not suggested anywhere else.">
            <Icon name="sparkle" /> Suggest
          </button>
        </div>

        <details className="card">
          <summary>Meeting details (used on the S-140)</summary>
          <div className="row2">
            {([["heading", "Heading"], ["book", "Bible reading"], ["opening_song", "Opening song"], ["middle_song", "Middle song"],
              ["closing_song", "Closing song"]] as const).map(([k, l]) => (
              <label key={k} className="field"><span>{l}</span>
                <input className="input" value={meta[k]} onChange={(e) => setMeta({ ...meta, [k]: e.target.value })} />
              </label>
            ))}
          </div>
        </details>

        {groups.map((g, gi) => {
          const rows: number[][] = [];
          let pending: number[] | null = null;
          for (const i of g.items) {
            if (wide(slots[i])) { pending = null; rows.push([i]); continue; }
            if (pending) { pending.push(i); pending = null; } else { pending = [i]; rows.push(pending); }
          }
          return (
            <section key={gi}>
              <div className="section-head"><span className="swatch" style={{ background: SECTION_COLORS[g.section] ?? "#8A94A0" }} />{SECTION_TITLES[g.section] ?? g.section}</div>
              <div className="card grid gap-4">
                {rows.map((r, k) => (
                  <div key={k} className={r.length > 1 ? "grid gap-4 sm:grid-cols-2" : "grid"}>{r.map(renderSlot)}</div>
                ))}
              </div>
            </section>
          );
        })}

        {issues.length ? (
          <div className="card grid gap-2">
            <div className="font-semibold">Checks · {issues.length} to look at</div>
            {errors.map((x, k) => <Note key={`e${k}`} tone="error">{x.text}</Note>)}
            {warnings.map((x, k) => <Note key={`w${k}`} tone="warn">{x.text}</Note>)}
            {errors.length ? <div className="caption mt-0">Saving is blocked until the red items are fixed.</div> : null}
          </div>
        ) : null}

        <div className="card savebar">
          <div className="min-w-48 flex-1">
            <div className="mb-1 text-sm font-semibold">{needed - filled ? `${filled} of ${needed} filled, ${needed - filled} still open` : `All ${needed} filled`}</div>
            <Bar pct={needed ? (100 * filled) / needed : 100} label="Filled" />
          </div>
          <div className="btns max-sm:w-full max-sm:flex-nowrap">
            <button type="button" className="btn primary max-sm:flex-1" onClick={save} disabled={busy || errors.length > 0}><Icon name="save" /> Save schedule</button>
            {data.snapshot ? <button type="button" className="btn" onClick={() => setConfirm("undo")} disabled={busy}><Icon name="undo" /><span className="max-sm:sr-only">Undo</span></button> : null}
            {data.saved ? <button type="button" className="btn danger" onClick={() => setConfirm("delete")} disabled={busy}><Icon name="trash" /><span className="max-sm:sr-only">Delete</span></button> : null}
          </div>
        </div>
      </div>
      <Confirm open={confirm !== null} busy={busy} onCancel={() => setConfirm(null)} onConfirm={doConfirm}
        button={confirm === "undo" ? "Undo" : "Delete"}
        message={confirm === "undo"
          ? `This puts back ${data.snapshot?.note}, replacing what is saved now for the ${type.toLowerCase()} on ${fmtDate(date)}. Undo can itself be undone.`
          : `The ${type.toLowerCase()} on ${fmtDate(date)} and everyone assigned to it will be removed. Undo on this page can bring it back.`} />
    </>
  );
}
