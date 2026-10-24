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

/** Only same-site paths are allowed as a "next" target, so a link can't bounce people elsewhere. */
export function safeNext(value: string | null): string | null {
  return value && value.startsWith("/") && !value.startsWith("//") && !value.startsWith("/\\") ? value : null;
}

type Sent = { method?: string; body?: unknown; form?: FormData; headers?: Record<string, string> };

async function request(path: string, init: Sent): Promise<{ res: Response; data: unknown }> {
  let res: Response;
  try {
    res = await fetch(`/api/backend/${path}`, {
      method: init.method ?? "GET",
      // A FormData body sets its own content type (with the multipart boundary).
      headers: init.body !== undefined || init.headers ? { ...(init.body !== undefined ? { "content-type": "application/json" } : {}), ...init.headers } : undefined,
      body: init.form ?? (init.body !== undefined ? JSON.stringify(init.body) : undefined),
    });
  } catch {
    throw new ApiError(0, "network", "Can't reach the server. Check your connection.");
  }
  const data = await parse(res);
  if (res.status === 401 && typeof window !== "undefined") {
    // The proxy already tried the refresh token once. A 401 here means the session is over.
    const here = window.location.pathname + window.location.search;
    window.location.assign(`/login?reason=expired&next=${encodeURIComponent(here)}`);
  }
  if (!res.ok) throw toError(res, data);
  return { res, data };
}

/** Calls the backend through the same-origin proxy. Tokens never reach browser JavaScript. */
export async function api<T>(path: string, init: { method?: string; body?: unknown; headers?: Record<string, string> } = {}): Promise<T> {
  return (await request(path, init)).data as T;
}

/** A list plus the API's count of everything that matched (it stops counting at 10,000). */
export async function apiPage<T>(path: string): Promise<{ items: T[]; total: number | null }> {
  const { res, data } = await request(path, {});
  const header = res.headers.get("x-total-count");
  return { items: data as T[], total: header === null ? null : Number(header) };
}

/** Uploads one file (multipart). The caller adds the fields, such as `purpose`. */
export async function apiUpload<T>(path: string, form: FormData): Promise<T> {
  return (await request(path, { method: "POST", form })).data as T;
}

/** For the auth routes that set or clear cookies, or that work without a session. */
export async function authCall(
  path: "login" | "register" | "logout" | "forgot-password" | "reset-password" | "verify-email",
  body?: unknown,
): Promise<unknown> {
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

/** True when a session cookie is valid. Unlike api(), a "no" is not treated as an expired session. */
export async function isSignedIn(): Promise<boolean> {
  try {
    const res = await fetch("/api/backend/auth/me");
    return res.ok;
  } catch {
    return false;
  }
}
