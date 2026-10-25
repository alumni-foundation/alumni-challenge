# Messaging API wishlist

What the web app would like from the backend so the Messages screen (`/messages`, the chat icon in the top bar
and the **Message** buttons) can go live. Until then the screen shows "Messaging is coming soon" and nothing is
fetched. The shapes below are what `src/components/messages/types.ts` already draws.

Rules we would want, in plain words:

- Only people who are **connected** (an accepted connection) can message each other. A block ends it both ways.
- A suspended account cannot send or receive. Messages from people you blocked never reach you.
- A report can point at a message (`target_type: "message"` already exists in the reports API), so a moderator
  needs a way to read **that one message and a few around it**, and nothing else of the conversation.

## Data shapes

```ts
type Conversation = {
  id: string;
  with: { user_id: string; profile_id: string | null; full_name: string; verified: boolean };
  last_message: { body: string; created_at: string; sender_user_id: string } | null;
  unread_count: number;       // this person's unread messages in this conversation
};

type Message = {
  id: string;
  conversation_id: string;
  sender_user_id: string;
  body: string;               // plain text, 1 to 2000 characters
  created_at: string;         // ISO 8601
  read_at: string | null;     // when the other person opened it
};

type UnreadSummary = { unread_messages: number; unread_conversations: number };
```

## Endpoints we would call

| Call | Purpose |
|---|---|
| `GET /messages/conversations?limit=&offset=` | The list on the left, newest activity first. `X-Total-Count` header as the directory does. |
| `POST /messages/conversations` body `{ user_id }` | Start (or return the existing) conversation with a connected person. Used by the **Message** button. |
| `GET /messages/conversations/{id}/messages?before=&limit=` | The thread, newest page first, older pages by cursor. |
| `POST /messages/conversations/{id}/messages` body `{ body }` + `Idempotency-Key` | Send. Returns the `Message`. |
| `POST /messages/conversations/{id}/read` | Mark everything up to now as read; clears the unread count. |
| `GET /messages/unread` | `UnreadSummary`, for the number on the chat icon. Polled about once a minute, like notifications. |

## Nice to have

- A server-sent events or websocket channel for new messages, so the thread updates without polling.
- `DELETE /messages/{id}` for the sender, within a short window.
- Rate limits per sender (the login and register limits are the model), and a clear error code for "not connected any more".
