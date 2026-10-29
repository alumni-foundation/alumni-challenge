# Messaging API wishlist

The `/messages` page, the chat icon in the top bar and the **Message** buttons (profile pages, directory cards) are a
layout only. There is no messaging backend, so nothing here is called yet. This is what the web app needs, so the
backend agent can decide what to build. Names follow the existing API style (snake_case, UUID ids, ISO-8601 UTC times,
`limit` / `offset` paging with `X-Total-Count`).

## Rules the UI assumes

- Only two people who are **connected** (an accepted connection) can message each other. If the connection ends or
  either person blocks the other, the thread becomes read-only (or disappears); a new message is refused with an error
  code the UI can show in plain words.
- A conversation is one-to-one. A thread exists once, per pair of users (no duplicates when either side starts it).
- Suspended accounts cannot send, and their threads are hidden from the other person.
- Sending takes an `Idempotency-Key` header, like bookings, so a retry never posts twice.

## Shapes

```ts
type Conversation = {
  id: string;                  // uuid
  other_user_id: string;       // uuid
  other_profile_id: string | null; // uuid, so the UI can link to /alumni/{id}
  other_full_name: string | null;
  other_avatar_url: string | null;
  last_message: MessagePreview | null;
  unread_count: number;        // messages from the other person after my last read
  updated_at: string;          // time of the last message, for sorting
  can_send: boolean;           // false when the connection ended, someone is blocked or suspended
};

type MessagePreview = {
  id: string;
  sender_id: string;           // uuid of the user
  body: string;                // first ~140 characters
  created_at: string;
};

type Message = {
  id: string;
  conversation_id: string;
  sender_id: string;
  body: string;                // plain text, 1 to 2000 characters
  created_at: string;
  read_at: string | null;      // when the other person read it (null = not yet)
};

type UnreadCount = { unread_count: number; unread_conversations: number };
```

## Endpoints

| Call | Purpose |
|---|---|
| `GET /conversations?limit=&offset=` | My conversations, newest activity first. Returns `Conversation[]` and `X-Total-Count`. |
| `POST /conversations` with `{ user_id }` | Open (or return the existing) conversation with a connected person. Used by the **Message** buttons, which could then link to `/messages?c={id}`. 403 when not connected. |
| `GET /conversations/{id}/messages?limit=&before=` | A page of messages, newest first, cursor by `before` (a message id or time). |
| `POST /conversations/{id}/messages` with `{ body }` | Send. Returns the `Message`. Needs `Idempotency-Key`. |
| `POST /conversations/{id}/read` | Mark everything up to now as read; clears this conversation's unread count. |
| `GET /messages/unread-count` | `UnreadCount`, for a badge on the chat icon in the top bar. |

## Nice to have

- A push channel (server-sent events or a websocket) so the open thread and the badge update without polling. Until
  then the web app would poll `GET /messages/unread-count` and the open thread every 15 to 30 seconds.
- Report a message (`POST /reports` with `target_type: "message"`), so moderators can review it.
- Delete my own message (soft delete, shown as "Message deleted").
- Rate limit per sender, and a clear `429` the UI can word nicely.
