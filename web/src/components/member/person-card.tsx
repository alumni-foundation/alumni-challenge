import { MessageCircle } from "lucide-react";
import Link from "next/link";
import { Avatar, Card, LinkButton, VerifiedMark } from "@/components/ui";
import type { ProfileSummary } from "@/lib/api/types";

/**
 * One person in the directory. The whole card opens the profile (the name link is stretched over it), so it is easy
 * to tap. A person the viewer is connected with also gets a Message button, which sits above that link.
 */
export function PersonCard({ person, schoolName, connected = false }: { person: ProfileSummary; schoolName?: string; connected?: boolean }) {
  const work = [person.profession, person.company].filter(Boolean).join(" at ");
  const meta = [schoolName, person.graduation_year && `Class of ${person.graduation_year}`, person.country].filter(Boolean).join(" · ");
  return (
    <Card interactive className="relative flex items-center gap-3">
      <Avatar name={person.full_name} id={person.id} size={48} />
      <span className="min-w-0 flex-1">
        <span className="flex items-center gap-1.5 font-semibold">
          <Link href={`/alumni/${person.id}`} className="truncate after:absolute after:inset-0 after:rounded-card focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink">
            {person.full_name}
          </Link>
          {person.verification_status === "verified" && <VerifiedMark />}
        </span>
        {work && <span className="block truncate text-small text-ink">{work}</span>}
        {meta && <span className="line-clamp-2 block text-small text-muted">{meta}</span>}
      </span>
      {connected && (
        <LinkButton href="/messages" variant="secondary" size="sm" className="relative z-10 shrink-0" prefetch={false}>
          <MessageCircle className="size-4" aria-hidden /> Message<span className="sr-only"> {person.full_name}</span>
        </LinkButton>
      )}
    </Card>
  );
}
