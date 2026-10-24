import Link from "next/link";
import { Logo } from "@/components/shell/logo";
import { LinkButton } from "@/components/ui";
import { hasSession } from "@/lib/server/auth";

const LINKS = [
  { href: "/schools", label: "Schools" },
  { href: "/partners", label: "Partners" },
];

export async function PublicHeader() {
  const signedIn = await hasSession();
  return (
    <header className="border-b border-line bg-surface">
      <div className="mx-auto flex max-w-5xl items-center gap-4 px-4 py-3 sm:px-6">
        <Link href="/" className="flex min-h-11 items-center gap-2.5" aria-label="Alumni Challenge home">
          <Logo size={32} tone="dark" />
          <span className="hidden font-bold tracking-wide sm:inline">ALUMNI CHALLENGE</span>
        </Link>
        <nav aria-label="Main" className="ml-2 hidden gap-1 sm:flex">
          {LINKS.map((l) => (
            <Link key={l.href} href={l.href} className="rounded-control px-3 py-2 text-small font-medium text-muted hover:bg-sunken hover:text-ink">
              {l.label}
            </Link>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-2">
          {signedIn ? (
            <LinkButton href="/start" size="sm">Open my home</LinkButton>
          ) : (
            <>
              <LinkButton href="/login" variant="ghost" size="sm">Log in</LinkButton>
              <LinkButton href="/register" size="sm">Sign up</LinkButton>
            </>
          )}
        </div>
      </div>
      <nav aria-label="Main" className="flex gap-1 border-t border-line px-4 sm:hidden">
        {LINKS.map((l) => (
          <Link key={l.href} href={l.href} className="px-3 py-3 text-small font-medium text-muted hover:text-ink">
            {l.label}
          </Link>
        ))}
      </nav>
    </header>
  );
}
