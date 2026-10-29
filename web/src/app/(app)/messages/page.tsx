"use client";

import { ArrowLeft, MessageCircle, Search, Send } from "lucide-react";
import { useState } from "react";
import { Avatar, Button, Card, Icon3D, Input } from "@/components/ui";
import { cn } from "@/lib/utils";

/**
 * Layout only: there is no messaging backend, so there are no conversations and nothing can be sent. The shapes the page
 * will need are in MESSAGING_API_WISHLIST.md. On wide screens the list and the thread sit side by side; on phones they
 * are separate screens (the thread has a Back button), and with nothing to list the thread screen is the only one shown.
 */
type Conversation = { id: string; name: string; preview: string; unread: number };
const CONVERSATIONS: Conversation[] = [];

export default function MessagesPage() {
  const [selected, setSelected] = useState<string | null>(null);
  const current = CONVERSATIONS.find((c) => c.id === selected) ?? null;
  const showThreadOnPhone = current !== null || CONVERSATIONS.length === 0;

  return (
    <div className="mx-auto max-w-[1280px]">
      <h1 className="sr-only">Messages</h1>
      <Card large className="flex h-[calc(100dvh-13rem)] min-h-[26rem] overflow-hidden p-0 sm:p-0 lg:h-[calc(100dvh-7.5rem)]">
        <section
          aria-label="Conversations"
          className={cn("min-w-0 flex-col border-line lg:flex lg:w-80 lg:shrink-0 lg:border-r", showThreadOnPhone ? "hidden" : "flex w-full")}
        >
          <div className="space-y-3 p-4">
            <h2 className="text-heading font-semibold">Conversations</h2>
            <div className="relative">
              <Search className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-muted" aria-hidden />
              <Input type="search" aria-label="Search conversations" placeholder="Search" disabled className="pl-10" />
            </div>
          </div>
          {CONVERSATIONS.length === 0 ? (
            <p className="px-4 text-small text-muted">No conversations yet.</p>
          ) : (
            <ul className="flex-1 divide-y divide-line overflow-y-auto">
              {CONVERSATIONS.map((c) => (
                <li key={c.id}>
                  <button type="button" onClick={() => setSelected(c.id)} className="flex min-h-16 w-full items-center gap-3 px-4 py-3 text-left hover:bg-sunken">
                    <Avatar name={c.name} id={c.id} size={44} />
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-semibold">{c.name}</span>
                      <span className="block truncate text-small text-muted">{c.preview}</span>
                    </span>
                    {c.unread > 0 && <span className="rounded-full bg-brand px-2 text-caption font-bold text-white">{c.unread}</span>}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section aria-label="Conversation" className={cn("min-w-0 flex-1 flex-col lg:flex", showThreadOnPhone ? "flex" : "hidden")}>
          {current && (
            <div className="flex items-center gap-3 border-b border-line px-4 py-3">
              <button type="button" onClick={() => setSelected(null)} aria-label="Back to conversations" className="-ml-2 grid size-11 place-items-center rounded-full hover:bg-sunken lg:hidden">
                <ArrowLeft className="size-5" aria-hidden />
              </button>
              <Avatar name={current.name} id={current.id} size={40} />
              <p className="min-w-0 truncate font-semibold">{current.name}</p>
            </div>
          )}
          <div className="flex flex-1 flex-col items-center justify-center gap-4 overflow-y-auto px-6 py-10 text-center">
            <Icon3D icon={MessageCircle} tone="gold" size="lg" />
            <p className="max-w-sm text-body text-muted">Messaging is coming soon. You will be able to message people you are connected with.</p>
          </div>
          <form onSubmit={(e) => e.preventDefault()} className="flex items-center gap-2 border-t border-line p-3 sm:p-4" aria-label="Write a message">
            <Input aria-label="Message" placeholder="Not available yet" disabled className="flex-1" />
            <Button type="submit" variant="dark" disabled title="Coming soon" aria-label="Send, coming soon"><Send className="size-4" aria-hidden /> <span className="hidden sm:inline">Send</span></Button>
          </form>
        </section>
      </Card>
    </div>
  );
}
