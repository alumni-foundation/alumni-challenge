import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { GET } from "./route";

const ID = "43e3976c-4c8d-4f47-8238-913e2b6a2b2a";
const call = (id: string, search = "") =>
  GET(new NextRequest(`http://web.test/api/v1/files/${id}/content${search}`), { params: Promise.resolve({ id }) });

describe("file content proxy", () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    process.env.API_URL = "http://api.test";
    fetchMock.mockReset();
    vi.stubGlobal("fetch", fetchMock);
  });
  afterEach(() => vi.unstubAllGlobals());

  it("streams the file with its status, type and cache headers, and sends no cookie or auth", async () => {
    fetchMock.mockResolvedValue(
      new Response("bytes", {
        status: 200,
        headers: { "content-type": "image/jpeg", "cache-control": "public, max-age=31536000, immutable", "set-cookie": "x=1" },
      }),
    );

    const res = await call(ID);

    expect(res.status).toBe(200);
    expect(res.headers.get("content-type")).toBe("image/jpeg");
    expect(res.headers.get("cache-control")).toBe("public, max-age=31536000, immutable");
    expect(res.headers.get("set-cookie")).toBeNull();
    expect(await res.text()).toBe("bytes");
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe(`http://api.test/api/v1/files/${ID}/content`);
    expect(init.headers?.authorization).toBeUndefined();
  });

  it("passes only the token query through", async () => {
    fetchMock.mockResolvedValue(new Response("b", { status: 200 }));
    await call(ID, "?token=abc.def&evil=1");
    expect(fetchMock.mock.calls[0][0]).toBe(`http://api.test/api/v1/files/${ID}/content?token=abc.def`);
  });

  it("passes a 404 through and never caches it", async () => {
    fetchMock.mockResolvedValue(new Response("nope", { status: 404, headers: { "cache-control": "public, max-age=60" } }));
    const res = await call(ID, "?token=expired");
    expect(res.status).toBe(404);
    expect(res.headers.get("cache-control")).toBe("no-store");
  });

  it("refuses an id that is not a file id without calling the API", async () => {
    const res = await call("..%2Fauth%2Fme");
    expect(res.status).toBe(404);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("answers 503 when the API is down", async () => {
    fetchMock.mockRejectedValue(new Error("down"));
    expect((await call(ID)).status).toBe(503);
  });
});
