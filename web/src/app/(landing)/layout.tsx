import { PublicFooter } from "@/components/public/footer";

// The landing page draws its own header on top of the hero photo, so it has no shared header here.
export default function LandingLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col">
      <main id="main" className="flex-1">
        {children}
      </main>
      <PublicFooter />
    </div>
  );
}
