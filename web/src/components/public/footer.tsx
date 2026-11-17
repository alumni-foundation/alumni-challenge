import Link from "next/link";
import { Logo } from "@/components/shell/logo";
import { contact } from "@/lib/site-info";
import { site } from "@/lib/site";

/** The same places as the top menu, in the same order. */
const QUICK_LINKS = [
  { href: "/", label: "Home" },
  { href: "/about", label: "About us" },
  { href: "/our-story", label: "Our story" },
  { href: "/team", label: "The team" },
  { href: "/programs", label: "Programs" },
  { href: "/schools", label: "Schools" },
  { href: "/partners", label: "Partners" },
  { href: "/get-involved", label: "Get involved" },
  { href: "/blog", label: "Blog" },
  { href: "/contact", label: "Contact" },
];

const LEGAL = [
  { href: "/community-rules", label: "Community rules" },
  { href: "/terms", label: "Terms" },
  { href: "/privacy", label: "Privacy" },
];

const heading = "text-caption font-semibold uppercase tracking-widest text-faint";
const link = "inline-flex min-h-11 items-center text-small text-muted hover:text-ink hover:underline";

export function PublicFooter() {
  return (
    <footer className="mt-20 border-t border-line bg-sunken/60">
      <div className="mx-auto grid max-w-6xl gap-10 px-4 py-12 sm:px-6 md:grid-cols-2 lg:grid-cols-[1fr_1.1fr_1.5fr_1fr]">
        <div className="max-w-xs">
          <Logo variant="full" size={48} alt="Alumni Challenge" />
          <p className="mt-3 text-small text-muted">Where alumni of Kenyan schools meet, connect and belong.</p>
        </div>

        <nav aria-label="Quick links">
          <h2 className={heading}>Quick links</h2>
          <ul className="mt-2 grid grid-cols-2">
            {QUICK_LINKS.map((l) => (
              <li key={l.href}><Link href={l.href} className={link}>{l.label}</Link></li>
            ))}
          </ul>
        </nav>

        <div>
          <h2 className={heading}>Contact</h2>
          <address className="mt-3 text-small not-italic text-muted">
            {contact.address.map((l) => <span key={l} className="block">{l}</span>)}
          </address>
          <ul className="mt-1">
            <li><a href={contact.phoneHref} className={link}>{contact.phone}</a></li>
            <li><a href={`mailto:${contact.email}`} className={`${link} [overflow-wrap:anywhere]`}>{contact.email}</a></li>
          </ul>
        </div>

        <div>
          <h2 className={heading}>Opening hours</h2>
          <dl className="mt-3 space-y-1 text-small text-muted">
            {contact.hours.map((h) => (
              <div key={h.days} className="flex gap-3"><dt className="min-w-20">{h.days}</dt><dd>{h.time}</dd></div>
            ))}
          </dl>
          <h2 className={`${heading} mt-6`}>Newsletter</h2>
          <Link href="/contact" className={`${link} mt-1 text-brand-ink`}>Join our newsletter for latest Updates</Link>
        </div>
      </div>

      <div className="border-t border-line">
        <div className="mx-auto flex max-w-6xl flex-col gap-3 px-4 py-5 sm:px-6 md:flex-row md:items-center md:justify-between">
          <p className="text-caption text-faint">© {new Date().getFullYear()} {site.name}</p>
          <ul className="flex flex-wrap gap-x-4 text-caption text-faint" aria-label="Legal">
            {LEGAL.map((l) => (
              <li key={l.href}><Link href={l.href} className="inline-flex min-h-11 items-center hover:text-ink hover:underline md:min-h-0">{l.label}</Link></li>
            ))}
          </ul>
          <p className="inline-flex w-fit items-center rounded-full border border-line px-2.5 py-0.5 text-caption text-faint">System by Vancelle Baraza</p>
        </div>
      </div>
    </footer>
  );
}
