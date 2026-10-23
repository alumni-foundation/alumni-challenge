import type { Metadata } from "next";
import { Prose } from "@/components/public/prose";
import { site } from "@/lib/site";

export const metadata: Metadata = { title: "Contact" };

export default function Contact() {
  return (
    <Prose title="Contact" intro="Questions, problems or ideas? We would like to hear from you.">
      {site.contactEmail ? (
        <p>
          Write to <a href={`mailto:${site.contactEmail}`}>{site.contactEmail}</a>. Tell us what you were trying to do
          and what happened, and we will get back to you.
        </p>
      ) : (
        <p>Our contact details will appear here soon. In the meantime, your school’s alumni administrator can help.</p>
      )}
      <h2>Reporting a person</h2>
      <p>
        To report someone’s behaviour, open their profile and choose <strong>Report</strong>. That sends it straight to
        our moderators.
      </p>
    </Prose>
  );
}
