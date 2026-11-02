"use client";

import { MessageCircle } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Icon3D } from "@/components/ui/icon3d";
import { cn } from "@/lib/utils";

/** The chat icon in the top bar, next to the bell. Messaging is not built yet: the page it opens says so. */
export function MessagesLink({ className }: { className?: string }) {
  const active = usePathname().startsWith("/messages");
  return (
    <Link
      href="/messages"
      aria-label="Messages"
      aria-current={active ? "page" : undefined}
      className={cn("relative grid size-11 place-items-center rounded-2xl focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink", className)}
    >
      <Icon3D icon={MessageCircle} tone={active ? "ember" : "paper"} size="sm" />
    </Link>
  );
}
