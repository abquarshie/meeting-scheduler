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
  const [user, lang] = await Promise.all([requireUser(), prisma.settings.findUnique({ where: { key: "slip_language" } })]);
  const language = (LANGUAGES as readonly string[]).includes(lang?.value ?? "") ? lang!.value! : LANGUAGES[0];
  return (
    <div className="min-h-dvh md:grid md:grid-cols-[240px_minmax(0,1fr)]">
      <aside className="sticky top-0 hidden h-dvh flex-col gap-1 border-r border-line bg-surface px-3 py-5 md:flex">
        <a className="mb-4 flex items-center gap-2.5 px-2 text-lg font-bold tracking-tight text-ink no-underline" href="/">
          <img src="/icon.svg" alt="" className="size-8" />Meeting Scheduler
        </a>
        <SideNav items={ITEMS} />
        <div className="mt-auto grid gap-3 border-t border-line pt-4">
          <LanguagePick value={language} />
          <div className="flex items-center justify-between gap-2 px-1">
            <span className="truncate text-sm font-semibold">{user}</span>
            <form action={signOutAction}>
              <button className="btn ghost small" type="submit"><Icon name="logout" /> Sign out</button>
            </form>
          </div>
        </div>
      </aside>
      <main className="mx-auto w-full max-w-6xl px-4 pt-5 pb-28 md:px-8 md:pt-9 md:pb-16">{children}</main>
      <TabBar items={ITEMS} />
    </div>
  );
}
