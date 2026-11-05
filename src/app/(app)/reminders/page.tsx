import type { Metadata } from "next";
import { Empty, PageHead, Tabs } from "@/components/ui";
import { getUser, roleOf } from "@/lib/auth";
import { calPath } from "@/lib/calLink";
import { WEEKEND } from "@/lib/constants";
import { getRows, getSettings, setting } from "@/lib/data";
import { addDays, longDate, today } from "@/lib/dates";
import { reminderText, remindersFrom } from "@/lib/reminders";
import { CalendarTimes, ReminderList, type Card } from "./Reminders";

export const metadata: Metadata = { title: "Reminders" };
const SPANS = [["7", "Next 7 days"], ["14", "Next 14 days"]] as const;

export default async function RemindersPage({ searchParams }: { searchParams: Promise<{ days?: string }> }) {
  const sp = await searchParams;
  const days = sp.days === "14" ? 14 : 7;
  const now = today();
  const [user, rows, settings] = await Promise.all([
    getUser(), getRows({ from: now, to: addDays(now, days - 1) }), getSettings(),
  ]);
  const weekendOnly = user !== null && roleOf(user) === "weekend";
  const congregation = setting(settings, "congregation");
  const list = remindersFrom(weekendOnly ? rows.filter((r) => r.meeting_type === WEEKEND) : rows);
  const cards: Card[] = list.map((r) => {
    const text = reminderText(r, congregation);
    return {
      id: r.id, name: r.name, text, cal: weekendOnly ? "" : calPath(r.id), // calendar links are for full sign-ins only
      wa: `https://wa.me/?text=${encodeURIComponent(text)}`,
      lines: r.duties.map((d) => `${longDate(d.date)}: ${d.assisting ? `assisting ${d.with ?? ""} with ` : ""}${d.part}`),
    };
  });

  return (
    <>
      <PageHead title="Reminders" sub={`Everyone with a part coming up, with a ready WhatsApp message${weekendOnly ? "" : " and a calendar link for their phone"}.`} />
      <Tabs current={`/reminders?days=${days}`} tabs={SPANS.map(([d, label]) => ({ href: `/reminders?days=${d}`, label }))} />
      <div className="stack">
        {cards.length ? <ReminderList cards={cards} /> : <Empty>No one has a part in the next {days} days.</Empty>}
        {weekendOnly ? null : (
        <details className="card">
          <summary>Calendar links</summary>
          <p className="mt-0 text-sm text-muted">
            Each person&apos;s Calendar link is a feed of all their parts. Once subscribed, new and changed parts appear by
            themselves, with an alert the evening before. On Android, add the Calendar link in Google Calendar under
            &ldquo;From URL&rdquo;. On an iPhone, send the iPhone link instead: tapping it offers &ldquo;Subscribe&rdquo;
            (the plain link only adds the parts once). Set the meeting times so entries have the right hours; without
            them they show as all-day.
          </p>
          <CalendarTimes midweek={setting(settings, "midweek_time")} weekend={setting(settings, "weekend_time") || setting(settings, "meeting_time")} />
        </details>
        )}
      </div>
    </>
  );
}
