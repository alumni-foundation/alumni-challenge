"use client";

import { ArrowLeft, MessageCircle, Send } from "lucide-react";
import { useState } from "react";
import { Avatar, Icon3D, VerifiedMark } from "@/components/ui";
import { cn, formatDate } from "@/lib/utils";
import type { Conversation, MessageItem } from "./types";

export const COMING_SOON = "Messaging is coming soon. You will be able to message people you are connected with.";

/**
 * Conversation list on the left, the open thread in the middle, the composer under it. On a phone the
 * list and the thread are two screens: the list first, then a thread with a back arrow.
 * With no conversations (every real person, until the API exists) it shows the coming-soon words and a
 * disabled composer.
 */
export function MessagesView({
  conversations,
  messages = [],
  meId = "me",
  composerEnabled = false,
}: {
  conversations: Conversation[];
  messages?: MessageItem[];
  meId?: string;
  composerEnabled?: boolean;
}) {
  const [activeId, setActiveId] = useState<string | null>(null);
  const active = conversations.find((c) => c.id === activeId) ?? null;
  const empty = conversations.length === 0;
  const thread = messages.filter((m) => m.conversation_id === activeId);

  return (
    <div className="page-enter mx-auto flex h-[calc(100dvh-13rem)] min-h-[28rem] max-w-[1280px] overflow-hidden rounded-[1.75rem] border border-line bg-surface shadow-resting lg:h-[calc(100dvh-8rem)]">
      {/* Conversation list. On phones it is the whole screen until a thread is opened. */}
      <aside aria-label="Conversations" className={cn("w-full shrink-0 flex-col border-line md:w-80 md:border-r", active ? "hidden md:flex" : "flex")}>
        <h1 className="px-5 pb-3 pt-5 text-heading font-semibold">Messages</h1>
        {empty ? (
          <>
            <div className="flex flex-1 flex-col items-center justify-center gap-3 px-6 pb-10 text-center md:hidden">
              <Icon3D icon={MessageCircle} tone="gold" size="lg" />
              <p className="text-body">{COMING_SOON}</p>
            </div>
            <p className="hidden px-5 text-small text-muted md:block">No conversations yet.</p>
          </>
        ) : (
          <ul className="flex-1 divide-y divide-line overflow-y-auto">
            {conversations.map((c) => (
              <li key={c.id}>
                <button
                  type="button"
                  onClick={() => setActiveId(c.id)}
                  aria-current={c.id === activeId ? "true" : undefined}
                  className={cn("flex min-h-16 w-full items-center gap-3 px-5 py-3 text-left hover:bg-sunken focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-ink", c.id === activeId && "bg-sunken")}
                >
                  <Avatar name={c.with.full_name} id={c.with.user_id} size={44} />
                  <span className="min-w-0 flex-1">
                    <span className="flex items-center gap-1.5 font-semibold"><span className="truncate">{c.with.full_name}</span>{c.with.verified && <VerifiedMark />}</span>
                    <span className="block truncate text-small text-muted">{c.last_message?.body ?? "No messages yet"}</span>
                  </span>
                  {c.unread_count > 0 && <span className="grid h-5 min-w-5 place-items-center rounded-full bg-brand px-1 text-[11px] font-bold text-white" aria-label={`${c.unread_count} unread`}>{c.unread_count}</span>}
                </button>
              </li>
            ))}
          </ul>
        )}
      </aside>

      {/* The thread and the composer. Hidden on a phone until a conversation is open (and while there are none). */}
      <section aria-label="Conversation" className={cn("min-w-0 flex-1 flex-col", active ? "flex" : "hidden md:flex")}>
        <header className="flex min-h-16 items-center gap-3 border-b border-line px-4 sm:px-5">
          {active && (
            <button type="button" onClick={() => setActiveId(null)} aria-label="Back to conversations" className="grid size-11 place-items-center rounded-full hover:bg-sunken focus-visible:outline-2 focus-visible:outline-ink md:hidden">
              <ArrowLeft className="size-5" aria-hidden />
            </button>
          )}
          {active ? (
            <>
              <Avatar name={active.with.full_name} id={active.with.user_id} size={40} />
              <p className="flex items-center gap-1.5 font-semibold">{active.with.full_name}{active.with.verified && <VerifiedMark />}</p>
            </>
          ) : (
            <p className="font-semibold text-muted">{empty ? "Messages" : "Choose a conversation"}</p>
          )}
        </header>

        <div className="flex-1 overflow-y-auto px-4 py-4 sm:px-6">
          {active ? (
            <ol className="space-y-2">
              {thread.map((m) => {
                const mine = m.sender_user_id === meId;
                return (
                  <li key={m.id} className={cn("flex", mine ? "justify-end" : "justify-start")}>
                    <p className={cn("max-w-[80%] rounded-2xl px-4 py-2.5 text-small", mine ? "bg-ink text-white" : "bg-sunken text-ink")}>
                      {m.body}
                      <time dateTime={m.created_at} className={cn("mt-1 block text-caption", mine ? "text-white/70" : "text-muted")}>{formatDate(m.created_at)}</time>
                    </p>
                  </li>
                );
              })}
            </ol>
          ) : (
            <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
              <Icon3D icon={MessageCircle} tone="gold" size="lg" />
              <p className="max-w-sm text-body">{empty ? COMING_SOON : "Pick a conversation from the list."}</p>
            </div>
          )}
        </div>

        <form className="flex items-center gap-2 border-t border-line p-3 sm:p-4" onSubmit={(e) => e.preventDefault()}>
          <label htmlFor="message-text" className="sr-only">Write a message</label>
          <input
            id="message-text"
            disabled={!composerEnabled}
            placeholder={composerEnabled ? "Write a message" : "Messaging is not available yet"}
            className="h-11 min-w-0 flex-1 rounded-full border border-line-strong bg-surface px-4 text-small placeholder:text-faint disabled:cursor-not-allowed disabled:bg-sunken"
          />
          <button type="submit" disabled={!composerEnabled} aria-label="Send" className="grid size-11 shrink-0 place-items-center rounded-full bg-ink text-white disabled:cursor-not-allowed disabled:opacity-50">
            <Send className="size-4" aria-hidden />
          </button>
        </form>
      </section>
    </div>
  );
}
