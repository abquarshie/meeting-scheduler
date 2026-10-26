"use client";
import { useState } from "react";
import { setLanguage } from "@/actions/settings";
import { LANGUAGES } from "@/lib/constants";
import { useAct } from "./useAct";

/** The slip language: for slips, schedule sheets, the S-140 and the messages. Saved as everyone's default. */
export function LanguagePick({ value }: { value: string }) {
  const [busy, act] = useAct();
  const [lang, setLang] = useState(value);
  return (
    <label className="field">
      <span className="eyebrow px-1">Slip language</span>
      <select className="input" value={lang} disabled={busy}
        onChange={(e) => { const v = e.target.value; setLang(v); act(() => setLanguage(v)); }}>
        {LANGUAGES.map((l) => <option key={l}>{l}</option>)}
      </select>
    </label>
  );
}
