import { MessagesView } from "@/components/messages/messages-view";

export const metadata = { title: "Messages" };

/** Messaging has no backend yet, so this page shows where it will live and offers no conversations. */
export default function MessagesPage() {
  return <MessagesView conversations={[]} />;
}
