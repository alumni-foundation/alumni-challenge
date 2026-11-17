import { ArrowRight, Clock, Mail, MapPin, Phone } from "lucide-react";
import type { Metadata } from "next";
import { Eyebrow } from "@/components/site/parts";
import { Prose } from "@/components/public/prose";
import { Card } from "@/components/ui";
import { Icon3D } from "@/components/ui/icon3d";
import { contact } from "@/lib/site-info";
import { site } from "@/lib/site";

export const metadata: Metadata = {
  title: "Contact",
  description: `Milestone Business Center, Kiambu Road. Phone ${contact.phone}. ${contact.hoursShort}.`,
};

export default function Contact() {
  return (
    <div className="mx-auto max-w-2xl">
      <Prose title="Contact" intro="Questions, problems or ideas? We would like to hear from you.">
        {site.contactEmail ? (
          <p>
            Write to <a href={`mailto:${site.contactEmail}`}>{site.contactEmail}</a>. Tell us what you were trying to do
            and what happened, and we will get back to you.
          </p>
        ) : (
          <p>Our contact details will appear here soon. In the meantime, your school’s alumni administrator can help.</p>
        )}
      </Prose>

      <section aria-labelledby="details" className="mt-10">
        <Eyebrow>Contact Info</Eyebrow>
        <h2 id="details" className="mt-1 text-heading font-semibold">Contact Details</h2>
        <ul className="mt-4 grid gap-3 sm:grid-cols-2">
          <li>
            <Card className="flex h-full items-start gap-4">
              <Icon3D icon={MapPin} tone="ember" size="md" />
              <div>
                <h3 className="text-small font-semibold">Address</h3>
                <address className="mt-1 text-small not-italic text-muted">
                  {contact.address.map((l) => <span key={l} className="block">{l}</span>)}
                </address>
              </div>
            </Card>
          </li>
          <li>
            <Card className="flex h-full items-start gap-4">
              <Icon3D icon={Clock} tone="gold" size="md" />
              <div>
                <h3 className="text-small font-semibold">Opening hours</h3>
                <dl className="mt-1 text-small text-muted">
                  {contact.hours.map((h) => (
                    <div key={h.days} className="flex gap-2"><dt className="min-w-20">{h.days}</dt><dd>{h.time}</dd></div>
                  ))}
                </dl>
              </div>
            </Card>
          </li>
          <li>
            <Card className="flex h-full items-start gap-4">
              <Icon3D icon={Phone} tone="moss" size="md" />
              <div>
                <h3 className="text-small font-semibold">Phone number</h3>
                <a href={contact.phoneHref} className="mt-1 inline-flex min-h-11 items-center text-small font-medium text-brand-ink hover:underline">{contact.phone}</a>
              </div>
            </Card>
          </li>
          <li>
            <Card className="flex h-full items-start gap-4">
              <Icon3D icon={Mail} tone="sky" size="md" />
              <div className="min-w-0">
                <h3 className="text-small font-semibold">E-Mail</h3>
                <a href={`mailto:${contact.email}`} className="mt-1 inline-flex min-h-11 items-center break-all text-small font-medium text-brand-ink hover:underline">{contact.email}</a>
              </div>
            </Card>
          </li>
        </ul>
      </section>

      <section aria-labelledby="callback" className="mt-8 rounded-card border border-line bg-sunken/70 p-5 sm:p-6">
        <h2 id="callback" className="text-heading font-semibold">Request a call back</h2>
        <p className="mt-1 text-small text-muted">Send us a message, or phone {contact.phone} {contact.hoursShort}.</p>
        <a
          href={`mailto:${contact.email}?subject=Call%20back%20request`}
          className="mt-4 inline-flex h-11 items-center gap-2 rounded-full bg-ink px-6 text-small font-medium text-white shadow-raised transition-[background-color,transform] duration-150 hover:bg-black active:scale-[0.98] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
        >
          Request a Call Back <ArrowRight className="size-4" aria-hidden />
        </a>
      </section>

      <section className="mt-10 space-y-3">
        <h2 className="text-heading font-semibold">Reporting a person</h2>
        <p>
          To report someone’s behaviour, open their profile and choose <strong>Report</strong>. That sends it straight to
          our moderators.
        </p>
      </section>
    </div>
  );
}
