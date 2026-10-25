/**
 * The shapes the messages screen draws. There is no messaging API yet (see MESSAGING_API_WISHLIST.md at the
 * root of web/), so nothing here is fetched: the page passes empty lists. When the API exists, only the
 * hook that fills these changes.
 */
export type ConversationPerson = {
  user_id: string;
  profile_id: string | null;
  full_name: string;
  verified: boolean;
};

export type MessageItem = {
  id: string;
  conversation_id: string;
  sender_user_id: string;
  body: string;
  created_at: string;
  /** Set when the other person has opened it. */
  read_at: string | null;
};

export type Conversation = {
  id: string;
  with: ConversationPerson;
  last_message: Pick<MessageItem, "body" | "created_at" | "sender_user_id"> | null;
  unread_count: number;
};
