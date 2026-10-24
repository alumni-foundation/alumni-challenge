import localFont from "next/font/local";

// Both faces come from npm packages (no network at build time) and are served from our own origin.

/** Jost: a clean, Futura-like sans with a quiet, elegant rhythm. Body text, forms, buttons. */
export const sans = localFont({
  src: "../../node_modules/@fontsource-variable/jost/files/jost-latin-wght-normal.woff2",
  variable: "--font-jost",
  weight: "100 900",
  display: "swap",
});

/** Cormorant Garamond: a high-contrast display serif. Headlines (h1, h2) and their accent words. */
export const serif = localFont({
  src: [
    { path: "../../node_modules/@fontsource-variable/cormorant-garamond/files/cormorant-garamond-latin-wght-normal.woff2", weight: "300 700", style: "normal" },
    { path: "../../node_modules/@fontsource-variable/cormorant-garamond/files/cormorant-garamond-latin-wght-italic.woff2", weight: "300 700", style: "italic" },
  ],
  variable: "--font-serif-face",
  display: "swap",
  adjustFontFallback: "Times New Roman",
});
