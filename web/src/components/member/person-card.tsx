import Link from "next/link";
import { Avatar, Card, VerifiedMark } from "@/components/ui";
import type { ProfileSummary } from "@/lib/api/types";

/** One person in the directory. The whole card is the link, so it is easy to tap. */
export function PersonCard({ person, schoolName }: { person: ProfileSummary; schoolName?: string }) {
  const work = [person.profession, person.company].filter(Boolean).join(" at ");
  const meta = [schoolName, person.graduation_year && `Class of ${person.graduation_year}`, person.country].filter(Boolean).join(" · ");
  return (
    <Link href={`/alumni/${person.id}`} className="block rounded-card">
      <Card interactive className="flex items-center gap-3">
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
  );
}
