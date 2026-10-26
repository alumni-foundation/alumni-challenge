"use client";

import { Bell } from "lucide-react";
import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";
import { Avatar, Button, Skeleton, useToast } from "@/components/ui";
import { CountBadge } from "@/components/ui/count-badge";
import { Icon3D } from "@/components/ui/icon3d";
import { api } from "@/lib/api/client";
import { friendlyError } from "@/lib/api/messages";
import { useWrite } from "@/lib/api/hooks";
import { timeAgo, useNotifications, type NotificationItem } from "@/lib/notifications";
import { cn } from "@/lib/utils";

/**
 * The bell in the top bar: a textured tile with a red count, opening a panel under it. The button says it
 * opens a dialog and whether it is open; focus moves into the panel; Escape closes it and gives focus back
 * to the bell; a click outside closes it.
 */
export function NotificationBell({ className }: { className?: string }) {
  const { items, unread, isLoading, isError } = useNotifications();
  const [open, setOpen] = useState(false);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const titleId = useId();

  useEffect(() => {
    if (!open) return;
    panelRef.current?.focus();
    const onPointer = (e: PointerEvent) => {
      const t = e.target as Node;
      if (panelRef.current?.contains(t) || buttonRef.current?.contains(t)) return;
      setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      setOpen(false);
      buttonRef.current?.focus();
    };
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div className={cn("relative", className)}>
      <button
        ref={buttonRef}
        type="button"
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={open ? titleId : undefined}
        aria-label={unread ? `Notifications, ${unread} new` : "Notifications"}
        onClick={() => setOpen((v) => !v)}
        className="relative grid size-11 place-items-center rounded-2xl focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
      >
        <Icon3D icon={Bell} tone="paper" size="sm" />
        <CountBadge count={unread} />
      </button>

      {open && (
        <div
          ref={panelRef}
          id={titleId}
          role="dialog"
          aria-label="Notifications"
          tabIndex={-1}
          className="motion-rise fixed inset-x-4 top-[4.5rem] z-40 rounded-3xl border border-line bg-surface p-2 shadow-lifted focus:outline-none sm:absolute sm:inset-x-auto sm:right-0 sm:top-full sm:mt-3 sm:w-[24rem]"
        >
          <div className="flex items-center justify-between px-3 pb-1 pt-2.5">
            <h2 className="text-heading">Notifications</h2>
            {unread > 0 && <span className="text-small font-medium text-muted">{unread} new</span>}
          </div>
          {isLoading ? (
            <div className="space-y-2 p-2" role="status" aria-label="Loading">
              <Skeleton className="h-16" />
              <Skeleton className="h-16" />
            </div>
          ) : isError ? (
            <p className="px-3 py-6 text-center text-small text-ink">We couldn’t load your notifications. Try again in a moment.</p>
          ) : items.length === 0 ? (
            <p className="px-3 py-8 text-center text-body text-ink">You are all caught up.</p>
          ) : (
            <ul className="max-h-[60vh] divide-y divide-line overflow-y-auto">
              {items.map((item) => (
                <Row key={item.id} item={item} />
              ))}
            </ul>
          )}
          <div className="border-t border-line px-3 pt-1">
            <Link
              href="/connections?tab=received"
              onClick={() => setOpen(false)}
              className="inline-flex min-h-11 items-center text-small font-semibold text-brand-ink hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
            >
              See all in Connections
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}

/** One notification. A connection request can be answered right here. */
function Row({ item }: { item: NotificationItem }) {
  const toast = useToast();
  const refresh = [["connections"], ["blocked"], ["directory"]];
  const accept = useWrite((id: string) => api(`connections/${id}/accept`, { method: "PATCH" }), refresh);
  const decline = useWrite((id: string) => api(`connections/${id}/decline`, { method: "PATCH" }), refresh);

  async function act(fn: () => Promise<unknown>, done: string) {
    try {
      await fn();
      toast(done);
    } catch (e) {
      toast(friendlyError(e), "info");
    }
  }

  return (
    <li className="flex gap-3 px-3 py-3.5">
      <Avatar name={item.person?.name ?? "Alumni member"} id={item.person?.id ?? item.id} size={40} />
      <div className="min-w-0 flex-1">
        <p className="text-small font-semibold text-ink">{item.title}</p>
        <p className="text-small text-ink">{item.body}</p>
        <p className="mt-0.5 text-caption text-muted">{timeAgo(item.time)}</p>
        {item.kind === "connection_request" && (
          <div className="mt-2.5 flex gap-2">
            <Button variant="dark" size="sm" loading={accept.isPending && accept.variables === item.id} onClick={() => act(() => accept.mutateAsync(item.id), "You are now connected.")}>Accept</Button>
            <Button variant="secondary" size="sm" loading={decline.isPending && decline.variables === item.id} onClick={() => act(() => decline.mutateAsync(item.id), "Request declined.")}>Decline</Button>
          </div>
        )}
      </div>
    </li>
  );
}
