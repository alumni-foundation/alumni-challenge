import { cookies } from "next/headers";
import { PublicFooter } from "@/components/public/footer";
import { PublicHeader } from "@/components/public/header";
import { AppLayoutClient } from "@/app/(app)/app-layout-client";
import { hasSession } from "@/lib/server/auth";

/**
 * Events can be browsed without an account, and a ticket link opens from an email, so these pages sit between
 * the public site and the member app: a signed-in person gets their app shell around the page, a visitor gets
 * the public header and footer.
 */
export default async function EventsLayout({ children }: { children: React.ReactNode }) {
  if (await hasSession()) {
    const saved = (await cookies()).get("ac_sidebar")?.value;
    return <AppLayoutClient sidebar={saved === "expanded" || saved === "collapsed" ? saved : null}>{children}</AppLayoutClient>;
  }
  return (
    <div className="flex min-h-dvh flex-col">
      <PublicHeader />
      <main id="main" className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 sm:px-6 sm:py-12">
        {children}
      </main>
      <PublicFooter />
    </div>
  );
}
