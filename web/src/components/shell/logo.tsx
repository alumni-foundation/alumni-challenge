export function Logo({ size = 36, tone = "light" }: { size?: number; tone?: "light" | "dark" }) {
  const mark = tone === "light" ? "#fff" : "#17171b";
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden>
      <path d="M32 8 8 58h11.5l4.6-11.6h15.8L44.5 58H56L32 8Zm-4.6 30.4L32 26.8l4.6 11.6h-9.2Z" fill={mark} />
      <path d="M32 8 20 33h6l6-12.5L38 33h6L32 8Z" fill="#c31e2c" />
    </svg>
  );
}
