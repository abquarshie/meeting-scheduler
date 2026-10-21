"use client";
import { useEffect } from "react";
import { Icon } from "@/components/icons";

// Shown in place of a page that failed to load (usually the database not answering), with the menu still around it.
export default function PageError({ error, retry }: { error: Error & { digest?: string }; retry: () => void }) {
  useEffect(() => { console.error(error); }, [error]);
  return (
    <div className="card mx-auto mt-6 grid max-w-lg gap-3 text-center">
      <div className="mx-auto grid size-12 place-items-center rounded-full bg-warn-soft text-warn [&_svg]:size-6"><Icon name="warning" /></div>
      <h1 className="m-0 text-xl font-bold">This page didn&apos;t load</h1>
      <p className="m-0 text-sm text-muted">
        Nothing you saved is lost. The database may have been slow to wake up; trying again usually fixes it.
      </p>
      <div className="btns justify-center">
        <button type="button" className="btn primary" onClick={() => retry()}>Try again</button>
        <a className="btn" href="/">Go to Home</a>
      </div>
      {error.digest ? <div className="caption mt-0">Reference: {error.digest}</div> : null}
    </div>
  );
}
