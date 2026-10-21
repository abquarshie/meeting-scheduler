"use client";
import { usePathname, useRouter } from "next/navigation";

/** A month dropdown that keeps the choice in the address (?m=2026-10), so refresh and back work. */
export function MonthPick({ months, value, param = "m" }: { months: { value: string; label: string }[]; value: string; param?: string }) {
  const router = useRouter();
  const path = usePathname();
  return (
    <select className="input w-auto" aria-label="Month" value={value}
      onChange={(e) => router.replace(`${path}?${param}=${e.target.value}`)}>
      {months.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
    </select>
  );
}
