// Small building blocks shared by every page (server or client).
import Link from "next/link";
import type { ReactNode } from "react";

export function PageHead({ title, sub, children }: { title: string; sub?: string; children?: ReactNode }) {
  return (
    <div className="page-head flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="page-title">{title}</h1>
        {sub ? <div className="page-sub">{sub}</div> : null}
      </div>
      {children}
    </div>
  );
}

export type Tone = "ok" | "bad" | "warn" | "accent" | "neutral";
export function Pill({ tone = "neutral", children }: { tone?: Tone; children: ReactNode }) {
  return <span className={`pill ${tone}`}>{children}</span>;
}

export function Note({ tone, children }: { tone?: "warn" | "error" | "ok"; children: ReactNode }) {
  return <div className={`note ${tone ?? ""}`}>{children}</div>;
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="empty">{children}</div>;
}

export function Bar({ pct, color, label }: { pct: number; color?: string; label: string }) {
  const p = Math.max(0, Math.min(100, Math.round(pct)));
  return (
    <div className="bar" role="progressbar" aria-label={label} aria-valuenow={p} aria-valuemin={0} aria-valuemax={100}>
      <div className="fill" style={{ width: `${p}%`, ...(color ? { background: color } : {}) }} />
    </div>
  );
}

export function Stat({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="min-w-0 rounded-2xl border border-line bg-surface p-3.5 shadow-soft md:p-4">
      <div className="num text-2xl font-bold tracking-tight">{value}</div>
      <div className="mt-0.5 text-xs font-medium text-muted">{label}</div>
    </div>
  );
}

export function Tabs({ tabs, current }: { tabs: { href: string; label: string }[]; current: string }) {
  return (
    <nav className="tabs" aria-label="Sections">
      {tabs.map((t) => (
        <Link key={t.href} href={t.href} aria-current={t.href === current ? "page" : undefined}>{t.label}</Link>
      ))}
    </nav>
  );
}
