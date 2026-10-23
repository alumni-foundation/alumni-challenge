import type { Metadata } from "next";
import { LinkButton } from "@/components/ui";
import { StatusPage } from "@/components/public/status-page";
import { site } from "@/lib/site";

export const metadata: Metadata = { title: "Account suspended" };

export default function Suspended() {
  return (
    <StatusPage
      title="Your account is suspended"
      actions={
        site.contactEmail ? (
          <LinkButton href={`mailto:${site.contactEmail}`}>Contact support</LinkButton>
        ) : (
          <LinkButton href="/contact">Contact support</LinkButton>
        )
      }
    >
      <p>You can’t use your account right now. If you think this is a mistake, contact support and we will look into it.</p>
    </StatusPage>
  );
}
