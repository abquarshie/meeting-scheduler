/** Unicode NFC and trimmed, as utils.nfc. Ga names typed on different keyboards must compare equal. */
export function nfc(text: unknown): string {
  return String(text ?? "").normalize("NFC").trim();
}

const GA_SUBSTITUTES: Record<string, string> = { "3": "ɛ", ")": "ɔ" };

/** Typists use 3 ) N for ɛ ɔ ŋ when the keyboard lacks them (Admin → Settings switches this on), as
 * db.apply_ga_substitutes. A capital N only becomes ŋ between letters, so real initials survive. */
export function gaSubstitutes(text: string, on: boolean): string {
  if (!on) return text;
  const swapped = [...(text ?? "")].map((ch) => GA_SUBSTITUTES[ch] ?? ch).join("");
  return swapped.replace(/(?<=[A-Za-zɛɔŋ])N(?=[a-zɛɔŋ])/g, "ŋ");
}

export function talkLabel(number: string, title?: string | null): string {
  const n = nfc(number), t = nfc(title);
  return t ? `No. ${n} — ${t}` : `No. ${n}`;
}

/** "No. 12 — “Title”", or whichever part is filled in, as db.talk_text. */
export function talkText(meta: { talk_number?: string | null; talk_title?: string | null } | undefined): string {
  if (!meta) return "";
  const parts: string[] = [];
  if (meta.talk_number) parts.push(`No. ${meta.talk_number}`);
  if (meta.talk_title) parts.push(`“${meta.talk_title}”`);
  return parts.join(" — ");
}

/** CSV text with a BOM, so Excel keeps ɛ and ɔ right. */
export function toCSV(header: string[], rows: (string | number | null | undefined)[][]): string {
  const cell = (v: string | number | null | undefined) => {
    const s = v === null || v === undefined ? "" : String(v);
    return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  return "﻿" + [header, ...rows].map((r) => r.map(cell).join(",")).join("\r\n") + "\r\n";
}

/** Rows of a CSV file (quoted fields allowed), for the talk list import. */
export function parseCSV(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [], field = "", quoted = false;
  const src = text.replace(/^﻿/, "");
  for (let i = 0; i < src.length; i++) {
    const c = src[i];
    if (quoted) {
      if (c === '"' && src[i + 1] === '"') { field += '"'; i++; }
      else if (c === '"') quoted = false;
      else field += c;
    } else if (c === '"') quoted = true;
    else if (c === ",") { row.push(field); field = ""; }
    else if (c === "\n" || c === "\r") {
      if (c === "\r" && src[i + 1] === "\n") i++;
      row.push(field); rows.push(row); row = []; field = "";
    } else field += c;
  }
  if (field || row.length) { row.push(field); rows.push(row); }
  return rows.filter((r) => r.some((f) => f.trim()));
}
