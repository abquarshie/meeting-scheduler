"use client";
// Calls to the Python function (api/py.py), which holds the scheduling rules and builds the documents. The browser
// sends the sign-in cookie with each call, and the function checks it.

export type PyResult<T> = ({ ok: true; message?: string } & T) | { ok: false; error: string };

async function read<T>(res: Response): Promise<PyResult<T>> {
  let data: Record<string, unknown> = {};
  try { data = await res.json(); } catch { /* not JSON: a crash or a timeout */ }
  if (res.status === 401) {
    window.location.href = "/login";
    return { ok: false, error: "Please sign in again." };
  }
  if (!res.ok || data.error) {
    return { ok: false, error: (data.error as string) ?? `The server didn't answer (${res.status}). Please try again.` };
  }
  return { ok: true, ...(data as T) };
}

export async function py<T = object>(op: string, body: unknown): Promise<PyResult<T>> {
  try {
    return await read<T>(await fetch(`/api/py?op=${op}`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    }));
  } catch {
    return { ok: false, error: "Couldn't reach the server. Check the connection and try again." };
  }
}

export async function pyGet<T = object>(op: string, params: Record<string, string | number | undefined>): Promise<PyResult<T>> {
  try {
    return await read<T>(await fetch(pyUrl(op, params)));
  } catch {
    return { ok: false, error: "Couldn't reach the server. Check the connection and try again." };
  }
}

/** Upload a file as the request body (a workbook PDF, a blank form, a backup). */
export async function pyUpload<T = object>(op: string, file: File, params: Record<string, string> = {}): Promise<PyResult<T>> {
  try {
    return await read<T>(await fetch(pyUrl(op, { ...params, name: file.name }), { method: "POST", body: file }));
  } catch {
    return { ok: false, error: "The upload didn't get through. Files over about 4 MB are too big for the server." };
  }
}

export function pyUrl(op: string, params: Record<string, string | number | undefined>): string {
  const q = new URLSearchParams({ op });
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== "") q.set(k, String(v));
  return `/api/py?${q.toString()}`;
}

/** Download a document. Fetched first so a refusal ("no blank S-89 uploaded") shows as a message, not a broken page. */
export async function download(op: string, params: Record<string, string | number | undefined>): Promise<PyResult<object>> {
  try {
    const res = await fetch(pyUrl(op, params));
    const type = res.headers.get("Content-Type") ?? "";
    if (!res.ok || type.startsWith("application/json") && op !== "backup") return read(res);
    const blob = await res.blob();
    const disposition = res.headers.get("Content-Disposition") ?? "";
    const name = decodeURIComponent(/filename\*=UTF-8''([^;]+)/.exec(disposition)?.[1] ?? "download");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 10_000);
    return { ok: true, message: `Downloaded ${name}.` };
  } catch {
    return { ok: false, error: "Couldn't reach the server. Check the connection and try again." };
  }
}
