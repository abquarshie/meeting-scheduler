import type { Metadata } from "next";
import { PageHead } from "@/components/ui";
import { getSettings, getWorkbook, setting } from "@/lib/data";
import { WorkbookPage } from "./WorkbookPage";

export const metadata: Metadata = { title: "Workbook PDF" };

export default async function Page() {
  const [{ weeks, file }, settings] = await Promise.all([getWorkbook(), getSettings()]);
  return (
    <>
      <PageHead title="Workbook PDF" sub="Upload the meeting workbook so each week gets its real parts." />
      <WorkbookPage weeks={weeks} file={file} skipPast={setting(settings, "skip_past_weeks", "1") === "1"}
        datesSure={setting(settings, "workbook_dates_sure", "0") === "1"} />
    </>
  );
}
