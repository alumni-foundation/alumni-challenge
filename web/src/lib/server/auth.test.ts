import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest, NextResponse } from "next/server";
import { clearAuthCookies, isHttps, refreshTokens, setAuthCookies } from "./auth";

const PAIR = { access_token: "new-access", refresh_token: "new-refresh", token_type: "bearer" };
const json = (status: number, body: unknown = {}) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

let n = 0;
// The refresh cache is keyed by token and lives for the whole process, so each test uses its own.
const freshToken = () => `old-refresh-${n++}`;

describe("refreshTokens", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    process.env.API_URL = "http://api.test";
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });
  afterEach(() => vi.unstubAllGlobals());

  it("sends the refresh token to the API and returns the new pair", async () => {
    fetchMock.mockResolvedValue(json(200, PAIR));
    const token = freshToken();

    const result = await refreshTokens(token);

    expect(result).toEqual({ ok: true, tokens: PAIR });
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://api.test/api/v1/auth/refresh");
    expect(JSON.parse(init.body)).toEqual({ refresh_token: token });
  });

  it("makes ONE call when several requests find the access token expired at once", async () => {
    fetchMock.mockResolvedValue(json(200, PAIR));
    const token = freshToken();

    const results = await Promise.all([refreshTokens(token), refreshTokens(token), refreshTokens(token)]);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    for (const r of results) expect(r).toEqual({ ok: true, tokens: PAIR });
  });

  it("does not replay the old token: a late request still holding it gets the same new pair", async () => {
    // Replaying a used refresh token makes the API end every session, so this matters.
    fetchMock.mockResolvedValue(json(200, PAIR));
    const token = freshToken();

    await refreshTokens(token);
    const late = await refreshTokens(token);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(late).toEqual({ ok: true, tokens: PAIR });
  });

  it("reports a rejected token as invalid, and does not keep asking with it", async () => {
    fetchMock.mockResolvedValue(json(401, { error: { code: "unauthorized", message: "Invalid refresh token." } }));
    const token = freshToken();

    expect(await refreshTokens(token)).toEqual({ ok: false, reason: "invalid" });
    expect(await refreshTokens(token)).toEqual({ ok: false, reason: "invalid" });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("reports a server error as unavailable and allows another try", async () => {
    fetchMock.mockResolvedValueOnce(json(503)).mockResolvedValueOnce(json(200, PAIR));
    const token = freshToken();

    expect(await refreshTokens(token)).toEqual({ ok: false, reason: "unavailable" });
    // Let the failed attempt clear itself from the cache before retrying.
    await Promise.resolve();
    expect(await refreshTokens(token)).toEqual({ ok: true, tokens: PAIR });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("reports a network failure as unavailable, not as an expired session", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("fetch failed"));

    expect(await refreshTokens(freshToken())).toEqual({ ok: false, reason: "unavailable" });
  });
});

describe("cookie security follows the protocol the visitor used", () => {
  const req = (url: string, proto?: string) =>
    new NextRequest(url, { headers: proto ? { "x-forwarded-proto": proto } : {} });

  it("is secure for https, directly or via a proxy header", () => {
    expect(isHttps(req("https://example.org/"))).toBe(true);
    expect(isHttps(req("http://10.0.0.5:3000/", "https"))).toBe(true);
    expect(isHttps(req("http://10.0.0.5:3000/", "https, http"))).toBe(true);
  });

  it("is not secure for plain http", () => {
    expect(isHttps(req("http://localhost:3000/"))).toBe(false);
    expect(isHttps(req("http://localhost:3000/", "http"))).toBe(false);
  });

  it("sets and clears both cookies with the Secure flag only over https", () => {
    const pair = { access_token: "a", refresh_token: "r", token_type: "bearer" };
    for (const [r, expected] of [[req("https://example.org/"), true], [req("http://localhost:3000/"), false]] as const) {
      const set = NextResponse.json({});
      setAuthCookies(r, set, pair);
      const cleared = NextResponse.json({});
      clearAuthCookies(r, cleared);
      for (const res of [set, cleared]) {
        for (const name of ["ac_access", "ac_refresh"]) expect(res.cookies.get(name)?.secure ?? false).toBe(expected);
      }
    }
  });
});
