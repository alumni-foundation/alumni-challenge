/** Checks for a picture before it is uploaded. The server checks again and re-encodes it; this spares a slow failed upload. */

export const IMAGE_MAX_BYTES = 5 * 1024 * 1024;
export const IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp"];

/** A plain-words problem with this file, or null when it may be sent. */
export function imageProblem(file: { type: string; size: number }): string | null {
  if (!IMAGE_TYPES.includes(file.type)) return "Choose a JPEG, PNG or WebP picture.";
  if (file.size <= 0) return "That file is empty. Choose another picture.";
  if (file.size > IMAGE_MAX_BYTES) return "That picture is too large. Choose one under 5 MB.";
  return null;
}
