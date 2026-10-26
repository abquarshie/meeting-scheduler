import type { Metadata } from "next";
import { LoginForm } from "./LoginForm";

export const metadata: Metadata = { title: "Sign in" };

export default async function LoginPage({ searchParams }: { searchParams: Promise<{ next?: string }> }) {
  const { next } = await searchParams;
  return (
    <main className="grid min-h-dvh md:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
      <section className="hero hidden rounded-none! md:flex md:flex-col md:justify-between md:p-12!">
        <div className="flex items-center gap-3 text-lg font-semibold">
          <img src="/icon.svg" alt="" className="size-10 rounded-xl ring-1 ring-white/20" />Meeting Scheduler
        </div>
        <div className="max-w-md">
          <h2 className="m-0 text-3xl leading-tight font-semibold tracking-tight">Every part filled, every slip printed.</h2>
          <p className="mt-3 mb-0 text-white/75">Midweek and weekend assignments, S-89 slips, the S-140 and public talk letters, in one place.</p>
        </div>
        <div className="text-sm text-white/60">Changes are credited to the name you sign in with.</div>
      </section>
      <section className="grid place-items-center bg-[radial-gradient(ellipse_at_top,var(--brand-soft),transparent_60%)] px-4 py-10 md:bg-none">
        <div className="w-full max-w-sm">
          <div className="mb-8 flex items-center gap-3 md:hidden">
            <img src="/icon.svg" alt="" className="size-10 rounded-xl" />
            <span className="text-lg font-semibold">Meeting Scheduler</span>
          </div>
          <h1 className="m-0 text-2xl font-semibold tracking-tight">Welcome back</h1>
          <p className="mt-1.5 mb-6 text-sm text-muted">Sign in to manage assignments.</p>
          <LoginForm next={next ?? ""} />
        </div>
      </section>
    </main>
  );
}
