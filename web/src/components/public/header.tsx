import Link from "next/link";
import { Logo } from "@/components/shell/logo";
import { LinkButton } from "@/components/ui";
import { hasSession } from "@/lib/server/auth";
import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/schools", label: "Schools" },
  { href: "/partners", label: "Partners" },
];

const linkClass = "inline-flex min-h-11 items-center rounded-full px-4 text-small font-medium text-muted transition-colors hover:bg-sunken hover:text-ink";

/** The bar on public pages. "bare" drops the bottom rule, for the top of the landing page where it sits on the hero. */
export async function PublicHeader({ bare = false }: { bare?: boolean }) {
  const signedIn = await hasSession();
  return (
    <header className={cn("relative z-20 bg-canvas", !bare && "border-b border-line")}>
      <div className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-3 sm:px-6 lg:px-10">
        <Link href="/" className="flex min-h-11 items-center gap-2.5" aria-label="Alumni Challenge home">
          <Logo size={32} tone="dark" />
          <span className="hidden font-bold tracking-wide sm:inline">ALUMNI CHALLENGE</span>
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
