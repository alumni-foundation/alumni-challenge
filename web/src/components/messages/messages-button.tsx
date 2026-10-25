"use client";

import { MessageCircle } from "lucide-react";
import Link from "next/link";
import { CountBadge } from "@/components/ui/count-badge";
import { Icon3D } from "@/components/ui/icon3d";
import { cn } from "@/lib/utils";

/**
 * The chat icon in the top bar, next to the bell. There is no messaging API yet, so `unread` is always 0
 * for now and no count is drawn; when it exists, the page passes the real count here.
 */
export function MessagesButton({ unread = 0, className }: { unread?: number; className?: string }) {
  return (
    <Link
      href="/messages"
      aria-label={unread > 0 ? `Messages, ${unread} unread` : "Messages"}
      className={cn("relative grid size-11 shrink-0 place-items-center rounded-2xl focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink", className)}
    >
      <Icon3D icon={MessageCircle} tone="paper" size="sm" />
      <CountBadge count={unread} />
    </Link>
  );
}
