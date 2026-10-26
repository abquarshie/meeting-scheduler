// Small building blocks shared by every page (server or client).
import Link from "next/link";
import type { ReactNode } from "react";
import { Icon, type IconName } from "./icons";

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

export function Stat({ label, value, icon, sub, tone }: {
  label: string; value: ReactNode; icon?: IconName; sub?: ReactNode; tone?: "bad" | "warn" | "ok";
}) {
  const color = tone === "bad" ? "text-bad" : tone === "warn" ? "text-warn" : tone === "ok" ? "text-ok" : "";
  return (
    <div className="stat">
      <div className="stat-top"><span>{label}</span>{icon ? <span className="stat-icon"><Icon name={icon} /></span> : null}</div>
      <div className={`stat-value ${color}`}>{value}</div>
      {sub ? <div className="stat-sub">{sub}</div> : null}
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
