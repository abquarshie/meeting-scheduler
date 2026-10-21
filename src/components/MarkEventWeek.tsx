"use client";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { EVENT_KINDS, EVENT_NAMES, EVENT_TEXT } from "@/lib/constants";
import { today } from "@/lib/dates";
import { py, pyGet } from "./py";
import { useAct } from "./useAct";

type Preview = { label: string; saved: { date: string; type: string; text: string }[] };

/** Mark a week as a circuit assembly or convention week. Any day in the week will do. Meetings already saved that
 * week are listed, and cleared only once that is ticked (each can be brought back with Undo). */
export function MarkEventWeek({ defaultDay }: { defaultDay?: string }) {
  const router = useRouter();
  const [busy, act] = useAct();
  const [day, setDay] = useState(defaultDay ?? today());
  const [kind, setKind] = useState<string>("assembly");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [sure, setSure] = useState(false);

  useEffect(() => {
    let live = true;
    setSure(false);
    void pyGet<Preview>("week_preview", { day }).then((r) => { if (live && r.ok) setPreview(r); });
    return () => { live = false; };
  }, [day]);

  const saved = preview?.saved ?? [];
  return (
    <div className="grid gap-3">
      <div className="row2">
        <label className="field"><span>Any day in the week</span>
          <input className="input" type="date" value={day} onChange={(e) => e.target.value && setDay(e.target.value)} />
        </label>
        <div className="field"><span>Kind of week</span>
          <div className="seg w-fit" role="group">
            {EVENT_KINDS.map((k) => <button key={k} type="button" aria-pressed={kind === k} onClick={() => setKind(k)}>{EVENT_NAMES[k]}</button>)}
          </div>
        </div>
      </div>
      {preview ? <div className="text-sm"><b>{preview.label}</b> will show <b>{EVENT_TEXT[kind].en}</b> (in Ga: {EVENT_TEXT[kind].ga})</div> : null}
      {saved.length ? (
        <>
          <div className="note warn">Already saved that week: {saved.map((m) => m.text).join(", ")}. Marking the week clears them.</div>
          <label className="check"><input type="checkbox" checked={sure} onChange={(e) => setSure(e.target.checked)} />
            Clear them (to bring one back later, remove the mark, then use Undo on Create or edit)</label>
        </>
      ) : null}
      <button type="button" className="btn primary w-fit" disabled={busy || (saved.length > 0 && !sure)}
        onClick={() => act(() => py("mark_event", { day, kind }), () => router.refresh())}>
        Mark as {EVENT_NAMES[kind]} week
      </button>
    </div>
  );
}
