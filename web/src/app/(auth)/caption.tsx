"use client";

import { usePathname } from "next/navigation";

// One short line, and only things that are true today: no dates, no numbers.
const CAPTIONS: Record<string, string> = {
  "/register": "Find the people you went to school with.",
};
const DEFAULT = "From classmates to the first tee.";

/** The frosted caption over the photo (large screens only). Dark glass, white text, kept AA over any picture. */
export function AuthCaption() {
  const path = usePathname();
  return (
    <p className="absolute bottom-8 left-[5vw] hidden max-w-xs rounded-[1.25rem] border border-white/25 bg-[rgb(20_14_8/0.68)] px-6 py-4 text-lead font-medium leading-snug text-white shadow-lifted backdrop-blur-md lg:block">
      {CAPTIONS[path] ?? DEFAULT}
    </p>
  );
}
