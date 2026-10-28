import { EventEditor } from "@/components/admin/events/event-editor";
import { EventsGate } from "@/components/admin/events/gate";

/** `?org=<id>` preselects the organizer, for the Create event buttons on a school or partner page. */
export default async function NewEventPage({ searchParams }: { searchParams: Promise<{ org?: string | string[] }> }) {
  const { org } = await searchParams;
  return (
    <EventsGate>
      <EventEditor initial={null} presetOrganizationId={typeof org === "string" ? org : undefined} />
    </EventsGate>
  );
}
