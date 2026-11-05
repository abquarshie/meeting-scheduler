import type { Metadata } from "next";
import Link from "next/link";
import { Empty, PageHead, Tabs } from "@/components/ui";
import { getUser, roleOf } from "@/lib/auth";
import { calPath } from "@/lib/calLink";
import { WEEKEND } from "@/lib/constants";
import { getPeople, getRows, getSettings, setting } from "@/lib/data";
import { waNumber } from "@/lib/contacts";
import { addDays, longDate, today } from "@/lib/dates";
import { reminderText, remindersFrom } from "@/lib/reminders";
import { CalendarTimes, ReminderList, type Card } from "./Reminders";

export const metadata: Metadata = { title: "Reminders" };
const SPANS = [["7", "Next 7 days"], ["14", "Next 14 days"]] as const;

export default async function RemindersPage({ searchParams }: { searchParams: Promise<{ days?: string }> }) {
  const sp = await searchParams;
  const days = sp.days === "14" ? 14 : 7;
  const now = today();
  const [user, rows, people, settings] = await Promise.all([
    getUser(), getRows({ from: now, to: addDays(now, days - 1) }), getPeople(), getSettings(),
  ]);
  const weekendOnly = user !== null && roleOf(user) === "weekend";
  const phone = new Map(people.map((p) => [p.id, p.phone]));
  const congregation = setting(settings, "congregation");
  const list = remindersFrom(weekendOnly ? rows.filter((r) => r.meeting_type === WEEKEND) : rows);
  const cards: Card[] = list.map((r) => {
    const text = reminderText(r, congregation);
    const ph = phone.get(r.id) ?? "";
    return {
      id: r.id, name: r.name, phone: ph, text, cal: calPath(r.id),
      wa: `https://wa.me/${waNumber(ph)}?text=${encodeURIComponent(text)}`,
      lines: r.duties.map((d) => `${longDate(d.date)}: ${d.assisting ? `assisting ${d.with ?? ""} with ` : ""}${d.part}`),
    };
  });
  const noNumber = cards.filter((c) => !waNumber(c.phone)).length;

  return (
    <>
      <PageHead title="Reminders" sub="Everyone with a part coming up, with a ready WhatsApp message and a calendar link for their phone." />
      <Tabs current={`/reminders?days=${days}`} tabs={SPANS.map(([d, label]) => ({ href: `/reminders?days=${d}`, label }))} />
      <div className="stack">
        {noNumber ? (
          <p className="m-0 text-sm text-muted">
            {noNumber} of {cards.length} have no WhatsApp number saved, so WhatsApp asks you to pick the chat.{" "}
            {weekendOnly ? null : <>Add numbers under <Link href="/participants?tab=edit">Participants</Link>.</>}
          </p>
        ) : null}
        {cards.length ? <ReminderList cards={cards} /> : <Empty>No one has a part in the next {days} days.</Empty>}
        <details className="card">
          <summary>Calendar links</summary>
          <p className="mt-0 text-sm text-muted">
            Each person&apos;s Calendar link is a feed of all their parts. Opened on a phone (or added in Google Calendar under
            &ldquo;From URL&rdquo;), new and changed parts appear by themselves, with an alert the evening before. Set the
            meeting times so entries have the right hours; without them they show as all-day.
          </p>
          <CalendarTimes midweek={setting(settings, "midweek_time")} weekend={setting(settings, "weekend_time") || setting(settings, "meeting_time")} />
        </details>
      </div>
    </>
  );
}
