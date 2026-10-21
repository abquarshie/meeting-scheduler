import type { Metadata } from "next";
import { PageHead } from "@/components/ui";
import { MEETING_TYPES, MIDWEEK } from "@/lib/constants";
import { isISODate, today } from "@/lib/dates";
import { prisma } from "@/lib/db";
import { Editor } from "./Editor";

export const metadata: Metadata = { title: "Create or edit" };

export default async function SchedulePage({ searchParams }: {
  searchParams: Promise<{ date?: string; type?: string; mode?: string }>;
}) {
  const sp = await searchParams;
  const saved = await prisma.$queryRaw<{ meeting_date: string; meeting_type: string }[]>`
    SELECT DISTINCT meeting_date, meeting_type FROM schedules ORDER BY meeting_date DESC, meeting_type`;
  const date = isISODate(sp.date) ? sp.date : today();
  const type = (MEETING_TYPES as readonly string[]).includes(sp.type ?? "") ? sp.type! : MIDWEEK;
  return (
    <>
      <PageHead title="Create or edit" sub="Pick a date, then fill each part. Only eligible people are listed." />
      <Editor key={`${date}|${type}`} date={date} type={type} mode={sp.mode === "edit" ? "edit" : "new"}
        saved={saved.map((m) => ({ date: m.meeting_date, type: m.meeting_type }))} />
    </>
  );
}
