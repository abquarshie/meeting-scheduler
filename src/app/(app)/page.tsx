import Link from "next/link";
import { Icon } from "@/components/icons";
import { Bar, Note, Stat } from "@/components/ui";
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
  return (
    <>
      <div className="page-head">
        <h1 className="page-title">{greeting(user)}</h1>
        <div className="page-sub">{longDate(now)} {now.slice(0, 4)}</div>
      </div>
      <div className="stack">
        {gaps.length ? (
          <div className="card">
            <h2 className="section-title">Still to set up</h2>
            <div className="grid gap-2">
              {gaps.map(([what, href]) => (
                <div key={what} className="flex items-center justify-between gap-3 text-sm">
                  <span>{what}</span><Link className="btn small" href={href}>Go</Link>
                </div>
              ))}
            </div>
            <div className="caption">This disappears as each one is done.</div>
          </div>
        ) : null}

        {!people.length ? (
          <div className="card">
            <h2 className="section-title">Add your participants first</h2>
            <p className="mt-0 text-sm">Schedules are filled from the people you add, with the parts each one can take.</p>
            <Link className="btn primary" href="/participants">Add participants</Link>
          </div>
        ) : (
          <>
            <div className="card border-l-4 border-l-brand">
              {next ? (() => {
                const mrows = meetingRows(rows, next.date, next.type);
                const meta = metas.get(key(next.date, next.type));
                const { filled, needed } = fillCounts(mrows);
                const open = needed - filled;
                const detail = next.type === MIDWEEK ? meta?.heading : talkText(meta);
                return (
                  <div className="grid gap-5 md:grid-cols-[minmax(0,3fr)_minmax(0,1fr)]">
                    <div>
                      <div className="text-xl font-bold">{longDate(next.date)}</div>
                      <div className="mb-3 text-sm text-muted">{next.type}, {daysAway(next.date)}{detail ? `. ${detail}` : ""}</div>
                      <div className="grid gap-2">
                        {["Treasures", "Ministry", "Living", "Weekend"].map((section) => {
                          const part = mrows.filter((r) => r.section === section);
                          if (!part.length) return null;
                          const c = fillCounts(part);
                          return (
                            <div key={section} className="grid grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)_auto] items-center gap-3 text-sm">
                              <span className="flex items-center gap-2 truncate"><span className="swatch" style={{ background: SECTION_COLORS[section] }} />{SECTION_TITLES[section]}</span>
                              <Bar pct={c.needed ? (100 * c.filled) / c.needed : 0} color={SECTION_COLORS[section]} label={section} />
                              <span className="num text-xs text-muted">{c.filled} of {c.needed}</span>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                    <div className="grid content-start gap-2">
                      <div className="num text-4xl font-bold">{open}</div>
                      <div className="text-sm text-muted">{open ? (open === 1 ? "slot open" : "slots open") : "Every part is filled"}</div>
                      <Link className={`btn ${open ? "primary" : ""}`} href={editHref(next.date, next.type)}><Icon name="edit" /> {open ? "Fill open slots" : "Edit schedule"}</Link>
                      <Link className="btn" href={`/print?meeting=${encodeURIComponent(key(next.date, next.type))}`}><Icon name="print" /> Print slips</Link>
                    </div>
                  </div>
                );
              })() : gap ? (
                <div className="grid gap-3">
                  <div><div className="text-xl font-bold">{longDate(gap.meeting)}</div><div className="text-sm text-muted">{gap.label} has no schedule yet.</div></div>
                  <Link className="btn primary w-fit" href={createHref(gap.meeting)}><Icon name="add" /> Create this week</Link>
                </div>
              ) : (
                <div className="grid gap-3">
                  <div><div className="text-xl font-bold">No meetings scheduled yet</div><div className="text-sm text-muted">Upload the workbook to get each week&apos;s parts, then create the first schedule.</div></div>
                  <div className="btns"><Link className="btn primary" href="/schedule"><Icon name="add" /> Create a schedule</Link><Link className="btn" href="/workbook">Upload workbook</Link></div>
                </div>
              )}
            </div>

            {next && gap ? (
              <Note><span className="flex flex-wrap items-center justify-between gap-2">{gap.label} ({longDate(gap.meeting)}) has no schedule yet.
                <Link className="btn small" href={createHref(gap.meeting)}><Icon name="add" /> Create it</Link></span></Note>
            ) : null}

            {anySaved && (backupDays === null || backupDays >= BACKUP_REMINDER_DAYS) ? (
              <Note tone="warn"><span className="flex flex-wrap items-center justify-between gap-2">
                {backupDays === null ? "No backup file has been downloaded yet." : `Last backup was ${backupDays} days ago.`} The database is the only copy of your schedules until you take one.
                <Link className="btn small" href="/admin">Back up now</Link></span></Note>
            ) : null}

            <div className="grid grid-cols-3 gap-3">
              {!soon.length && notCreated.length
                ? <Stat label="Weeks not yet created" value={notCreated.length} />
                : <Stat label="Open slots, next 4 weeks" value={openSoon} />}
              <Stat label="Active participants" value={people.filter((p) => p.active).length} />
              <Stat label="Away or suspended this week" value={away.size} />
            </div>
            {soon.length && notCreated.length ? <div className="caption mt-0">{notCreated.length} week(s) in the next 4 weeks still have no schedule.</div> : null}

            {upcoming.length > 1 ? (
              <div className="card">
                <h2 className="section-title">Coming up</h2>
                <div className="table-wrap">
                  <table className="table">
                    <thead><tr><th>Date</th><th>Meeting</th><th>Week or talk</th><th>Filled</th><th className="r">Open</th><th /></tr></thead>
                    <tbody>
                      {upcoming.slice(1, 9).map((m) => {
                        const meta = metas.get(key(m.date, m.type));
                        const c = fillCounts(meetingRows(rows, m.date, m.type));
                        const pct = c.needed ? Math.round((100 * c.filled) / c.needed) : 100;
                        return (
                          <tr key={key(m.date, m.type)}>
                            <td className="whitespace-nowrap">{shortDay(m.date)}</td>
                            <td>{m.type === MIDWEEK ? "Midweek" : "Weekend"}</td>
                            <td>{(m.type === MIDWEEK ? meta?.heading : talkText(meta)) || ""}</td>
                            <td className="min-w-28"><div className="flex items-center gap-2"><Bar pct={pct} label="Filled" /><span className="num text-xs text-muted">{pct}%</span></div></td>
                            <td className="r num">{c.needed - c.filled}</td>
                            <td className="r"><Link href={editHref(m.date, m.type)}>Open</Link></td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : null}
          </>
        )}
      </div>
    </>
  );
}
