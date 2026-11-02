"use client";

import { useMemo } from "react";
import { useConnections, useMe } from "@/lib/api/hooks";

/**
 * One thing that wants the person's attention. The bell and its panel only know this shape, so when the
 * backend gets a notifications API, only the source inside useNotifications changes: the UI does not.
 */
export type NotificationItem = {
  id: string;
  kind: "connection_request";
  title: string;
  body: string;
  /** Where "see it" goes. */
  href: string;
  /** ISO time the thing happened. */
  time: string;
  read: boolean;
  /** Who it is about, for the avatar. */
  person?: { id: string; name: string };
};

export type Notifications = {
  items: NotificationItem[];
  /** How many are not read yet: what the badge shows. */
  unread: number;
  isLoading: boolean;
  isError: boolean;
};

/**
 * Today's only source is real data we already have: connection requests waiting for this person.
 * Newest first. Requests are never "read" until they are answered, then they leave the list.
 */
export function useNotifications(): Notifications {
  const me = useMe();
  const connections = useConnections();
  const items = useMemo<NotificationItem[]>(() => {
    const myId = me.data?.id;
    return (connections.data ?? [])
      .filter((c) => c.status === "pending" && c.addressee_id === myId)
      .sort((a, b) => b.created_at.localeCompare(a.created_at))
      .map((c) => ({
        id: c.id,
        kind: "connection_request" as const,
        title: `${c.other_full_name ?? "An alumni member"} wants to connect`,
        body: "Accept to add them to your network.",
        href: "/connections?tab=received",
        time: c.created_at,
        read: false,
        person: { id: c.other_user_id, name: c.other_full_name ?? "Alumni member" },
      }));
  }, [connections.data, me.data?.id]);
  return {
    items,
    unread: items.filter((i) => !i.read).length,
    isLoading: connections.isLoading || me.isLoading,
    isError: connections.isError,
  };
}

const UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ["day", 86_400_000],
  ["hour", 3_600_000],
  ["minute", 60_000],
];

/** "2 hours ago", "yesterday", "just now". */
export function timeAgo(iso: string, now = Date.now()): string {
  const diff = new Date(iso).getTime() - now;
  const rtf = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
  for (const [unit, ms] of UNITS) {
    if (Math.abs(diff) >= ms) return rtf.format(Math.round(diff / ms), unit);
  }
  return "just now";
}
