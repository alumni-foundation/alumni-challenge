import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { Logo } from "@/components/shell/logo";
import { LinkButton } from "@/components/ui";
import { hasSession } from "@/lib/server/auth";
import { NavLinks, type NavItem } from "./nav-links";

const LINKS: NavItem[] = [
  { href: "/schools", label: "Schools" },
  { href: "/partners", label: "Partners" },
];

const overlayLink = "min-h-11 items-center px-4 text-small font-medium text-white/90 transition-colors hover:text-white aria-[current]:text-white";
const plainLink = "min-h-11 items-center px-4 text-small font-medium text-muted transition-colors hover:text-ink aria-[current]:text-ink";

/** Where the landing page's own sections are. A section that is not on the page sends the link to the full page. */
export type Anchors = { schools: boolean; partners: boolean };

/**
 * The bar on public pages. "overlay" sits on top of the landing hero: white text, links centred, and
 * a dark pill on the right. The hero's scrim keeps that text at AA contrast over any picture.
 */
export async function PublicHeader({ overlay = false, anchors = { schools: true, partners: true } }: { overlay?: boolean; anchors?: Anchors }) {
  const signedIn = await hasSession();
  const landingItems: NavItem[] = [
    { href: "/", label: "Home", section: "home" },
    { href: anchors.schools ? "/#schools" : "/schools", label: "Schools", section: "schools" },
    { href: anchors.partners ? "/#partners" : "/partners", label: "Partners", section: "partners" },
    { href: "/contact", label: "Contact" },
  ];

  if (overlay) {
    return (
      <header className="absolute inset-x-0 top-0 z-20 text-white">
        <div className="relative flex items-center gap-2 px-4 py-4 sm:gap-3 sm:px-8 sm:py-6 lg:px-12">
          <Link href="/" className="flex min-h-11 items-center gap-2.5" aria-label="Alumni Challenge home">
            <Logo size={32} tone="light" />
            <span className="whitespace-nowrap text-caption font-semibold uppercase tracking-[0.1em] sm:text-body sm:tracking-[0.14em]">Alumni Challenge</span>
          </Link>
          <NavLinks
            landing
            items={landingItems}
            className="absolute left-1/2 hidden -translate-x-1/2 gap-1 rounded-full bg-[rgb(20_14_8/0.62)] px-2 backdrop-blur-md lg:flex"
            linkClassName={`inline-flex ${overlayLink}`}
          />
          <div className="ml-auto flex items-center gap-1">
            {!signedIn && (
              <Link href="/login" className="mr-1 hidden h-11 items-center rounded-full bg-[rgb(20_14_8/0.62)] px-5 text-small font-medium text-white backdrop-blur-md transition-colors hover:bg-[rgb(20_14_8/0.8)] sm:inline-flex">
                Log in
              </Link>
            )}
            <Link
              href={signedIn ? "/start" : "/register"}
              className="inline-flex h-11 items-center gap-2 whitespace-nowrap rounded-full bg-[#1b1713] px-4 text-small sm:px-5 font-medium text-white shadow-lifted transition-colors hover:bg-black"
            >
              {signedIn ? "Open my home" : "Get started"} <ArrowRight className="size-4" aria-hidden />
            </Link>
          </div>
        </div>
        <NavLinks landing items={landingItems.slice(1)} className="flex gap-1 px-3 sm:px-6 lg:hidden" linkClassName={`inline-flex ${overlayLink}`} />
      </header>
    );
  }

  return (
    <header className="border-b border-line bg-canvas">
      <div className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-3 sm:px-6 lg:px-10">
        <Link href="/" className="flex min-h-11 items-center gap-2.5" aria-label="Alumni Challenge home">
          <Logo size={32} tone="dark" />
          <span className="hidden font-semibold uppercase tracking-[0.14em] sm:inline">Alumni Challenge</span>
        </Link>
        <NavLinks items={LINKS} className="ml-4 hidden gap-1 sm:flex" linkClassName={`inline-flex ${plainLink}`} />
        <div className="ml-auto flex items-center gap-1.5">
          {signedIn ? (
            <LinkButton href="/start" size="sm" className="sm:h-11 sm:px-5">Open my home</LinkButton>
          ) : (
            <>
              <Link href="/login" className="inline-flex min-h-11 items-center rounded-full px-4 text-small font-medium text-muted transition-colors hover:bg-sunken hover:text-ink">Log in</Link>
              <LinkButton href="/register" size="sm" className="sm:h-11 sm:px-5">Sign up</LinkButton>
            </>
          )}
        </div>
      </div>
      <NavLinks items={LINKS} className="mx-auto flex max-w-6xl gap-1 px-3 pb-2 sm:hidden" linkClassName={`inline-flex ${plainLink}`} />
    </header>
  );
}
