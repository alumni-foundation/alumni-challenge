import type { Metadata, Viewport } from "next";
import { sans, serif } from "./fonts";
import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: { default: "Alumni Challenge", template: "%s · Alumni Challenge" },
  description: "Where alumni of Kenyan schools meet, connect and belong.",
};
export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#faf6ee" },
    { media: "(prefers-color-scheme: dark)", color: "#14110e" },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${sans.variable} ${serif.variable}`}>
      <body>
        <a href="#main" className="skip-link">Skip to content</a>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
