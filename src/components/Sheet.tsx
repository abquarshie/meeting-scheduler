"use client";
import { useEffect, useRef, type ReactNode } from "react";
import { Icon } from "./icons";

/** A pop-up: a centred card on wide screens, a sheet from the bottom on phones. */
export function Sheet({ open, onClose, title, children }: {
  open: boolean; onClose: () => void; title: string; children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);
  return (
    <dialog ref={ref} className="sheet" aria-label={title} onClose={onClose}
      onClick={(e) => { if (e.target === ref.current) onClose(); }}>
      {open ? (
        <div className="sheet-body">
          <div className="sheet-head">
            <h2>{title}</h2>
            <button type="button" className="btn ghost" onClick={onClose} aria-label="Close"><Icon name="close" /></button>
          </div>
          {children}
        </div>
      ) : null}
    </dialog>
  );
}

/** "Delete X? You can undo this straight after." with Cancel and a button to go ahead. */
export function Confirm({ open, message, button = "Delete", onCancel, onConfirm, busy }: {
  open: boolean; message: ReactNode; button?: string; onCancel: () => void; onConfirm: () => void; busy?: boolean;
}) {
  return (
    <Sheet open={open} onClose={onCancel} title="Please confirm">
      <p style={{ marginTop: 0 }}>{message}</p>
      <div className="btns" style={{ justifyContent: "flex-end" }}>
        <button type="button" className="btn" onClick={onCancel}>Cancel</button>
        <button type="button" className="btn primary" onClick={onConfirm} disabled={busy}>{button}</button>
      </div>
    </Sheet>
  );
}
