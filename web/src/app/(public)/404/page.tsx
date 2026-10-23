import type { Metadata } from "next";
import { StatusPage } from "@/components/public/status-page";

export const metadata: Metadata = { title: "Page not found" };

export default function NotFoundPage() {
  return (
    <StatusPage code="404" title="We can’t find that page">
      <p>The link may be old, or the page may have moved.</p>
    </StatusPage>
  );
}
