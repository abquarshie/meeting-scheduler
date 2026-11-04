import type { Metadata } from "next";
import { PageHead } from "@/components/ui";
import { getRole } from "@/lib/auth";
import { MEETING_TYPES, WEEKEND } from "@/lib/constants";
import { isISODate, today } from "@/lib/dates";
import { getMeetingList } from "@/lib/data";
import { Editor } from "./Editor";

export const metadata: Metadata = { title: "Create or edit" };

export default async function SchedulePage({ searchParams }: {
  searchParams: Promise<{ date?: string; type?: string; mode?: string }>;
}) {
  const sp = await searchParams;
  const [all, role] = await Promise.all([getMeetingList(), getRole()]);
  // a weekend-only user creates and edits weekend meetings only
  const types: readonly string[] = role === "weekend" ? [WEEKEND] : MEETING_TYPES;
  const saved = all.filter((m) => types.includes(m.type));
  const date = isISODate(sp.date) ? sp.date : today();
  const type = types.includes(sp.type ?? "") ? sp.type! : types[0]!;
  return (
    <>
      <PageHead title="Create or edit" sub="Pick a date, then fill each part. Only eligible people are listed." />
      <Editor key={`${date}|${type}`} date={date} type={type} mode={sp.mode === "edit" ? "edit" : "new"}
        saved={saved} types={types} />
    </>
  );
}
