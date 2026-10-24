import { ArrowRight, Building2, Handshake, LogIn } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { PublicHeader } from "@/components/public/header";
import { Icon3D } from "@/components/ui/icon3d"; // direct import: the ui index is a client module
import hero from "@/assets/hero.jpg";

export type HeroStat = { icon: React.ElementType; tone: "ember" | "gold" | "sky"; value: string; label: string };

/** Counts below this say "we are small" rather than "we are a community", so the stat panel stays hidden. */
export const MIN_STAT = 10;

/**
 * A full-bleed photograph in a rounded card, with the nav, headline and buttons on top. White text
 * stays AA over any picture because of the scrim: dark warm, strongest under the text column and
 * fading out toward the right, or over the whole picture on phones. Keep that true when swapping the photo.
 */
export function Hero({ signedIn, stats }: { signedIn: boolean; stats: HeroStat[] }) {
  return (
    <section className="p-3 sm:p-4">
      <div className="relative isolate flex min-h-[44rem] flex-col overflow-hidden rounded-[1.75rem] bg-side text-white shadow-lifted sm:min-h-[46rem] sm:rounded-[2.25rem] lg:min-h-[max(42rem,calc(100svh-2rem))]">
        <Image
          src={hero}
          alt=""
          fill
          sizes="100vw"
          quality={60}
          placeholder="blur"
          loading="eager"
          fetchPriority="high"
          className="-z-20 object-cover object-[65%_50%]"
        />
        <div
          aria-hidden
          className="absolute inset-0 -z-10 bg-[rgb(14_10_6/0.76)] lg:bg-transparent lg:bg-[linear-gradient(90deg,rgb(14_10_6/0.8)_0,rgb(14_10_6/0.76)_640px,rgb(14_10_6/0)_calc(640px+24vw))]"
        />

        <PublicHeader overlay />

        <div className="flex flex-1 flex-col justify-center px-5 pb-10 pt-40 sm:px-8 lg:px-12 lg:pt-28">
          <div className="max-w-xl">
            <p className="inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-3.5 py-1.5 text-caption font-medium text-white backdrop-blur-md">
              <span className="size-1.5 rounded-full bg-[#e8c48a]" aria-hidden /> For alumni of Kenyan schools
            </p>
            <h1 className="mt-6 text-hero font-medium text-white">
              Where alumni<br />
              <em className="accent-serif text-[#ecc98f]">connect</em><br />
              and belong.
            </h1>
            <p className="mt-6 max-w-md text-lead text-white/90">
              Find classmates, stay close to your school, and keep the community that shaped you.
            </p>
            <div className="mt-9 flex flex-wrap items-center gap-x-6 gap-y-4">
              <Link
                href={signedIn ? "/start" : "/register"}
                className="inline-flex h-12 items-center gap-2 rounded-full bg-[#1b1713] px-7 text-body font-medium text-white shadow-lifted ring-1 ring-white/15 transition-colors hover:bg-black"
              >
                {signedIn ? "Open my home" : "Get started"} <ArrowRight className="size-4" aria-hidden />
              </Link>
              <Link href={signedIn ? "#schools" : "/login"} className="group inline-flex items-center gap-3 text-body font-medium text-white">
                <span className="grid size-12 place-items-center rounded-full border border-white/50 bg-white/10 backdrop-blur-md transition-colors group-hover:bg-white/20">
                  <LogIn className="size-4" aria-hidden />
                </span>
                {signedIn ? "See schools" : "Log in"}
              </Link>
            </div>
          </div>
        </div>

        {stats.length > 0 && (
          <div className="px-5 pb-6 sm:px-8 sm:pb-8 lg:px-12">
            <dl className="grid w-full max-w-md grid-cols-2 divide-x divide-white/20 rounded-sheet border border-white/20 bg-[rgb(20_14_8/0.5)] py-4 backdrop-blur-xl sm:py-5">
              {stats.map((s) => (
                <div key={s.label} className="flex flex-col items-center gap-2 px-3 text-center">
                  <Icon3D icon={s.icon} tone={s.tone} size="sm" />
                  <dd className="font-serif text-heading font-semibold leading-none text-white">{s.value}</dd>
                  <dt className="text-caption text-white/90">{s.label}</dt>
                </div>
              ))}
            </dl>
          </div>
        )}
      </div>
    </section>
  );
}

/** "12" for twelve schools; "100+" when the list we asked for was cut off at its limit. */
export function countLabel(n: number, limit = 100): string {
  return n >= limit ? `${limit}+` : String(n);
}

export const SCHOOL_STAT = { icon: Building2, tone: "ember" } as const;
export const PARTNER_STAT = { icon: Handshake, tone: "gold" } as const;
