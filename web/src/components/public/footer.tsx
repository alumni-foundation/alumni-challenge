import Link from "next/link";
import { site } from "@/lib/site";

const LINKS = [
  { href: "/terms", label: "Terms" },
  { href: "/privacy", label: "Privacy" },
  { href: "/community-rules", label: "Community rules" },
  { href: "/contact", label: "Contact" },
];

export function PublicFooter() {
  return (
    <footer className="mt-16 border-t border-line bg-surface">
      <div className="mx-auto flex max-w-5xl flex-col gap-4 px-4 py-8 text-small text-muted sm:flex-row sm:items-center sm:justify-between sm:px-6">
        <p>© {site.name}</p>
        <nav aria-label="Legal and help" className="flex flex-wrap gap-x-5">
          {LINKS.map((l) => (
            <Link key={l.href} href={l.href} className="inline-flex min-h-11 items-center hover:text-ink hover:underline">{l.label}</Link>
          ))}
        </nav>
      </div>
    </footer>
  );
}
