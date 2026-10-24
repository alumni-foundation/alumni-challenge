import { ArrowRight, Building2, Handshake } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { PublicHeader } from "@/components/public/header";
import { Icon3D } from "@/components/ui/icon3d"; // direct import: the ui index is a client module
import hero from "@/assets/hero.jpg";
import { cn } from "@/lib/utils";

export type HeroStat = { icon: React.ElementType; tone: "ember" | "gold" | "sky"; value: string; label: string };

// The one place the photo's text colours are decided. White on these overlays holds AA (4.5:1) even if
// the picture behind is pure white: the left-hand scrim is at least 68% dark under the whole text column (it is sized from the page centre, so it follows the column on wide screens),
// the stat bar is 68% dark and frosted. Keep that true when swapping in a real photo.
const pillOnPhoto =
  "inline-flex h-12 items-center justify-center gap-2 rounded-full px-7 text-body font-medium transition-[background-color,transform] duration-150 active:scale-[0.98]";

/** The photo, edge to edge, with the nav, headline, buttons and a frosted stat bar on top. */
export function Hero({ signedIn, stats }: { signedIn: boolean; stats: HeroStat[] }) {
  return (
    <section className="relative isolate flex min-h-[44rem] flex-col overflow-hidden bg-side text-white sm:min-h-[48rem] lg:min-h-[100svh]">
      <Image
        src={hero}
        alt=""
        fill
        sizes="100vw"
        quality={60}
        placeholder="blur"
        loading="eager"
        fetchPriority="high"
        className="-z-20 object-cover object-[70%_50%]"
      />
      {/* Darkening only where there is text: a scrim on the left on wide screens, from the bottom on phones. */}
      <div
        aria-hidden
        className="absolute inset-0 -z-10 bg-[linear-gradient(0deg,rgb(14_10_6/0.84)_0%,rgb(14_10_6/0.76)_70%,rgb(14_10_6/0.66)_100%)] sm:hidden"
      />

      <PublicHeader overlay />

      <div className="mx-auto flex w-full max-w-6xl flex-1 flex-col justify-center px-4 pb-10 pt-36 sm:px-6 lg:px-10 lg:pt-32">
        <div className="relative max-w-3xl">
          <div
            aria-hidden
            className="absolute -inset-y-28 -left-[100vw] -right-36 -z-10 hidden bg-[rgb(14_10_6/0.72)] blur-[40px] sm:block"
          />
          <h1 className="text-hero font-semibold text-white">
            Where alumni of Kenyan schools meet, <em className="accent-serif">connect</em> and <em className="accent-serif">belong</em>.
          </h1>
          <p className="mt-5 max-w-xl text-lead text-white/90">
            Find classmates, stay close to your school, and keep the community that shaped you.
          </p>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <Link href={signedIn ? "/start" : "/register"} className={cn(pillOnPhoto, "bg-brand text-white shadow-lifted hover:bg-brand-dark")}>
              {signedIn ? "Open my home" : "Get started"} <ArrowRight className="size-4" aria-hidden />
            </Link>
            {signedIn ? (
              <Link href="#schools" className={cn(pillOnPhoto, "border border-white/50 text-white hover:bg-white/10")}>See schools</Link>
            ) : (
              <Link href="/login" className={cn(pillOnPhoto, "border border-white/50 text-white hover:bg-white/10")}>Log in</Link>
            )}
          </div>
        </div>
      </div>

      {stats.length > 0 && (
        <div className="mx-auto w-full max-w-6xl px-4 pb-6 sm:px-6 sm:pb-8 lg:px-10">
          <dl className="grid w-full max-w-lg grid-cols-2 divide-x divide-white/20 rounded-sheet border border-white/15 bg-[rgb(20_14_8/0.68)] py-4 backdrop-blur-xl sm:py-5">
            {stats.map((s) => (
              <div key={s.label} className="flex flex-col items-center gap-2 px-3 text-center">
                <Icon3D icon={s.icon} tone={s.tone} size="sm" />
                <dd className="text-heading font-semibold leading-none text-white">{s.value}</dd>
                <dt className="text-caption text-white/90">{s.label}</dt>
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
