"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Icon, type IconName } from "./icons";

export type NavItem = { href: string; label: string; short?: string; icon: IconName; phone?: boolean };

function active(path: string, href: string) {
  return href === "/" ? path === "/" : path === href || path.startsWith(`${href}/`);
}

export function SideNav({ items }: { items: NavItem[] }) {
  const path = usePathname();
  return (
    <nav aria-label="Main" className="grid gap-0.5">
      {items.map((i) => (
        <Link key={i.href} href={i.href} aria-current={active(path, i.href) ? "page" : undefined}
          className="nav-link">
          <Icon name={i.icon} />{i.label}
        </Link>
      ))}
    </nav>
  );
}

/** Phones: the five pages used most along the bottom, the rest under More. */
export function TabBar({ items }: { items: NavItem[] }) {
  const path = usePathname();
  const main = items.filter((i) => i.phone);
  const more = items.filter((i) => !i.phone);
  const inMore = more.some((i) => active(path, i.href));
  return (
    <nav aria-label="Main"
      className="fixed inset-x-0 bottom-0 z-30 flex border-t border-line bg-surface/90 px-1 pt-1.5 pb-[calc(.375rem+env(safe-area-inset-bottom))] backdrop-blur md:hidden">
      {main.map((i) => (
        <Link key={i.href} href={i.href} aria-current={active(path, i.href) ? "page" : undefined}
          className="flex flex-1 flex-col items-center gap-0.5 rounded-lg py-1 text-[11px] font-medium text-faint no-underline aria-[current=page]:font-semibold aria-[current=page]:text-brand-ink [&_svg]:size-6">
          <Icon name={i.icon} />{i.short ?? i.label}
        </Link>
      ))}
      <details className="relative flex flex-1">
        <summary aria-current={inMore ? "page" : undefined}
          className="flex flex-1 cursor-pointer list-none flex-col items-center gap-0.5 rounded-lg py-1 text-[11px] font-medium text-faint aria-[current=page]:font-semibold aria-[current=page]:text-brand-ink [&_svg]:size-6">
          <Icon name="settings" />More
        </summary>
        <div className="absolute right-1 bottom-[calc(100%+8px)] grid w-56 gap-0.5 rounded-2xl border border-line bg-surface p-2 shadow-lift">
          {more.map((i) => (
            <Link key={i.href} href={i.href} aria-current={active(path, i.href) ? "page" : undefined}
              onClick={(e) => (e.currentTarget.closest("details") as HTMLDetailsElement | null)?.removeAttribute("open")}
              className="nav-link">
              <Icon name={i.icon} />{i.label}
            </Link>
          ))}
        </div>
      </details>
    </nav>
  );
}
