import type { Metadata } from "next";
import { StatusPage } from "@/components/public/status-page";

export const metadata: Metadata = { title: "Not allowed" };

export default function Forbidden() {
  return (
    <StatusPage code="403" title="You can’t open this page">
      <p>Your account doesn’t have access to it. If you think it should, ask the person who manages your school’s alumni.</p>
    </StatusPage>
  );
}
