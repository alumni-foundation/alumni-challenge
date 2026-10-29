import Link from "next/link";
import { Logo } from "@/components/shell/logo";
import { site } from "@/lib/site";

const COLUMNS = [
  {
    title: "Explore",
    links: [
      { href: "/schools", label: "Schools" },
      { href: "/partners", label: "Partners" },
    ],
  },
  {
    title: "Join in",
    links: [
      { href: "/register", label: "Create an account" },
      { href: "/login", label: "Log in" },
    ],
  },
  {
    title: "Good to know",
    links: [
      { href: "/community-rules", label: "Community rules" },
      { href: "/terms", label: "Terms" },
      { href: "/privacy", label: "Privacy" },
      { href: "/contact", label: "Contact" },
    ],
  },
];

export function PublicFooter() {
  return (
    <footer className="mt-20 border-t border-line bg-sunken/60">
      <div className="mx-auto grid max-w-6xl gap-10 px-4 py-12 sm:px-6 md:grid-cols-[1.4fr_repeat(3,1fr)]">
        <div className="max-w-xs">
          <Logo variant="full" size={48} alt="Alumni Challenge" />
          <p className="mt-3 text-small text-muted">Where alumni of Kenyan schools meet, connect and belong.</p>
        </div>
        {COLUMNS.map((c) => (
          <nav key={c.title} aria-label={c.title}>
            <h2 className="text-caption font-semibold uppercase tracking-widest text-faint">{c.title}</h2>
            <ul className="mt-2">
              {c.links.map((l) => (
                <li key={l.href}>
                  <Link href={l.href} className="inline-flex min-h-11 items-center text-small text-muted hover:text-ink hover:underline">{l.label}</Link>
                </li>
              ))}
            </ul>
          </nav>
        ))}
      </div>
      <div className="border-t border-line">
        <p className="mx-auto max-w-6xl px-4 py-5 text-caption text-faint sm:px-6">© {new Date().getFullYear()} {site.name}</p>
      </div>
    </footer>
  );
}
