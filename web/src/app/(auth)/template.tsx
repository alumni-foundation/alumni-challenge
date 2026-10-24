"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Logo } from "@/components/shell/logo";
import { cn } from "@/lib/utils";
import { AuthCaption } from "./caption";

/**
 * A template (not a layout) so it is created again on every navigation: the card, the Back to home pill and the
 * caption enter each time someone arrives, while the photo in the layout stays put between sign-in pages.
 * The entrance is CSS (see .auth-enter in globals.css). The class comes off after it has played, so a validation
 * error or typing never starts it again.
 */
export default function AuthTemplate({ children }: { children: React.ReactNode }) {
  const [entering, setEntering] = useState(true);
  useEffect(() => {
    const t = window.setTimeout(() => setEntering(false), 1200);
    return () => window.clearTimeout(t);
  }, []);

  return (
    <div className={cn("contents", entering && "auth-enter")}>
      {/* First in the tab order, before the logo and the form. Dark glass with white text, so it reads on any part of the photo. */}
      <Link
        href="/"
        className="auth-back-in absolute left-4 top-4 z-20 inline-flex h-11 items-center gap-2 rounded-full border border-white/25 bg-[rgb(20_14_8/0.68)] pl-3.5 pr-5 text-small font-medium text-white shadow-raised backdrop-blur-md transition-colors hover:bg-[rgb(20_14_8/0.85)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink sm:left-6 sm:top-6 lg:left-[5vw] lg:top-8"
      >
        <ArrowLeft className="size-4" aria-hidden /> Back to home
      </Link>

      <main id="main" className="relative z-10 -mt-8 flex flex-1 flex-col lg:mt-0 lg:w-[30rem] lg:flex-none">
        <div className="auth-card auth-card-in flex flex-1 flex-col rounded-t-[28px] px-5 pb-8 pt-7 sm:px-8 sm:pt-8 lg:flex-none lg:rounded-[28px] lg:shadow-lifted">
          <div className="mx-auto w-full max-w-md flex-1 lg:max-w-none lg:flex-none">
            <Link
              href="/"
              aria-label="Alumni Challenge home"
              className="mb-7 inline-flex items-center gap-2.5 rounded-full bg-ink py-2 pl-3 pr-5 text-white focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
            >
              <Logo size={26} tone="light" />
              <span className="text-caption font-semibold uppercase tracking-[0.16em]">Alumni Challenge</span>
            </Link>
            <div className="auth-stagger">{children}</div>
            <p className="mt-8 flex justify-center gap-4 border-t border-line pt-4 text-caption text-muted">
              <Link href="/terms" className="inline-flex min-h-8 items-center hover:text-ink hover:underline">Terms</Link>
              <Link href="/privacy" className="inline-flex min-h-8 items-center hover:text-ink hover:underline">Privacy</Link>
            </p>
          </div>
        </div>
      </main>

      <AuthCaption />
    </div>
  );
}
