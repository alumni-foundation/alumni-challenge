import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { POST as login } from "@/app/api/auth/login/route";
import { POST as register } from "@/app/api/auth/register/route";
import { POST as forgot } from "@/app/api/auth/forgot-password/route";
import { GET as file } from "@/app/api/v1/files/[id]/content/route";
import { visitorHeaders, visitorIp } from "./visitor";

const h = (o: Record<string, string>) => new Headers(o);

describe("visitorIp", () => {
  afterEach(() => vi.unstubAllEnvs());

  it("in production believes only CF-Connecting-IP", () => {
    vi.stubEnv("NODE_ENV", "production");
    expect(visitorIp(h({ "cf-connecting-ip": "203.0.113.9" }))).toBe("203.0.113.9");
    expect(visitorIp(h({ "cf-connecting-ip": "2001:db8::1" }))).toBe("2001:db8::1");
    expect(visitorIp(h({ "x-forwarded-for": "198.51.100.7", "x-visitor-ip": "198.51.100.8" }))).toBeNull();
    expect(visitorIp(h({}))).toBeNull();
  });

  it("in development uses the connection address Next records", () => {
    vi.stubEnv("NODE_ENV", "development");
    expect(visitorIp(h({ "x-forwarded-for": "::1" }))).toBe("::1");
    expect(visitorIp(h({ "x-visitor-ip": "198.51.100.8" }))).toBeNull();
  });

  it("drops anything that is not an address", () => {
    vi.stubEnv("NODE_ENV", "production");
    expect(visitorIp(h({ "cf-connecting-ip": "1.2.3.4, evil" }))).toBeNull();
    expect(visitorIp(h({ "cf-connecting-ip": "<script>" }))).toBeNull();
    expect(visitorHeaders(h({ "cf-connecting-ip": "nope" }))).toEqual({});
  });
});

describe("a spoofed X-Visitor-IP from the browser", () => {
  const fetchMock = vi.fn();
  const ID = "43e3976c-4c8d-4f47-8238-913e2b6a2b2a";

  beforeEach(() => {
    process.env.API_URL = "http://api.test";
    vi.stubEnv("NODE_ENV", "production");
    fetchMock.mockReset();
    fetchMock.mockImplementation(async () => new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  const post = (path: string, headers: Record<string, string>) =>
    new NextRequest(`http://web.test${path}`, {
      method: "POST",
      headers: { origin: "http://web.test", host: "web.test", "content-type": "application/json", ...headers },
      body: "{}",
    });
  const sent = () => new Headers(fetchMock.mock.calls[0][1].headers as Record<string, string>).get("x-visitor-ip");

  const routes: [string, (r: NextRequest) => Promise<Response>, string][] = [
    ["login", login, "/api/auth/login"],
    ["register", register, "/api/auth/register"],
    ["forgot password", forgot, "/api/auth/forgot-password"],
  ];
  for (const [name, handler, path] of routes) {
    it(`is ignored on ${name}: the API gets Cloudflare's address`, async () => {
      await handler(post(path, { "x-visitor-ip": "6.6.6.6", "cf-connecting-ip": "203.0.113.9" }));
      expect(sent()).toBe("203.0.113.9");
    });
    it(`is ignored on ${name}: with no Cloudflare header the API gets none`, async () => {
      await handler(post(path, { "x-visitor-ip": "6.6.6.6", "x-forwarded-for": "6.6.6.7" }));
      expect(sent()).toBeNull();
    });
  }

  it("is ignored on the file proxy", async () => {
    await file(
      new NextRequest(`http://web.test/api/v1/files/${ID}/content`, { headers: { "x-visitor-ip": "6.6.6.6" } }),
      { params: Promise.resolve({ id: ID }) },
    );
    expect(sent()).toBeNull();
  });
});
