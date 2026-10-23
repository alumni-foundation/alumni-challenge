import { PublicFooter } from "@/components/public/footer";
import { PublicHeader } from "@/components/public/header";
import { StatusPage } from "@/components/public/status-page";

export default function NotFound() {
  return (
    <div className="flex min-h-dvh flex-col">
      <PublicHeader />
      <main id="main" className="mx-auto w-full max-w-5xl flex-1 px-4 py-8 sm:px-6 sm:py-12">
        <StatusPage code="404" title="We can’t find that page">
          <p>The link may be old, or the page may have moved.</p>
        </StatusPage>
      </main>
      <PublicFooter />
    </div>
  );
}
