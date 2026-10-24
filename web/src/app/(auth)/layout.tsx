import Image from "next/image";
import Link from "next/link";
import { Logo } from "@/components/shell/logo";
import auth from "@/assets/auth.jpg";
import { AuthCaption } from "./caption";

/**
 * The shared shell for every sign-in page. Large screens: the photo fills the screen and a frosted card
 * sits on the right. Below lg: a photo strip on top and the card as a full-width sheet rising over it.
 * The photo is a wide banner, so it is placed (not cropped to fill) with its group on the left of the
 * card, and it fades into a fog-coloured ground that matches the picture's own backdrop.
 */
export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative flex min-h-dvh flex-col bg-[#ebe7e5] lg:flex-row lg:items-center lg:justify-end lg:overflow-hidden lg:px-[5vw] lg:py-10">
      <div className="relative h-56 shrink-0 overflow-hidden [--w:clamp(1500px,120vw,2300px)] sm:h-72 lg:absolute lg:inset-0 lg:h-auto">
        <div className="auth-photo absolute inset-0 lg:inset-auto lg:bottom-28 lg:left-[calc(4vw-0.42*var(--w))] lg:aspect-[1994/789] lg:w-[var(--w)]">
          <Image
            src={auth}
            alt=""
            fill
            sizes="(min-width: 1024px) 2000px, 100vw"
            quality={75}
            placeholder="blur"
            loading="eager"
            fetchPriority="high"
            className="object-cover object-[78%_40%] lg:object-center"
          />
        </div>
      </div>

      <main id="main" className="relative z-10 -mt-8 flex flex-1 flex-col lg:mt-0 lg:w-[30rem] lg:flex-none">
        <div className="auth-card flex flex-1 flex-col rounded-t-[28px] px-5 pb-8 pt-7 sm:px-8 sm:pt-8 lg:flex-none lg:rounded-[28px] lg:shadow-lifted">
          <div className="mx-auto w-full max-w-md flex-1 lg:max-w-none lg:flex-none">
            <Link href="/" aria-label="Alumni Challenge home" className="mb-7 inline-flex items-center gap-2.5 rounded-full bg-ink py-2 pl-3 pr-5 text-white">
              <Logo size={26} tone="light" />
              <span className="text-caption font-semibold uppercase tracking-[0.16em]">Alumni Challenge</span>
            </Link>
            {children}
            <p className="mt-8 flex justify-center gap-4 border-t border-line pt-4 text-caption text-muted">
              <Link href="/terms" className="inline-flex min-h-8 items-center hover:text-ink hover:underline">Terms</Link>
              <Link href="/privacy" className="inline-flex min-h-8 items-center hover:text-ink hover:underline">Privacy</Link>
            </p>
          </div>
        </div>
      </main>

      <AuthCaption />
    </div>
  );
}
