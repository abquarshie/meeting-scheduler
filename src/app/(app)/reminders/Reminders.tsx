"use client";
import { useState } from "react";
import { saveCalendarTimes } from "@/actions/settings";
import { Icon } from "@/components/icons";
import { useToast } from "@/components/Toaster";
import { useAct } from "@/components/useAct";

export type Card = { id: number; name: string; wa: string; text: string; lines: string[]; cal: string };

export function ReminderList({ cards }: { cards: Card[] }) {
  const toast = useToast();
  const [sent, setSent] = useState<Set<number>>(new Set());
  const copy = async (text: string, what: string) => {
    try {
      await navigator.clipboard.writeText(text);
      toast(`${what} copied`);
    } catch {
      toast("Couldn't copy here. Long-press to select the text instead.", { tone: "warn" });
    }
  };
  return (
    <div className="grid gap-3 md:grid-cols-2">
      {cards.map((c) => (
        <div key={c.id} className={`card ${sent.has(c.id) ? "opacity-60" : ""}`}>
          <div className="card-head">
            <h2>{c.name}</h2>
          </div>
          <ul className="mt-0 mb-3 grid gap-1 pl-4 text-sm">{c.lines.map((l, i) => <li key={i}>{l}</li>)}</ul>
          <div className="flex flex-wrap gap-2">
            <a className="btn primary" href={c.wa} target="_blank" rel="noopener noreferrer"
              onClick={() => setSent((s) => new Set(s).add(c.id))}>
              <Icon name="check" />WhatsApp
            </a>
            <button type="button" className="btn" onClick={() => copy(c.text, "Message")}><Icon name="copy" />Copy</button>
            {c.cal ? <>
            <button type="button" className="btn" onClick={() => copy(`${window.location.origin}${c.cal}`, "Calendar link")}>
              <Icon name="calendar" />Calendar link
            </button>
            {/* webcal:// makes an iPhone offer "Subscribe" instead of adding the parts once */}
            <button type="button" className="btn" onClick={() => copy(`webcal://${window.location.host}${c.cal}`, "iPhone calendar link")}>
              <Icon name="calendar" />iPhone link
            </button>
            </> : null}
          </div>
        </div>
      ))}
    </div>
  );
}

export function CalendarTimes({ midweek, weekend }: { midweek: string; weekend: string }) {
  const [m, setM] = useState(midweek);
  const [w, setW] = useState(weekend);
  const [busy, act] = useAct();
  return (
    <form className="form" onSubmit={(e) => { e.preventDefault(); act(() => saveCalendarTimes(m, w)); }}>
      <div className="row2">
        <label className="field"><span>Midweek meeting starts</span><input className="input" value={m} onChange={(e) => setM(e.target.value)} placeholder="e.g. 18:30" /></label>
        <label className="field"><span>Weekend meeting starts</span><input className="input" value={w} onChange={(e) => setW(e.target.value)} placeholder="e.g. 9:00am" /></label>
      </div>
      <button className="btn w-fit" disabled={busy}>Save times</button>
    </form>
  );
}
