import type { Conversation, MessageItem } from "./types";

/**
 * Made-up people and words, for /design-check and tests only. Never import this from a page a real
 * person can open: they would read it as their own conversations.
 */
export const SAMPLE_CONVERSATIONS: Conversation[] = [
  {
    id: "c1",
    with: { user_id: "u1", profile_id: "p1", full_name: "Sample Person One", verified: true },
    last_message: { body: "Sample: see you at the meetup?", created_at: "2026-10-25T08:00:00Z", sender_user_id: "u1" },
    unread_count: 2,
  },
  {
    id: "c2",
    with: { user_id: "u2", profile_id: "p2", full_name: "Sample Person Two", verified: false },
    last_message: { body: "Sample: thanks for the intro.", created_at: "2026-10-24T17:30:00Z", sender_user_id: "me" },
    unread_count: 0,
  },
];

export const SAMPLE_MESSAGES: MessageItem[] = [
  { id: "m1", conversation_id: "c1", sender_user_id: "u1", body: "Sample: hello!", created_at: "2026-10-25T07:58:00Z", read_at: "2026-10-25T07:59:00Z" },
  { id: "m2", conversation_id: "c1", sender_user_id: "me", body: "Sample: hi, good to hear from you.", created_at: "2026-10-25T07:59:00Z", read_at: null },
  { id: "m3", conversation_id: "c1", sender_user_id: "u1", body: "Sample: see you at the meetup?", created_at: "2026-10-25T08:00:00Z", read_at: null },
];
