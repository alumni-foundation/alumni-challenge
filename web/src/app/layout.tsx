import type { Metadata, Viewport } from "next";
import "@fontsource-variable/inter";
import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: { default: "Alumni Challenge", template: "%s · Alumni Challenge" },
  description: "Connect with fellow alumni, schools and partners. Support each other and create impact.",
};
export const viewport: Viewport = { themeColor: "#16161a" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
