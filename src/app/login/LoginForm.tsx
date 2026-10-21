"use client";
import { useActionState } from "react";
import { signInAction } from "@/actions/session";

export function LoginForm({ next }: { next: string }) {
  const [error, act, busy] = useActionState(signInAction, null);
  return (
    <form action={act} className="form">
      <input type="hidden" name="next" value={next} />
      <label className="field"><span>Your name</span>
        <input className="input" name="name" autoComplete="name" required />
      </label>
      <label className="field"><span>Password</span>
        <input className="input" name="password" type="password" autoComplete="current-password" required />
      </label>
      {error ? <div className="msg error">{error}</div> : null}
      <button className="btn primary" disabled={busy}>Sign in</button>
    </form>
  );
}
