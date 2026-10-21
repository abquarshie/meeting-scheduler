import type { Metadata } from "next";
import { PageHead } from "@/components/ui";
import { getPeople, getRows, getSettings, setting } from "@/lib/data";
import { fmtDate, today } from "@/lib/dates";
import { prisma } from "@/lib/db";
import { nfc } from "@/lib/text";
import { Talks } from "./Talks";

export const metadata: Metadata = { title: "Public talks" };

/** Numeric where it can be, so 2 sorts before 10 (db._talks). */
function talkOrder(a: string, b: string) {
  const x = /^\d+$/.test(a) ? Number(a) : null, y = /^\d+$/.test(b) ? Number(b) : null;
  if (x !== null && y !== null) return x - y;
  if (x !== null) return -1;
  if (y !== null) return 1;
  return a.localeCompare(b);
}

export default async function TalksPage({ searchParams }: { searchParams: Promise<{ tab?: string }> }) {
  const [sp, rows, people, settings, talkRows, speakerRows, engagementRows] = await Promise.all([
    searchParams, getRows({ role: "Public Talk" }), getPeople(), getSettings(), prisma.talks.findMany(),
    prisma.outgoing_speakers.findMany({ where: { active: 1 } }),
    prisma.outgoing_engagements.findMany({ orderBy: { meeting_date: "asc" } }),
  ]);
  const talks = talkRows.map((t) => ({ number: t.number, title: t.title ?? "" })).sort((a, b) => talkOrder(a.number, b.number));

  // one choice per guest speaker: a symposium can bring two to one meeting
  const guests = rows
    .filter((r) => r.person && nfc(r.visitor))
    .sort((a, b) => a.meeting_date.localeCompare(b.meeting_date) || a.sort_order - b.sort_order)
    .map((r) => ({ id: r.id, date: r.meeting_date, label: `${fmtDate(r.meeting_date)} — ${r.person}`, congregation: nfc(r.visitor_congregation) }));
  const upcoming = guests.find((g) => g.date >= today());

  const letter = Object.fromEntries([
    "meeting_time", "hall_address", "talk_coordinator_phone", "talk_coordinator_email",
  ].map((k) => [k, setting(settings, k)]));
  letter.talk_coordinator_signoff = setting(settings, "talk_coordinator_signoff", "Bernard Mensah");

  const brothers = people.filter((p) => p.active && p.gender === "Brother").map((p) => ({ id: p.id, name: p.name }));
  const names = new Map(people.map((p) => [p.id, p.name]));
  const speakers = speakerRows
    .filter((s) => names.has(s.student_id))
    .map((s) => ({
      id: s.student_id, name: names.get(s.student_id)!,
      talks: (s.talk_numbers ?? "").split(",").map((n) => n.trim()).filter(Boolean),
      engagements: engagementRows.filter((e) => e.student_id === s.student_id)
        .map((e) => ({ id: e.id, date: e.meeting_date, congregation: e.congregation ?? "", talk: e.talk_number ?? "" })),
    }))
    .sort((a, b) => a.name.toLowerCase().localeCompare(b.name.toLowerCase()));

  return (
    <>
      <PageHead title="Public talks" sub="Guest speakers, our outgoing speakers, their letters, the talk list and the annual checklist." />
      <Talks tab={sp.tab ?? "letters"} guests={guests} defaultGuest={(upcoming ?? guests[guests.length - 1])?.id ?? 0}
        letter={letter} talks={talks} brothers={brothers} speakers={speakers} />
    </>
  );
}
