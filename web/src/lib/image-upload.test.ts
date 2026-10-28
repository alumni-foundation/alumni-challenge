import { describe, expect, it } from "vitest";
import { IMAGE_MAX_BYTES, imageProblem } from "./image-upload";

describe("imageProblem", () => {
  it("accepts JPEG, PNG and WebP up to 5 MB", () => {
    for (const type of ["image/jpeg", "image/png", "image/webp"]) {
      expect(imageProblem({ type, size: 1024 })).toBeNull();
    }
    expect(imageProblem({ type: "image/png", size: IMAGE_MAX_BYTES })).toBeNull();
  });

  it("refuses other types, whatever the file is called", () => {
    for (const type of ["image/gif", "image/svg+xml", "application/pdf", "text/html", ""]) {
      expect(imageProblem({ type, size: 1024 })).toMatch(/JPEG, PNG or WebP/);
    }
  });

  it("refuses a file over 5 MB, by a single byte too", () => {
    expect(imageProblem({ type: "image/jpeg", size: IMAGE_MAX_BYTES + 1 })).toMatch(/under 5 MB/);
  });

  it("refuses an empty file", () => {
    expect(imageProblem({ type: "image/jpeg", size: 0 })).toMatch(/empty/);
  });

  it("names the type problem before the size problem", () => {
    expect(imageProblem({ type: "image/gif", size: IMAGE_MAX_BYTES + 1 })).toMatch(/JPEG, PNG or WebP/);
  });
});
