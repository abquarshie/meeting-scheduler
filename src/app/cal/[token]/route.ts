import { readCalToken } from "@/lib/calLink";
import { getRows, getSettings, setting } from "@/lib/data";
import { addDays, today } from "@/lib/dates";
import { prisma } from "@/lib/db";
import { calendar, remindersFrom } from "@/lib/reminders";

// A participant's assignments as a calendar feed (no sign-in: the signed link is the key). Phones that subscribe
// re-read it every few hours, so new and changed parts show up on their own.
export async function GET(_: Request, { params }: { params: Promise<{ token: string }> }) {
  const id = readCalToken((await params).token);
  if (id === null) return new Response("This calendar link doesn't work. Ask for a new one.", { status: 404 });
  try {
    const [person, rows, settings] = await Promise.all([
      prisma.students.findUnique({ where: { id }, select: { name: true } }),
      getRows({ from: addDays(today(), -60), person: id }),
      getSettings(),
    ]);
    if (!person) return new Response("Not found", { status: 404 });
    const mine = remindersFrom(rows).find((r) => r.id === id) ?? null;
    const body = calendar(mine, person.name, {
      midweek: setting(settings, "midweek_time"), weekend: setting(settings, "weekend_time") || setting(settings, "meeting_time"),
      congregation: setting(settings, "congregation"),
    });
    return new Response(body, {
      headers: {
        "content-type": "text/calendar; charset=utf-8",
        "content-disposition": `inline; filename="assignments-${id}.ics"`,
        "cache-control": "private, max-age=300",
      },
    });
  } catch (e) {
    console.error(e);
    return new Response("Couldn't read the schedule just now.", { status: 503 });
  }
}
