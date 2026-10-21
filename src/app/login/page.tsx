import type { Metadata } from "next";
import { LoginForm } from "./LoginForm";

export const metadata: Metadata = { title: "Sign in" };

export default async function LoginPage({ searchParams }: { searchParams: Promise<{ next?: string }> }) {
  const { next } = await searchParams;
  return (
    <main className="grid min-h-dvh place-items-center px-4">
      <div className="card w-full max-w-sm">
        <div className="mb-4 flex items-center gap-3">
          <img src="/icon.svg" alt="" className="size-10" />
          <div>
            <h1 className="m-0 text-xl font-bold">Meeting Scheduler</h1>
            <div className="text-sm text-muted">Sign in to manage assignments.</div>
          </div>
        </div>
        <LoginForm next={next ?? ""} />
      </div>
    </main>
  );
}
