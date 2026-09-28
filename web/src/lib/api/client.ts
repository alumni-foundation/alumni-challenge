export type FieldIssue = { loc: (string | number)[]; msg: string; type?: string };

export class ApiError extends Error {
  status: number;
  code: string;
  details: FieldIssue[];
  constructor(status: number, code: string, message: string, details: FieldIssue[] = []) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
  /** Maps validation issues to { fieldName: message } for inline form errors. */
  fieldErrors(): Record<string, string> {
    const out: Record<string, string> = {};
    for (const d of this.details) {
      const key = String(d.loc[d.loc.length - 1] ?? "");
      if (key && !out[key]) out[key] = d.msg;
    }
    return out;
  }
}

async function parse(res: Response): Promise<unknown> {
  const text = await res.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

function toError(res: Response, data: unknown): ApiError {
  const err = (data as { error?: { code?: string; message?: string; details?: unknown } } | null)?.error;
  const details = Array.isArray(err?.details) ? (err.details as FieldIssue[]) : [];
  return new ApiError(
    res.status,
    err?.code ?? "error",
    err?.message ?? "Something went wrong. Please try again.",
    details,
  );
}

export function safeNext(value: string | null): string {
  return value && value.startsWith("/") && !value.startsWith("//") ? value : "/home";
}

/** Calls the backend through the same-origin proxy. Tokens never reach browser JavaScript. */
export async function api<T>(path: string, init: { method?: string; body?: unknown } = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api/backend/${path}`, {
      method: init.method ?? "GET",
      headers: init.body !== undefined ? { "content-type": "application/json" } : undefined,
      body: init.body !== undefined ? JSON.stringify(init.body) : undefined,
    });
  } catch {
    throw new ApiError(0, "network", "Can't reach the server. Check your connection.");
  }
  const data = await parse(res);
  if (res.status === 401 && typeof window !== "undefined") {
    const here = window.location.pathname + window.location.search;
    window.location.assign(`/login?next=${encodeURIComponent(here)}`);
  }
  if (!res.ok) throw toError(res, data);
  return data as T;
}

/** For the few routes that set or clear cookies (login, register, logout). */
export async function authCall(path: "login" | "register" | "logout", body?: unknown): Promise<unknown> {
  let res: Response;
  try {
    res = await fetch(`/api/auth/${path}`, {
      method: "POST",
      headers: body !== undefined ? { "content-type": "application/json" } : undefined,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError(0, "network", "Can't reach the server. Check your connection.");
  }
  const data = await parse(res);
  if (!res.ok) throw toError(res, data);
  return data;
}
