// Line icons drawn inline, so nothing loads from elsewhere.
const PATHS = {
  home: "M3 10.5 12 3l9 7.5V21h-6v-6H9v6H3z",
  calendar: "M5 4h14a2 2 0 0 1 2 2v13a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z M16 2v4 M8 2v4 M3 10h18",
  edit: "M4 20h4L19 9l-4-4L4 16v4Z M13 7l4 4",
  print: "M6 9V3h12v6 M6 17H4v-6a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v6h-2 M6 14h12v7H6z",
  mic: "M12 2a3 3 0 0 1 3 3v6a3 3 0 0 1-6 0V5a3 3 0 0 1 3-3Z M5 11a7 7 0 0 0 14 0 M12 18v4",
  people: "M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z M2 21v-1a6 6 0 0 1 12 0v1 M16 3.5a4 4 0 0 1 0 7 M22 21v-1a6 6 0 0 0-4-5.6",
  book: "M3 5h7a2 2 0 0 1 2 2v13a2 2 0 0 0-2-2H3z M21 5h-7a2 2 0 0 0-2 2v13a2 2 0 0 1 2-2h7z",
  chart: "M4 20V10 M10 20V4 M16 20v-7 M3 20h18",
  settings: "M4 6h10 M18 6h2 M16 4v4 M4 12h4 M12 12h8 M10 10v4 M4 18h12 M20 18h0 M18 16v4",
  logout: "M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4 M16 17l5-5-5-5 M21 12H9",
  close: "M6 6l12 12 M18 6 6 18",
  download: "M12 3v12 M7 10l5 5 5-5 M4 21h16",
  upload: "M12 21V9 M7 14l5-5 5 5 M4 3h16",
  add: "M12 5v14 M5 12h14",
  sparkle: "M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z M19 17v4 M17 19h4",
  undo: "M9 14 4 9l5-5 M4 9h11a5 5 0 0 1 0 10h-3",
  trash: "M4 7h16 M10 11v6 M14 11v6 M6 7l1 13h10l1-13 M9 7V4h6v3",
  save: "M5 3h11l3 3v15H5z M8 3v5h7V3 M8 21v-7h8v7",
  copy: "M9 9h11v11H9z M5 15H4V4h11v1",
  warning: "M12 3 2 20h20L12 3Z M12 10v4 M12 17h0",
  check: "M5 12l5 5L20 7",
  chevron: "M9 6l6 6-6 6",
  clock: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z M12 7v5l3 2",
  away: "M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z M2 21v-1a6 6 0 0 1 10-4.5 M16 16l5 5 M21 16l-5 5",
  shield: "M12 3l8 3v6c0 4.5-3.4 8.3-8 9-4.6-.7-8-4.5-8-9V6z M9 12l2 2 4-4",
  globe: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z M3 12h18 M12 3a14 14 0 0 1 0 18 M12 3a14 14 0 0 0 0 18",
} as const;

export type IconName = keyof typeof PATHS;

export function Icon({ name, title }: { name: IconName; title?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round"
      strokeLinejoin="round" aria-hidden={title ? undefined : true} role={title ? "img" : undefined}>
      {title ? <title>{title}</title> : null}
      <path d={PATHS[name]} />
    </svg>
  );
}
