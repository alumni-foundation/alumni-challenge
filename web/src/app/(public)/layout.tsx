import { PublicFooter } from "@/components/public/footer";
import { PublicHeader } from "@/components/public/header";

export default function PublicLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col">
      <PublicHeader />
      <main id="main" className="mx-auto w-full max-w-5xl flex-1 px-4 py-8 sm:px-6 sm:py-12">
        {children}
      </main>
      <PublicFooter />
    </div>
  );
}
