import localFont from "next/font/local";

// Both faces come from npm packages (no network at build time) and are served from our own origin.
export const sans = localFont({
  src: "../../node_modules/@fontsource-variable/inter/files/inter-latin-wght-normal.woff2",
  variable: "--font-inter",
  weight: "100 900",
  display: "swap",
});

/** A refined serif for one or two accent words in a headline. Never for body text. */
export const serif = localFont({
  src: [
    { path: "../../node_modules/@fontsource/instrument-serif/files/instrument-serif-latin-400-normal.woff2", weight: "400", style: "normal" },
    { path: "../../node_modules/@fontsource/instrument-serif/files/instrument-serif-latin-400-italic.woff2", weight: "400", style: "italic" },
  ],
  variable: "--font-serif-face",
  display: "swap",
  adjustFontFallback: "Times New Roman",
});
