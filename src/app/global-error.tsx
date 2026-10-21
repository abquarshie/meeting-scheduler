"use client";
import "@fontsource-variable/inter/wght.css";
import "./globals.css";

// The last resort, when even the page frame failed. It replaces the whole document, so it brings its own html and body.
export default function GlobalError({ retry }: { error: Error & { digest?: string }; retry: () => void }) {
  return (
    <html lang="en-GB">
      <body>
        <main className="grid min-h-dvh place-items-center px-4">
          <div className="card grid w-full max-w-sm gap-3 text-center">
            <h1 className="m-0 text-xl font-bold">Something went wrong</h1>
            <p className="m-0 text-sm text-muted">Nothing you saved is lost. Please try again in a moment.</p>
            <div className="btns justify-center">
              <button type="button" className="btn primary" onClick={() => retry()}>Try again</button>
              <a className="btn" href="/">Go to Home</a>
            </div>
          </div>
        </main>
      </body>
    </html>
  );
}
