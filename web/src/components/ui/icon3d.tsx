import { cn } from "@/lib/utils";

export type Icon3DTone = "ember" | "gold" | "moss" | "sky" | "ink" | "paper";
export type Icon3DSize = "sm" | "md" | "lg";

// Tile size in px and the icon's share of it. The look itself lives in globals.css (.icon3d).
const SIZES: Record<Icon3DSize, { box: number; icon: number }> = {
  sm: { box: 40, icon: 20 },
  md: { box: 56, icon: 26 },
  lg: { box: 72, icon: 34 },
};

type Props = {
  icon: React.ElementType;
  tone?: Icon3DTone;
  size?: Icon3DSize;
  /** Draws the pressed look without a click, for showing the state. */
  pressed?: boolean;
  /** Draws the hover look without a pointer, for showing the state. */
  hover?: boolean;
  className?: string;
} & ({ onClick: () => void; label: string } | { onClick?: undefined; label?: undefined });

/**
 * A textured tile with an icon on it: gradient body, inner highlight, layered soft shadow and a
 * faint grain. Decorative by default (aria-hidden). Pass onClick and a label to make it a button
 * with a real pressed state.
 */
export function Icon3D({ icon: Icon, tone = "ember", size = "md", pressed, hover, className, onClick, label }: Props) {
  const s = SIZES[size];
  const common = {
    className: cn("icon3d", className),
    "data-tone": tone,
    "data-pressed": pressed ? "true" : undefined,
    "data-hover": hover ? "true" : undefined,
    style: { width: s.box, height: s.box },
  };
  const glyph = <Icon width={s.icon} height={s.icon} strokeWidth={2} aria-hidden />;
  if (onClick) {
    return (
      <button type="button" {...common} onClick={onClick} aria-label={label}>
        {glyph}
      </button>
    );
  }
  return (
    <span {...common} aria-hidden>
      {glyph}
    </span>
  );
}
