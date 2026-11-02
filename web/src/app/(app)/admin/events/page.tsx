import { EventList } from "@/components/admin/events/event-list";
import { EventsGate } from "@/components/admin/events/gate";

export default function AdminEventsPage() {
  return (
    <EventsGate>
      <EventList />
    </EventsGate>
  );
}
