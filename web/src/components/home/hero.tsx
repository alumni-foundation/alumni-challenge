import { BadgeCheck, Search } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import hero from "@/assets/hero.jpg";

type Props = {
  /** First name, or undefined while the profile loads. */
  name?: string;
  /** Real numbers; null while they load. */
  connections: number | null;
  waiting: number | null;
  verified: boolean | null;
};

function line({ connections, waiting }: Pick<Props, "connections" | "waiting">): string {
  if (waiting) return `${waiting === 1 ? "Someone is" : `${waiting} people are`} waiting to connect with you.`;
  if (connections === 0) return "Start with the people you shared a school with.";
  return "See who is here, and keep in touch with your school family.";
}

/** One cell of the stat strip: a big gold number (or a calm phrase when there is nothing to count yet) and a label. */
function Stat({ value, empty, label }: { value: number | null; empty: string; label: string }) {
  return (
    <div className="flex flex-col items-center justify-center px-2 text-center">
      {value === null ? (
        <span className="h-8 w-10 animate-pulse rounded-md bg-white/20" aria-label="Loading" />
      ) : value === 0 ? (
        <span className="text-lead font-semibold leading-8 text-white">{empty}</span>
      ) : (
        <span className="font-serif text-[2rem] font-semibold leading-8 text-[#ecc98f] [font-variant-numeric:lining-nums]">{value}</span>
      )}
      <span className="mt-2 text-caption font-medium text-white/90">{label}</span>
    </div>
  );
}

/**
 * The Home hero: a photograph in a rounded card with a scrim only under the text, white text, and a frosted
 * strip of real numbers along the bottom. The scrim keeps the text at AA over any picture (measured in the
 * browser against the worst pixels), so keep it if the photo is swapped.
 */
export function HomeHero({ name, connections, waiting, verified }: Props) {
  return (
    <section aria-label="Welcome" className="relative isolate flex h-full min-h-[29rem] flex-col overflow-hidden rounded-[1.75rem] bg-side text-white shadow-lifted sm:rounded-[2.25rem] lg:min-h-[28rem]">
      <Image
        src={hero}
        alt=""
        fill
        sizes="(min-width: 1024px) 1100px, 100vw"
        quality={70}
        placeholder="blur"
        loading="eager"
        fetchPriority="high"
        className="-z-20 object-cover object-[88%_30%]"
      />
      <div
        aria-hidden
        className="absolute inset-0 -z-10 bg-[linear-gradient(180deg,rgb(14_10_6/0.82),rgb(14_10_6/0.6))] lg:bg-transparent lg:bg-[linear-gradient(90deg,rgb(14_10_6/0.78)_0,rgb(14_10_6/0.7)_520px,rgb(14_10_6/0)_calc(520px+14vw))]"
      />

      <div className="flex-1 px-6 pb-36 pt-9 sm:px-10 sm:pt-12 lg:pb-40">
        <div className="max-w-lg">
          <h1 className="text-hero font-medium text-white [font-size:clamp(2.25rem,1.4rem+2.4vw,3.25rem)]">
            Welcome back{name ? <>, <em className="accent-serif text-[#ecc98f]">{name}</em></> : null}.
          </h1>
          <p className="mt-4 max-w-sm text-lead text-white/90">{line({ connections, waiting })}</p>
          <Link
            href="/directory"
            className="mt-7 inline-flex h-12 items-center gap-2 rounded-full bg-[#1b1713] px-7 text-body font-medium text-white shadow-lifted ring-1 ring-white/15 transition-colors hover:bg-black focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
          >
            <Search className="size-4" aria-hidden /> Find alumni
          </Link>
        </div>
      </div>

      <div role="group" aria-label="Your numbers" className="hero-glass absolute inset-x-4 bottom-4 grid grid-cols-3 divide-x divide-white/20 rounded-3xl border border-white/20 py-4 sm:inset-x-6 sm:bottom-6 sm:py-5">
        <Stat value={connections} empty="None yet" label="Connections" />
        <Stat value={waiting} empty="None" label="Requests" />
        <div className="flex flex-col items-center justify-center px-2 text-center">
          {verified === null ? (
            <span className="h-8 w-16 animate-pulse rounded-md bg-white/20" aria-label="Loading" />
          ) : (
            <span className="inline-flex items-center gap-1.5 text-lead font-semibold leading-8 text-white">
              {verified && <BadgeCheck className="size-5 text-[#ecc98f]" aria-hidden />}
              {verified ? "Verified" : "Not yet"}
            </span>
          )}
          <span className="mt-2 text-caption font-medium text-white/90">Verification</span>
        </div>
      </div>
    </section>
  );
}
