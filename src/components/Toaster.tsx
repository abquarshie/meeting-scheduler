"use client";
import { createContext, useCallback, useContext, useState, type ReactNode } from "react";

type Toast = { id: number; text: string; tone?: "warn"; action?: { label: string; run: () => void } };
type Push = (text: string, opts?: { tone?: "warn"; action?: Toast["action"]; ms?: number }) => void;
const Ctx = createContext<Push>(() => {});

/** Short messages after saving ("Saved GH₵50.00 expense to Staples"), with an optional Undo. */
export function Toaster({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const push = useCallback<Push>((text, opts = {}) => {
    const id = Date.now() + Math.random();
    setItems((xs) => [...xs, { id, text, tone: opts.tone, action: opts.action }]);
    setTimeout(() => setItems((xs) => xs.filter((x) => x.id !== id)), opts.ms ?? (opts.action || opts.tone ? 8000 : 3500));
  }, []);
  return (
    <Ctx.Provider value={push}>
      {children}
      <div className="toasts" role="status" aria-live="polite">
        {items.map((t) => (
          <div key={t.id} className={`toast ${t.tone ?? ""}`}>
            <span>{t.text}</span>
            {t.action ? (
              <button type="button" onClick={() => {
                t.action!.run();
                setItems((xs) => xs.filter((x) => x.id !== t.id));
              }}>{t.action.label}</button>
            ) : null}
          </div>
        ))}
      </div>
    </Ctx.Provider>
  );
}

export function useToast(): Push {
  return useContext(Ctx);
}
