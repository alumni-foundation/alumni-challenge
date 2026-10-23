import Link from "next/link";
import { Logo } from "@/components/shell/logo";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid min-h-dvh lg:grid-cols-2">
      <aside className="relative hidden flex-col justify-between overflow-hidden bg-side p-12 text-white lg:flex">
        <div className="absolute -right-24 -top-24 size-96 rounded-full bg-brand/30 blur-3xl" aria-hidden />
        <Link href="/" className="relative flex items-center gap-3">
          <Logo size={44} />
          <span>
            <span className="block text-lead font-bold tracking-wide">ALUMNI CHALLENGE</span>
            <span className="block text-caption text-white/70">Meet · Connect · Belong</span>
          </span>
        </Link>
        <div className="relative max-w-md">
          <p className="text-display font-bold">Your school family, in one place.</p>
          <p className="mt-4 text-body text-white/75">
            Find the people you shared a school with, stay close to the community that shaped you, and
            meet at the events that bring you together.
          </p>
        </div>
        <p className="relative text-caption text-white/60">© Alumni Challenge</p>
      </aside>
      <main id="main" className="flex flex-col px-4 py-6 sm:px-6">
        <Link href="/" className="mb-6 flex min-h-11 items-center gap-2.5 lg:hidden" aria-label="Alumni Challenge home">
          <Logo size={32} tone="dark" />
          <span className="font-bold tracking-wide">ALUMNI CHALLENGE</span>
        </Link>
        <div className="flex flex-1 items-start justify-center lg:items-center">
          <div className="w-full max-w-sm">{children}</div>
        </div>
      </main>
    </div>
  );
}
