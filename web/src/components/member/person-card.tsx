import Link from "next/link";
import { MessageButton } from "@/components/messages/message-button";
import { Avatar, Card, VerifiedMark } from "@/components/ui";
import type { ProfileSummary } from "@/lib/api/types";

/** One person in the directory. The whole card is the link, so it is easy to tap. */
export function PersonCard({ person, schoolName, connected = false }: { person: ProfileSummary; schoolName?: string; connected?: boolean }) {
  const work = [person.profession, person.company].filter(Boolean).join(" at ");
  const meta = [schoolName, person.graduation_year && `Class of ${person.graduation_year}`, person.country].filter(Boolean).join(" · ");
  return (
    <div className="relative">
    <Link href={`/alumni/${person.id}`} className="block rounded-card">
      <Card interactive className={connected ? "flex flex-wrap items-center gap-3 sm:pr-36" : "flex items-center gap-3"}>
        <Avatar name={person.full_name} id={person.id} size={48} />
        <span className="min-w-0 flex-1">
          <span className="flex items-center gap-1.5 font-semibold">
            <span className="truncate">{person.full_name}</span>
            {person.verification_status === "verified" && <VerifiedMark />}
          </span>
          {work && <span className="block truncate text-small text-ink">{work}</span>}
          {meta && <span className="line-clamp-2 block text-small text-muted">{meta}</span>}
        </span>
      </Card>
    </Link>
    {connected && (
      // Beside the link, not inside it: a button cannot sit inside a link.
      <div className="absolute bottom-3 right-3 sm:bottom-auto sm:top-1/2 sm:-translate-y-1/2">
        <MessageButton />
      </div>
    )}
    </div>
  );
}
