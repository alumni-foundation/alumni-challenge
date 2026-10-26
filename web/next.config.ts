import type { NextConfig } from "next";
import { PHASE_DEVELOPMENT_SERVER } from "next/constants";

// Files named page.dev.tsx are routes only in `next dev` (the design-check page). `next build` does
// not know the "dev.tsx" extension, so those pages are not compiled or shipped.
const nextConfig = (phase: string): NextConfig => ({
  output: "standalone",
  pageExtensions: phase === PHASE_DEVELOPMENT_SERVER ? ["tsx", "ts", "jsx", "js", "dev.tsx"] : ["tsx", "ts", "jsx", "js"],
  poweredByHeader: false,
  // Event posters come from the API through our own file proxy, so they can be resized like any other picture.
  images: { formats: ["image/avif", "image/webp"], qualities: [60, 75], localPatterns: [{ pathname: "/api/v1/files/**" }, { pathname: "/brand/**" }] },
  async redirects() {
    // The directory moved from /alumni to /directory. Profiles stay at /alumni/:profileId.
    return [{ source: "/alumni", destination: "/directory", permanent: true }];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
});

export default nextConfig;
