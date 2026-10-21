import type { Metadata } from "next";
import { PageHead } from "@/components/ui";
import { assignmentStats, familyNames, getPeople } from "@/lib/data";
import { prisma } from "@/lib/db";
import { People } from "./People";

export const metadata: Metadata = { title: "Participants" };

export default async function ParticipantsPage({ searchParams }: { searchParams: Promise<{ tab?: string; id?: string }> }) {
  const [sp, people, { used, last }, away] = await Promise.all([
    searchParams, getPeople(), assignmentStats(), prisma.unavailable.findMany({ orderBy: { meeting_date: "asc" } }),
  ]);
  const awayBy: Record<number, string[]> = {};
  for (const a of away) (awayBy[a.student_id] ??= []).push(a.meeting_date);
  return (
    <>
      <PageHead title="Participants" sub="Who can take which parts, families, away dates and suspensions." />
      <People people={people} families={familyNames(people)} tab={sp.tab ?? (people.length ? "list" : "add")}
        selected={Number(sp.id) || people[0]?.id || 0} last={Object.fromEntries(last)} used={Object.fromEntries(used)} away={awayBy} />
    </>
  );
}
