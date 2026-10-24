import Image from "next/image";
import auth from "@/assets/auth.jpg";

/**
 * The shared shell for every sign-in page. Large screens: the photo fills the screen and a frosted card
 * sits on the right. Below lg: a photo strip on top and the card as a full-width sheet rising over it.
 * The card, the Back to home pill and the caption live in template.tsx, so they enter on every visit while the photo stays put.
 * The photo is a wide banner, so it is placed (not cropped to fill) with its group on the left of the
 * card, and it fades into a fog-coloured ground that matches the picture's own backdrop.
 */
export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative flex min-h-dvh flex-col bg-[#ebe7e5] lg:flex-row lg:items-center lg:justify-end lg:overflow-hidden lg:px-[5vw] lg:py-10">
      <div className="relative h-56 shrink-0 overflow-hidden [--w:clamp(1500px,120vw,2300px)] sm:h-72 lg:absolute lg:inset-0 lg:h-auto">
        <div className="auth-photo auth-photo-in absolute inset-0 lg:inset-auto lg:bottom-28 lg:left-[calc(4vw-0.42*var(--w))] lg:aspect-[1994/789] lg:w-[var(--w)]">
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

      {children}
    </div>
  );
}
