import type { Metadata } from "next";
import { signOutAction } from "@/actions/session";
import { LanguagePick } from "@/components/LanguagePick";
import { Icon } from "@/components/icons";
import { PageHead, Tabs } from "@/components/ui";
import { getUser } from "@/lib/auth";
import { EVENT_TEXT, LANGUAGES } from "@/lib/constants";
import { gapDays, getEvents, getSettings, setting, templateNames } from "@/lib/data";
import { weekLabel } from "@/lib/dates";
import { prisma } from "@/lib/db";
import { Backup, ChangeLog, Settings, Templates } from "./Admin";

export const metadata: Metadata = { title: "Admin" };

const TABS = [["data", "Data & backup"], ["settings", "Settings"], ["log", "Change log"]] as const;

export default async function AdminPage({ searchParams }: { searchParams: Promise<{ tab?: string; who?: string }> }) {
  const sp = await searchParams;
  const tab = TABS.some(([k]) => k === sp.tab) ? sp.tab! : "data";
  const [settings, user] = await Promise.all([getSettings(), getUser()]);
  let body;
  if (tab === "settings") {
    const events = await getEvents();
    body = (
      <Settings congregation={setting(settings, "congregation")} useAux={setting(settings, "use_aux", "1") === "1"}
        gaConvert={setting(settings, "ga_convert", "0") === "1"} midweek={setting(settings, "midweek_day", "Wednesday")}
        weekend={setting(settings, "weekend_day", "Sunday")} gap={gapDays(settings)}
        events={events.map((e) => ({ id: e.id, text: `${weekLabel(e.start)} — ${EVENT_TEXT[e.kind].en} · ${EVENT_TEXT[e.kind].ga}` }))} />
    );
  } else if (tab === "log") {
    const log = await prisma.audit_log.findMany({ orderBy: { id: "desc" }, take: 500 });
    body = <ChangeLog log={log.map((l) => ({ id: l.id, ts: (l.ts ?? "").replace("T", " "), user: l.user ?? "", action: l.action ?? "", details: l.details ?? "" }))} />;
  } else {
    const names = await templateNames();
    body = (
      <>
        <Templates languages={[...LANGUAGES]} stored={Object.fromEntries(names)} />
        <Backup />
      </>
    );
  }
  return (
    <>
      <PageHead title="Admin" sub="Blank forms, backups, settings and the change log." />
      <Tabs current={`/admin?tab=${tab}`} tabs={TABS.map(([k, l]) => ({ href: `/admin?tab=${k}`, label: l }))} />
      <div className="stack">
        {body}
        {/* the sidebar holds these on a computer; a phone has only the tab bar */}
        <div className="card grid gap-3 md:hidden">
          <LanguagePick value={setting(settings, "slip_language", "English")} />
          <form action={signOutAction} className="flex items-center gap-3">
            <span className="flex-1 text-sm text-muted">Signed in as {user}</span>
            <button className="btn small"><Icon name="logout" /> Sign out</button>
          </form>
        </div>
      </div>
    </>
  );
}
