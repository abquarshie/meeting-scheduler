// What's new: shown once on each phone or computer when the app opens after an update (components/WhatsNew.tsx).
// Every pull request that changes something people will notice adds an entry at the TOP of NEWS, with the next id,
// today's date and a few plain sentences. Entries never change id once released.
export type News = { id: number; date: string; title: string; items: string[] };

export const NEWS: News[] = [
  {
    id: 3, date: "2026-11-09", title: "Weekend schedule columns",
    items: ["The weekend schedule now reads: date, speaker, talk title, chairman, opening prayer, reader."],
  },
  {
    id: 2, date: "2026-11-06", title: "What's new",
    items: ["This card tells you about updates the first time you open the app after a change."],
  },
  {
    id: 1, date: "2026-11-05", title: "Reminders and calendars",
    items: [
      "Send each participant a WhatsApp reminder of their part.",
      "Each participant can subscribe to their own calendar of assignments, with an iPhone link too.",
      "Calendar events show the Kingdom Hall and each part's theme.",
      "Assembly and convention weeks show on the midweek sheet and S-140.",
    ],
  },
];
