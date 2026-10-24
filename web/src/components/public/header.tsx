import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { Logo } from "@/components/shell/logo";
import { LinkButton } from "@/components/ui";
import { hasSession } from "@/lib/server/auth";
import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/schools", label: "Schools" },
  { href: "/partners", label: "Partners" },
];
const OVERLAY_LINKS = [{ href: "/", label: "Home" }, ...LINKS, { href: "/contact", label: "Contact" }];

const linkClass = "inline-flex min-h-11 items-center rounded-full px-4 text-small font-medium text-muted transition-colors hover:bg-sunken hover:text-ink";

/**
 * The bar on public pages. "overlay" sits on top of the landing hero: white text, links centred, and
 * a dark pill on the right. The hero's scrim keeps that text at AA contrast over any picture.
 */
export async function PublicHeader({ overlay = false }: { overlay?: boolean }) {
  const signedIn = await hasSession();

  if (overlay) {
    return (
      <header className="absolute inset-x-0 top-0 z-20 text-white">
        <div className="relative flex items-center gap-3 px-5 py-4 sm:px-8 sm:py-6 lg:px-12">
          <Link href="/" className="flex min-h-11 items-center gap-2.5" aria-label="Alumni Challenge home">
            <Logo size={34} tone="light" />
            <span className="whitespace-nowrap font-serif text-xl font-semibold tracking-wide sm:text-2xl">Alumni Challenge</span>
          </Link>
          <nav aria-label="Main" className="absolute left-1/2 hidden -translate-x-1/2 gap-1 rounded-full bg-[rgb(20_14_8/0.62)] px-2 backdrop-blur-md lg:flex">
            {OVERLAY_LINKS.map((l) => (
              <Link
                key={l.href}
                href={l.href}
                aria-current={l.href === "/" ? "page" : undefined}
                className={cn(
                  "relative inline-flex min-h-11 items-center px-4 text-small font-medium text-white/90 transition-colors hover:text-white",
                  l.href === "/" && "text-white after:absolute after:inset-x-4 after:bottom-1.5 after:h-px after:bg-white/80",
                )}
              >
                {l.label}
              </Link>
            ))}
          </nav>
          <div className="ml-auto flex items-center gap-1">
            <Link
              href={signedIn ? "/start" : "/register"}
              className="inline-flex h-11 items-center gap-2 whitespace-nowrap rounded-full bg-[#1b1713] px-5 text-small font-medium text-white shadow-lifted transition-colors hover:bg-black"
            >
              {signedIn ? "Open my home" : "Get started"} <ArrowRight className="size-4" aria-hidden />
            </Link>
          </div>
        </div>
        <nav aria-label="Main" className="flex gap-1 px-3 sm:px-6 lg:hidden">
          {OVERLAY_LINKS.slice(1).map((l) => (
            <Link key={l.href} href={l.href} className="inline-flex min-h-11 items-center rounded-full px-4 text-small font-medium text-white/90 hover:text-white">
              {l.label}
            </Link>
          ))}
        </nav>
      </header>
    );
  }

  return (
    <header className="border-b border-line bg-canvas">
      <div className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-3 sm:px-6 lg:px-10">
        <Link href="/" className="flex min-h-11 items-center gap-2.5" aria-label="Alumni Challenge home">
          <Logo size={32} tone="dark" />
          <span className="hidden font-serif text-xl font-semibold tracking-wide sm:inline">Alumni Challenge</span>
        </Link>
        <nav aria-label="Main" className="ml-4 hidden gap-1 sm:flex">
          {LINKS.map((l) => (
            <Link key={l.href} href={l.href} className={linkClass}>
              {l.label}
            </Link>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-1.5">
          {signedIn ? (
            <LinkButton href="/start" size="sm" className="sm:h-11 sm:px-5">Open my home</LinkButton>
          ) : (
            <>
              <Link href="/login" className={linkClass}>Log in</Link>
              <LinkButton href="/register" size="sm" className="sm:h-11 sm:px-5">Sign up</LinkButton>
            </>
          )}
        </div>
      </div>
      <nav aria-label="Main" className="mx-auto flex max-w-6xl gap-1 px-3 pb-2 sm:hidden">
        {LINKS.map((l) => (
          <Link key={l.href} href={l.href} className={linkClass}>
            {l.label}
          </Link>
        ))}
      </nav>
    </header>
  );
}
