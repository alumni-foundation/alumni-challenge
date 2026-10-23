import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";
import { EmptyState, LinkButton } from "@/components/ui";
import { fetchOrg } from "@/lib/server/public-api";
import { OrgLogo } from "./org";

/** The public page for one school or partner. Visitors and members see the same thing. */
export async function OrgPage({ id, type }: { id: string; type: "school" | "partner" }) {
  const result = await fetchOrg(id);
  if (result.org === null) {
    if (result.reason === "missing") notFound();
    return <EmptyState title="We can’t load this page right now" body="Please try again in a moment." />;
  }
  const { org } = result;
  if (org.type !== type) notFound();

  const back = type === "school" ? { href: "/schools", label: "All schools" } : { href: "/partners", label: "All partners" };
  return (
    <article className="mx-auto max-w-2xl">
      <Link href={back.href} className="mb-6 inline-flex min-h-11 items-center gap-1.5 text-small text-muted hover:text-ink">
        <ArrowLeft className="size-4" aria-hidden /> {back.label}
      </Link>
      <div className="flex items-center gap-4">
        <OrgLogo org={org} size={72} />
        <h1 className="text-title">{org.name}</h1>
      </div>
      {org.description && <p className="mt-6 whitespace-pre-line text-body">{org.description}</p>}
      <div className="mt-8 rounded-card border border-line bg-surface p-5">
        <p className="font-semibold">
          {type === "school" ? `Went to ${org.name}?` : `Part of the ${org.name} community?`}
        </p>
        <p className="mt-1 text-small text-muted">Create an account to find fellow alumni and stay connected.</p>
        <LinkButton href="/register" className="mt-4 w-full sm:w-auto">Join the alumni network</LinkButton>
      </div>
    </article>
  );
}
