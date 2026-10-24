import { ArrowRight, Building2, Handshake } from "lucide-react";
import { getImageProps } from "next/image";
import Link from "next/link";
import { PublicHeader } from "@/components/public/header";
import { Icon3D } from "@/components/ui/icon3d"; // direct import: the ui index is a client module
import heroLight from "@/assets/hero-group.jpg";
import { cn } from "@/lib/utils";

export type HeroStat = { icon: React.ElementType; tone: "ember" | "gold" | "sky"; value: string; label: string };

/** Counts below this say "we are small" rather than "we are a community", so the strip stays hidden. */
export const MIN_STAT = 10;

const pill =
  "inline-flex h-12 items-center justify-center gap-2 rounded-full px-7 text-body font-medium transition-[background-color,transform] duration-150 active:scale-[0.98]";

/**
 * The hero. The text sits on the page colour; the photo stands on the page, anchored bottom-right on
 * wide screens and under the text on phones. Readability does not depend on the picture: a scrim in the
 * page colour runs from the text side and fades out toward the people, and the photo fades into the
 * page at its top and bottom. Contrast is measured against the worst pixels behind the text, not eyeballed.
 */
export function Hero({ signedIn, stats }: { signedIn: boolean; stats: HeroStat[] }) {
  const common = { alt: "", sizes: "(min-width: 1024px) 48vw, 100vw", quality: 70, loading: "eager" as const, fetchPriority: "high" as const };
  const light = getImageProps({ ...common, src: heroLight, placeholder: "blur" }).props;

  return (
    <section className="relative isolate overflow-hidden bg-canvas">
      <PublicHeader bare />

      <div className="relative flex flex-col lg:block lg:h-[min(53.4vw,56rem)]">
        {/* The photo. pointer-events-none so it can never sit on top of a button. */}
        <picture className="pointer-events-none mix-blend-multiply relative order-2 -z-10 -mt-24 block aspect-[576/641] w-full sm:mx-auto sm:max-w-lg lg:absolute lg:bottom-0 lg:right-0 lg:mt-0 lg:w-[min(48vw,780px)] lg:max-w-none">
          <img {...light} alt="" className="hero-photo size-full object-cover" />
        </picture>

        {/* Scrim: the page colour, solid behind the text, fading to nothing toward the people. */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 hidden bg-[linear-gradient(90deg,var(--canvas)_0%,var(--canvas)_36%,transparent_60%)] lg:block"
        />

        <div className="relative z-10 order-1 mx-auto flex w-full lg:h-full max-w-6xl flex-col justify-start px-4 pt-8 sm:px-6 lg:justify-center lg:px-10 lg:pt-0">
          <div className="max-w-xl lg:max-w-[min(34rem,50%)]">
            <h1 className="text-hero font-semibold text-ink">
              Where alumni of Kenyan schools meet, <em className="accent-serif">connect</em> and <em className="accent-serif">belong</em>.
            </h1>
            <p className="mt-5 max-w-md text-lead text-muted">
              Find classmates, stay close to your school, and keep the community that shaped you.
            </p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Link href={signedIn ? "/start" : "/register"} className={cn(pill, "bg-brand text-white shadow-raised hover:bg-brand-dark")}>
                {signedIn ? "Open my home" : "Get started"} <ArrowRight className="size-4" aria-hidden />
              </Link>
              <Link href={signedIn ? "#schools" : "/login"} className={cn(pill, "border border-line-strong text-ink hover:bg-sunken")}>
                {signedIn ? "See schools" : "Log in"}
              </Link>
            </div>
          </div>
        </div>
      </div>

      {stats.length > 0 && (
        <div className="relative z-10 mx-auto w-full max-w-6xl px-4 pb-6 sm:px-6 lg:px-10">
          <dl className="grid w-full max-w-lg grid-cols-2 divide-x divide-line rounded-sheet border border-line bg-surface/80 py-4 shadow-resting backdrop-blur-xl sm:py-5">
            {stats.map((s) => (
              <div key={s.label} className="flex flex-col items-center gap-2 px-3 text-center">
                <Icon3D icon={s.icon} tone={s.tone} size="sm" />
                <dd className="text-heading font-semibold leading-none text-ink">{s.value}</dd>
                <dt className="text-caption text-muted">{s.label}</dt>
              </div>
            ))}
          </dl>
        </div>
      )}
    </section>
  );
}

/** "12" for twelve schools; "100+" when the list we asked for was cut off at its limit. */
export function countLabel(n: number, limit = 100): string {
  return n >= limit ? `${limit}+` : String(n);
}

export const SCHOOL_STAT = { icon: Building2, tone: "ember" } as const;
export const PARTNER_STAT = { icon: Handshake, tone: "gold" } as const;
