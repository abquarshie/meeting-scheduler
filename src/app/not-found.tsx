import Link from "next/link";

export default function NotFound() {
  return (
    <main className="grid min-h-dvh place-items-center px-4">
      <div className="card grid w-full max-w-sm gap-3 text-center">
        <img src="/icon.svg" alt="" className="mx-auto size-10" />
        <h1 className="m-0 text-xl font-bold">Page not found</h1>
        <p className="m-0 text-sm text-muted">That address isn&apos;t part of the Meeting Scheduler.</p>
        <Link className="btn primary" href="/">Go to Home</Link>
      </div>
    </main>
  );
}
