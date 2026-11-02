import { describe, expect, it } from "vitest";
import { safeNext } from "./client";

describe("safeNext", () => {
  it.each([
    ["a tab after the slash", "/\t/evil.example"],
    ["a tab inside the path", "/a\tb"],
    ["a newline", "/\n/evil.example"],
    ["a carriage return", "/\r/evil.example"],
    ["a leading newline", "\n/admin"],
    ["a space", "/ /evil.example"],
    ["a non-breaking space", "/ /evil.example"],
    ["a line separator", "/ /evil.example"],
    ["a delete character", "/\u007f/evil.example"],
    ["two slashes", "//x"],
    ["a slash and a backslash", "/\\x"],
    ["a backslash inside the path", "/a\\b"],
    ["a full address", "https://x"],
    ["a script address", "javascript:x"],
    ["a relative path", "admin"],
    ["nothing", ""],
    ["null", null],
  ])("refuses %s", (_name, value) => {
    expect(safeNext(value)).toBeNull();
  });

  it.each(["/admin?x=1", "/directory", "/", "/school/abc/roster", "/events/abc?tab=past#top"])("keeps %s", (value) => {
    expect(safeNext(value)).toBe(value);
  });
});
