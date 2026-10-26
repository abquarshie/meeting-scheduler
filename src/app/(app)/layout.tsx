import { signOutAction } from "@/actions/session";
import { Icon } from "@/components/icons";
import { LanguagePick } from "@/components/LanguagePick";
import { SideNav, TabBar, type NavItem } from "@/components/Nav";
import { requireUser } from "@/lib/auth";
import { LANGUAGES } from "@/lib/constants";
import { prisma } from "@/lib/db";

export const dynamic = "force-dynamic"; // always the latest schedules

const ITEMS: NavItem[] = [
  { href: "/", label: "Home", icon: "home", phone: true },
  { href: "/month", label: "Month overview", short: "Month", icon: "calendar", phone: true },
  { href: "/schedule", label: "Create or edit", short: "Edit", icon: "edit", phone: true },
  { href: "/print", label: "Slips and printing", short: "Print", icon: "print", phone: true },
  { href: "/talks", label: "Public talks", icon: "mic" },
  { href: "/participants", label: "Participants", short: "People", icon: "people", phone: true },
  { href: "/workbook", label: "Workbook PDF", icon: "book" },
  { href: "/reports", label: "Reports", icon: "chart" },
  { href: "/admin", label: "Admin", icon: "settings" },
];

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  // the frame must render even when the database is down, so the page's own error screen shows inside it
  const [user, lang] = await Promise.all([
    requireUser(),
    prisma.settings.findUnique({ where: { key: "slip_language" } }).catch((e) => { console.error(e); return null; }),
  ]);
  const language = (LANGUAGES as readonly string[]).includes(lang?.value ?? "") ? lang!.value! : LANGUAGES[0];
  const initials = user.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]!.toUpperCase()).join("") || "?";
  return (
    <div className="min-h-dvh md:grid md:grid-cols-[256px_minmax(0,1fr)]">
      <aside className="sticky top-0 hidden h-dvh flex-col border-r border-line bg-surface px-3 py-5 md:flex">
        <a className="mb-6 flex items-center gap-2.5 px-2 text-[15px] font-semibold tracking-tight text-ink no-underline" href="/">
          <img src="/icon.svg" alt="" className="size-8 rounded-lg shadow-soft" />
          <span className="leading-tight">Meeting Scheduler<span className="block text-xs font-normal text-muted">Assignments &amp; slips</span></span>
        </a>
        <div className="eyebrow mb-2 px-3">Menu</div>
        <SideNav items={ITEMS} />
        <div className="mt-auto grid gap-4 pt-4">
          <LanguagePick value={language} />
          <div className="flex items-center gap-2.5 rounded-xl border border-line bg-subtle/60 p-2">
            <span className="avatar">{initials}</span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-sm font-semibold">{user}</span>
              <span className="block text-xs text-muted">Signed in</span>
            </span>
            <form action={signOutAction}>
              <button className="btn ghost small text-muted!" type="submit" title="Sign out" aria-label="Sign out"><Icon name="logout" /></button>
            </form>
          </div>
        </div>
      </aside>
      <div className="min-w-0">
        <header className="sticky top-0 z-30 flex items-center gap-2.5 border-b border-line bg-surface/90 px-4 py-2.5 backdrop-blur md:hidden">
          <a href="/" className="flex items-center gap-2 text-[15px] font-semibold text-ink no-underline">
            <img src="/icon.svg" alt="" className="size-7 rounded-lg" />Meeting Scheduler
          </a>
          <span className="avatar ml-auto size-8! text-xs">{initials}</span>
          <form action={signOutAction}>
            <button className="btn ghost small text-muted!" type="submit" aria-label="Sign out"><Icon name="logout" /></button>
          </form>
        </header>
        <main className="mx-auto w-full max-w-6xl px-4 pt-5 pb-28 md:px-10 md:pt-10 md:pb-16">{children}</main>
      </div>
      <TabBar items={ITEMS} />
    </div>
  );
}
