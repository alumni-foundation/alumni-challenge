import { HeartHandshake, Search, Trophy } from "lucide-react";
import Link from "next/link";
import { OrgGrid } from "@/components/public/org";
import { LinkButton } from "@/components/ui";
import { hasSession } from "@/lib/server/auth";
import { fetchOrgs } from "@/lib/server/public-api";

const POINTS = [
  {
    icon: Search,
    title: "Find your people",
    body: "Look up classmates and fellow alumni by school, year, country or what they do now.",
  },
  {
    icon: HeartHandshake,
    title: "Stay close to your school",
    body: "Verified alumni, school staff and partners in one trusted place, with you in control of who sees what.",
  },
  {
    icon: Trophy,
    title: "Meet in person",
    body: "Events bring the community together. Golf tournaments come first, and more will follow.",
  },
];

export default async function Home() {
  const [schools, partners, signedIn] = await Promise.all([fetchOrgs("school"), fetchOrgs("partner"), hasSession()]);
  return (
    <div className="space-y-16">
      <section className="max-w-2xl">
        <h1 className="text-display">Where alumni of Kenyan schools meet, connect and belong.</h1>
        <p className="mt-4 text-lead text-muted">
          Reconnect with the people you shared a school with, and stay part of the community that shaped you.
        </p>
        <div className="mt-6 flex flex-col gap-3 sm:flex-row">
          {signedIn ? (
            <LinkButton href="/start" className="sm:min-w-40">Open my home</LinkButton>
          ) : (
            <>
              <LinkButton href="/register" className="sm:min-w-40">Sign up</LinkButton>
              <LinkButton href="/login" variant="secondary" className="sm:min-w-40">Log in</LinkButton>
            </>
          )}
        </div>
      </section>

      <section aria-labelledby="why" className="grid gap-4 sm:grid-cols-3">
        <h2 id="why" className="sr-only">What you can do</h2>
        {POINTS.map(({ icon: Icon, title, body }) => (
          <div key={title} className="rounded-card border border-line bg-surface p-5">
            <span className="inline-flex size-10 items-center justify-center rounded-xl bg-brand-soft text-brand-ink">
              <Icon className="size-[18px]" aria-hidden />
            </span>
            <h3 className="mt-4 text-heading">{title}</h3>
            <p className="mt-1 text-small text-muted">{body}</p>
          </div>
        ))}
      </section>

      <section aria-labelledby="schools">
        <div className="mb-4 flex items-end justify-between gap-3">
          <h2 id="schools" className="text-heading">Schools</h2>
          <Link href="/schools" className="inline-flex min-h-11 items-center text-small font-medium text-brand-ink hover:underline">See all</Link>
        </div>
        <OrgGrid orgs={schools?.slice(0, 6) ?? null} base="/schools" noun="schools" />
      </section>

      <section aria-labelledby="partners">
        <div className="mb-4 flex items-end justify-between gap-3">
          <h2 id="partners" className="text-heading">Partners</h2>
          <Link href="/partners" className="inline-flex min-h-11 items-center text-small font-medium text-brand-ink hover:underline">See all</Link>
        </div>
        <OrgGrid orgs={partners?.slice(0, 6) ?? null} base="/partners" noun="partners" />
      </section>

      {!signedIn && (
        <section className="rounded-sheet bg-side p-6 text-white sm:p-10">
          <h2 className="text-title">Ready to find your school family?</h2>
          <p className="mt-2 max-w-xl text-white/75">Creating an account is free and takes about a minute.</p>
          <LinkButton href="/register" className="mt-5">Join the alumni network</LinkButton>
        </section>
      )}
    </div>
  );
}
