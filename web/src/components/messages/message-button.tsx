import { MessageCircle } from "lucide-react";
import { LinkButton } from "@/components/ui";

/** The "Message" pill on a profile or a directory card. It opens the messages page, which says messaging is coming. */
export function MessageButton({ size = "sm", className }: { size?: "sm" | "md"; className?: string }) {
  return (
    <LinkButton href="/messages" variant="secondary" size={size} className={className}>
      <MessageCircle className="size-4" aria-hidden /> Message
    </LinkButton>
  );
}
