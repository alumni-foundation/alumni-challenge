import Image from "next/image";

/**
 * The real logo, used as supplied (public/brand). "full" is the logo with its words, for light backgrounds; "mark" is the
 * circle and A on its own, for tight spaces. Never put either straight on a dark background: use <LogoTile> for that.
 * `size` is the height in pixels. Width and height are always set, so nothing jumps while the picture loads.
 * Leave `alt` empty when the words "Alumni Challenge" are written next to it.
 */
const SRC = {
  full: { src: "/brand/alumni-challenge-logo.png", ratio: 1416 / 545 },
  mark: { src: "/brand/alumni-challenge-mark.png", ratio: 1 },
} as const;

export function Logo({ variant = "mark", size = 36, alt = "", className }: { variant?: "full" | "mark"; size?: number; alt?: string; className?: string }) {
  const { src, ratio } = SRC[variant];
  return <Image src={src} alt={alt} width={Math.round(size * ratio)} height={size} quality={75} className={className} />;
}

/** The mark on a white rounded tile, for dark backgrounds such as the sidebar. */
export function LogoTile({ size = 40, alt = "" }: { size?: number; alt?: string }) {
  return (
    <span className="grid shrink-0 place-items-center rounded-xl bg-surface shadow-resting" style={{ width: size, height: size }}>
      <Logo variant="mark" size={Math.round(size * 0.78)} alt={alt} />
    </span>
  );
}
