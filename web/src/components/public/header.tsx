import Link from "next/link";
import { Logo } from "@/components/shell/logo";
import { LinkButton } from "@/components/ui";
import { hasSession } from "@/lib/server/auth";
import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/schools", label: "Schools" },
  { href: "/partners", label: "Partners" },
];

/**
 * The bar on public pages. "overlay" sits on top of a photo: it becomes a frosted dark pill, so
 * the white text keeps AA contrast whatever picture is behind it.
 */
export async function PublicHeader({ overlay = false }: { overlay?: boolean }) {
  const signedIn = await hasSession();
  const linkClass = overlay
    ? "text-white/90 hover:bg-white/10 hover:text-white"
    : "text-muted hover:bg-sunken hover:text-ink";
  return (
    <header className={cn(overlay ? "absolute inset-x-0 top-0 z-20 px-3 pt-3 sm:px-6 sm:pt-5" : "border-b border-line bg-canvas")}>
      <div
        className={cn(
          "mx-auto flex max-w-6xl items-center gap-3",
          overlay
            ? "rounded-full border border-white/15 bg-[rgb(20_16_12/0.6)] py-1.5 pl-4 pr-1.5 text-white backdrop-blur-md sm:pl-5"
            : "px-4 py-3 sm:px-6",
        )}
      >
        <Link href="/" className="flex min-h-11 items-center gap-2.5" aria-label="Alumni Challenge home">
          <Logo size={32} tone={overlay ? "light" : "dark"} />
          <span className={cn("hidden font-bold tracking-wide sm:inline", overlay && "text-white")}>ALUMNI CHALLENGE</span>
        </Link>
        <nav aria-label="Main" className="ml-4 hidden gap-1 sm:flex">
          {LINKS.map((l) => (
            <Link key={l.href} href={l.href} className={cn("inline-flex min-h-11 items-center rounded-full px-4 text-small font-medium transition-colors", linkClass)}>
              {l.label}
            </Link>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-1.5">
          {signedIn ? (
            <LinkButton href="/start" size="sm" className="sm:h-11 sm:px-5">Open my home</LinkButton>
          ) : (
            <>
              <Link href="/login" className={cn("inline-flex min-h-11 items-center rounded-full px-4 text-small font-medium transition-colors", linkClass)}>
                Log in
              </Link>
              <LinkButton href="/register" size="sm" className="sm:h-11 sm:px-5">Sign up</LinkButton>
            </>
          )}
        </div>
      </div>
      {!overlay && (
        <nav aria-label="Main" className="mx-auto flex max-w-6xl gap-1 px-3 pb-2 sm:hidden">
          {LINKS.map((l) => (
            <Link key={l.href} href={l.href} className="inline-flex min-h-11 items-center rounded-full px-4 text-small font-medium text-muted hover:bg-sunken hover:text-ink">
              {l.label}
            </Link>
          ))}
        </nav>
      )}
    </header>
  );
}
