import { ArrowRight, Hammer, HeartHandshake, Mail, Wallet } from "lucide-react";
import Link from "next/link";
import { Icon3D } from "@/components/ui/icon3d";
import { Reveal } from "@/components/ui/reveal";
import { involvedBand } from "@/lib/site-content";
import { Eyebrow } from "./parts";

/** Where each action goes. Every Donate button leads to /get-involved. */
const ACTIONS = {
  "Donate Now": { href: "/get-involved", icon: Wallet, tone: "ember" },
  Volunteer: { href: "/contact", icon: Hammer, tone: "moss" },
  Newsletters: { href: "/contact", icon: Mail, tone: "sky" },
  "Get Involved": { href: "/get-involved", icon: HeartHandshake, tone: "gold" },
} as const;

/** The Donate Now / Volunteer / Newsletters / Get Involved band, with the "Join the Alumni Movement" call back line. */
export function InvolvedBand({ heading: H = "h2" }: { heading?: "h2" | "h3" }) {
  const band = involvedBand();
  return (
    <section aria-labelledby="involved-title">
      <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {band.actions.map((label, i) => {
          const a = ACTIONS[label as keyof typeof ACTIONS];
          return (
            <li key={label}>
              <Reveal delay={i * 80} className="h-full">
                <Link
                  href={a.href}
                  className="group flex h-full min-h-20 items-center gap-4 rounded-card border border-line bg-surface p-4 shadow-resting transition-[box-shadow,transform] duration-200 hover:-translate-y-0.5 hover:shadow-lifted active:scale-[0.98] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink motion-reduce:transition-none"
                >
                  <Icon3D icon={a.icon} tone={a.tone} size="md" />
                  <span className="min-w-0 flex-1">
                    <span className="block text-caption font-semibold tracking-widest text-faint">0{i + 1}</span>
                    <span className="block text-body font-medium">{label}</span>
                  </span>
                  <ArrowRight className="size-4 shrink-0 text-faint transition-transform duration-200 group-hover:translate-x-0.5" aria-hidden />
                </Link>
              </Reveal>
            </li>
          );
        })}
      </ul>
      <div className="mt-4 flex flex-col gap-4 rounded-card border border-line bg-sunken/70 p-5 sm:flex-row sm:items-center sm:justify-between sm:p-6">
        <div className="min-w-0">
          <Eyebrow>Alumni Connect</Eyebrow>
          <H id="involved-title" className="mt-1 text-heading font-semibold">{band.title}</H>
          <p className="mt-1 text-small text-muted">{band.text}</p>
        </div>
        <Link
          href="/contact"
          className="inline-flex h-11 shrink-0 items-center justify-center gap-2 rounded-full bg-ink px-6 text-small font-medium text-white shadow-raised transition-[background-color,transform] duration-150 hover:bg-black active:scale-[0.98] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
        >
          {band.callBack} <ArrowRight className="size-4" aria-hidden />
        </Link>
      </div>
    </section>
  );
}
