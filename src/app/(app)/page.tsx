import Link from "next/link";
import { Icon } from "@/components/icons";
import { Bar, Stat } from "@/components/ui";
import { getUser } from "@/lib/auth";
import { BACKUP_REMINDER_DAYS, LANGUAGES, MIDWEEK, SECTION_COLORS, SECTION_TITLES } from "@/lib/constants";
import {
  awayBetween, fillCounts, getEvents, getMetas, getPeople, getRows, getSettings, getWorkbook, isSuspended, key,
  meetingRows, savedMeetings, setting, templateNames, workbookStatus,
} from "@/lib/data";
import { addDays, daysAway, daysBetween, longDate, shortDay, today } from "@/lib/dates";
import { prisma } from "@/lib/db";
import { talkText } from "@/lib/text";

const editHref = (date: string, type: string) =>
  `/schedule?${new URLSearchParams({ date, type, mode: "edit" }).toString()}`;
const createHref = (date: string) => `/schedule?${new URLSearchParams({ date, type: MIDWEEK }).toString()}`;

function greeting(name: string | null) {
  const hour = new Date().getUTCHours(); // Ghana is on UTC
  const word = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
  return name ? `${word}, ${name}` : word;
}

export default async function Home() {
  const now = today();
  // only this week onwards: everything below is about what is coming up
  const [user, people, rows, metas, settings, workbook, events, templates, anySaved] = await Promise.all([
    getUser(), getPeople(), getRows({ from: addDays(now, -7) }), getMetas(), getSettings(), getWorkbook(), getEvents(),
    templateNames(), prisma.schedules.findFirst({ select: { id: true } }),
  ]);

  // what a new installation still needs before it can print
  const gaps: [string, string][] = [];
  if (!people.length) gaps.push(["Add your participants", "/participants"]);
  if (!setting(settings, "congregation")) gaps.push(["Set the congregation name; it heads every schedule sheet", "/admin?tab=settings"]);
  if (!workbook.weeks.length) gaps.push(["Upload the meeting workbook so weeks get their real parts", "/workbook"]);
  if (!LANGUAGES.some((l) => templates.has(`s89_${l}`))) gaps.push(["Upload the blank S-89; slips are printed on it", "/admin"]);
  if (!LANGUAGES.some((l) => templates.has(`s140_${l}`))) gaps.push(["Upload the blank S-140 template for the monthly export", "/admin"]);

  const upcoming = savedMeetings(rows).filter((m) => m.date >= now).sort((a, b) => a.date.localeCompare(b.date) || a.type.localeCompare(b.type));
  const toCreate = workbookStatus(workbook.weeks, rows, settings, events)
    .filter((w) => w.status === "to create" && w.meeting >= now).sort((a, b) => a.meeting.localeCompare(b.meeting));
  const gap = toCreate[0];

  const soon = upcoming.filter((m) => m.date <= addDays(now, 28));
  const openSoon = soon.reduce((n, m) => { const c = fillCounts(meetingRows(rows, m.date, m.type)); return n + c.needed - c.filled; }, 0);
  const notCreated = toCreate.filter((w) => w.meeting <= addDays(now, 28));
  const away = await awayBetween(now, addDays(now, 6));
  for (const p of people) if (isSuspended(p, now)) away.add(p.id);
  const lastExport = setting(settings, "last_export");
  const backupDays = lastExport ? daysBetween(lastExport, now) : null;

  const next = upcoming[0];
  // everything that wants a hand, newest worry first: setup gaps, a week not created, the backup
  const attention: { text: string; href: string; tone: "warn" | "bad" | "accent"; icon: "warning" | "calendar" | "shield" | "add" }[] = [];
  if (next && gap) attention.push({ text: `${gap.label} (${longDate(gap.meeting)}) has no schedule yet`, href: createHref(gap.meeting), tone: "warn", icon: "calendar" });
  if (anySaved && (backupDays === null || backupDays >= BACKUP_REMINDER_DAYS)) {
    attention.push({ text: backupDays === null ? "No backup downloaded yet. The database is the only copy of your schedules." : `Last backup was ${backupDays} days ago`, href: "/admin", tone: "bad", icon: "shield" });
  }
  for (const [what, href] of gaps) attention.push({ text: what, href, tone: "accent", icon: "add" });
  const iconTone = { warn: "bg-warn-soft text-warn", bad: "bg-bad-soft text-bad", accent: "bg-brand-soft text-brand-ink" };

  return (
    <>
      <div className="page-head">
        <div className="eyebrow">{longDate(now)} {now.slice(0, 4)}</div>
        <h1 className="page-title mt-1">{greeting(user)}</h1>
      </div>
      <div className="stack">
        {!people.length ? (
          <div className="hero">
            <div className="text-sm text-white/70">Getting started</div>
            <h2 className="mt-1 mb-2 text-2xl font-semibold tracking-tight">Add your participants first</h2>
            <p className="mt-0 mb-5 max-w-lg text-sm text-white/75">Schedules are filled from the people you add, with the parts each one can take.</p>
            <Link className="btn primary" href="/participants"><Icon name="add" /> Add participants</Link>
          </div>
        ) : next ? (() => {
          const mrows = meetingRows(rows, next.date, next.type);
          const meta = metas.get(key(next.date, next.type));
          const { filled, needed } = fillCounts(mrows);
          const open = needed - filled;
          const detail = next.type === MIDWEEK ? meta?.heading : talkText(meta);
          return (
            <div className="hero">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="text-sm text-white/70">Next meeting · {next.type}</div>
                  <h2 className="mt-1 mb-0 text-2xl font-semibold tracking-tight md:text-3xl">{longDate(next.date)}</h2>
                  <div className="mt-1 text-sm text-white/70">{daysAway(next.date)}{detail ? ` · ${detail}` : ""}</div>
                </div>
                <span className={`pill ${open ? "bg-white/15! text-white!" : "bg-emerald-400/20! text-emerald-100!"}`}>
                  <Icon name={open ? "clock" : "check"} />{open ? `${open} ${open === 1 ? "slot" : "slots"} open` : "Every part filled"}
                </span>
              </div>
              <div className="mt-6 grid gap-6 md:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)] md:items-end">
                <div className="grid gap-3">
                  {["Treasures", "Ministry", "Living", "Weekend"].map((section) => {
                    const part = mrows.filter((r) => r.section === section);
                    if (!part.length) return null;
                    const c = fillCounts(part);
                    return (
                      <div key={section} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1.5 text-sm sm:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)_auto]">
                        <span className="truncate text-white/85">{SECTION_TITLES[section]}</span>
                        <div className="hero-bar max-sm:order-last max-sm:col-span-2"><div style={{ width: `${c.needed ? (100 * c.filled) / c.needed : 0}%`, background: SECTION_COLORS[section] }} /></div>
                        <span className="num text-xs text-white/70">{c.filled}/{c.needed}</span>
                      </div>
                    );
                  })}
                </div>
                <div className="btns md:justify-end">
                  <Link className="btn primary" href={editHref(next.date, next.type)}><Icon name="edit" /> {open ? "Fill open slots" : "Edit schedule"}</Link>
                  <Link className="btn" href={`/print?meeting=${encodeURIComponent(key(next.date, next.type))}`}><Icon name="print" /> Print slips</Link>
                </div>
              </div>
            </div>
          );
        })() : (
          <div className="hero">
            <div className="text-sm text-white/70">{gap ? "Next workbook week" : "No meetings yet"}</div>
            <h2 className="mt-1 mb-1 text-2xl font-semibold tracking-tight md:text-3xl">{gap ? longDate(gap.meeting) : "Create your first schedule"}</h2>
            <p className="mt-0 mb-5 text-sm text-white/75">{gap ? `${gap.label} has no schedule yet.` : "Upload the workbook to get each week's parts, then create the first schedule."}</p>
            <div className="btns">
              <Link className="btn primary" href={gap ? createHref(gap.meeting) : "/schedule"}><Icon name="add" /> {gap ? "Create this week" : "Create a schedule"}</Link>
              {gap ? null : <Link className="btn" href="/workbook"><Icon name="upload" /> Upload workbook</Link>}
            </div>
          </div>
        )}

        {people.length ? (
          <div className="grid grid-cols-3 gap-2.5 md:gap-4">
            {!soon.length && notCreated.length
              ? <Stat label="Weeks not created" value={notCreated.length} icon="calendar" tone="warn" sub="in the next 4 weeks" />
              : <Stat label="Open slots" value={openSoon} icon="clock" tone={openSoon ? "warn" : "ok"}
                  sub={soon.length && notCreated.length ? `next 4 weeks · ${notCreated.length} week(s) not created` : "next 4 weeks"} />}
            <Stat label="Active participants" value={people.filter((p) => p.active).length} icon="people" sub={`${people.length} in total`} />
            <Stat label="Away or suspended" value={away.size} icon="away" sub="this week" />
          </div>
        ) : null}

        <div className={`grid gap-4 md:gap-5 ${attention.length && upcoming.length > 1 ? "lg:grid-cols-[minmax(0,1fr)_minmax(0,1.25fr)]" : ""}`}>
          {attention.length ? (
            <div className="card">
              <div className="card-head"><h2>Needs attention</h2><span className="pill warn">{attention.length}</span></div>
              <div className="rows">
                {attention.map((a) => (
                  <Link key={a.text} href={a.href} className="row-link">
                    <span className={`row-icon ${iconTone[a.tone]}`}><Icon name={a.icon} /></span>
                    <span className="min-w-0 text-sm">{a.text}</span>
                    <span className="chev"><Icon name="chevron" /></span>
                  </Link>
                ))}
              </div>
            </div>
          ) : null}

          {upcoming.length > 1 ? (
            <div className="card">
              <div className="card-head"><h2>Coming up</h2><Link className="text-sm font-medium no-underline" href="/month">Month overview</Link></div>
              <div className="rows">
                {upcoming.slice(1, 9).map((m) => {
                  const meta = metas.get(key(m.date, m.type));
                  const c = fillCounts(meetingRows(rows, m.date, m.type));
                  const pct = c.needed ? Math.round((100 * c.filled) / c.needed) : 100;
                  const open = c.needed - c.filled;
                  const [day, mon] = shortDay(m.date).split(" ").slice(1);
                  return (
                    <Link key={key(m.date, m.type)} href={editHref(m.date, m.type)} className="row-link">
                      <span className="datebox"><b>{day}</b><span>{mon}</span></span>
                      <span className="grid min-w-0 flex-1 gap-1.5">
                        <span className="flex items-center gap-2 text-sm">
                          <span className="font-semibold">{m.type === MIDWEEK ? "Midweek" : "Weekend"}</span>
                          <span className="truncate text-muted">{(m.type === MIDWEEK ? meta?.heading : talkText(meta)) || ""}</span>
                        </span>
                        <Bar pct={pct} label="Filled" />
                      </span>
                      <span className={`pill ${open ? "warn" : "ok"}`}>{open ? `${open} open` : "Filled"}</span>
                      <span className="chev"><Icon name="chevron" /></span>
                    </Link>
                  );
                })}
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </>
  );
}
