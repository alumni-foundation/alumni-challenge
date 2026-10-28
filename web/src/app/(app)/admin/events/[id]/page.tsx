import { EditEvent } from "@/components/admin/events/edit-event";
import { EventsGate } from "@/components/admin/events/gate";

export default async function EditEventPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <EventsGate>
      <EditEvent id={id} />
    </EventsGate>
  );
}
