import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { SAMPLE_CONVERSATIONS } from "./sample";

function files(dir: string): string[] {
  return readdirSync(dir).flatMap((n) => {
    const p = join(dir, n);
    return statSync(p).isDirectory() ? files(p) : /\.(tsx?|ts)$/.test(n) ? [p] : [];
  });
}

describe("sample conversations", () => {
  it("are marked as made up", () => {
    expect(SAMPLE_CONVERSATIONS.every((c) => c.with.full_name.startsWith("Sample"))).toBe(true);
  });

  it("are never imported by a page real people can open", () => {
    const root = join(process.cwd(), "src");
    const users = files(root).filter((f) => !/design-check|\.test\./.test(f) && /messages[\/]sample['"]|messages\/sample"/.test(readFileSync(f, "utf8")));
    expect(users.map((f) => f.replace(root, ""))).toEqual([]);
  });
});
