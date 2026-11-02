import type { Metadata, Viewport } from "next";
import { sans, serif } from "./fonts";
import "./globals.css";
import { Providers } from "./providers";

// Set NEXT_PUBLIC_SITE_URL (https://...) so share-image links are absolute; without it the address is left for the browser to resolve.
const siteUrl = process.env.NEXT_PUBLIC_SITE_URL;

export const metadata: Metadata = {
  ...(siteUrl ? { metadataBase: new URL(siteUrl) } : {}),
  title: { default: "Alumni Challenge", template: "%s · Alumni Challenge" },
  description: "Where alumni of Kenyan schools meet, connect and belong.",
  applicationName: "Alumni Challenge",
  openGraph: {
    type: "website",
    siteName: "Alumni Challenge",
    title: "Alumni Challenge",
    description: "Where alumni of Kenyan schools meet, connect and belong.",
  },
  twitter: { card: "summary_large_image", title: "Alumni Challenge", description: "Where alumni of Kenyan schools meet, connect and belong." },
};
export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#faf6ee",
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
