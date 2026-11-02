# Profile API: notes for the frontend

## `account_status` on a profile (admin "Suspended" banner)

Every route that returns a profile (`GET /alumni/{id}`, `GET /alumni/profile/me`, the profile
edit routes, verify, vouch) can include one extra key:

```json
"account_status": "active" | "suspended" | "deleted"
```

**The key is absent, not `null`, unless the viewer is allowed to know:**

| Viewer | Gets `account_status`? |
|---|---|
| Platform admin (`admin`, `super_admin`), on any profile they can open, including their own | **Yes**, always |
| Moderator, on a profile that **someone else** has reported, while that report is `open` or `reviewing` | **Yes**; it disappears the moment the report is `resolved` or `dismissed` |
| Moderator, on their own profile; or on a profile with no live report, or only a report they filed | No |
| The owner | **No** (not even if suspended) |
| School admin, event manager, any other member, signed-out visitor | No |

So render the banner when `account_status` is present and not `"active"`. Never rely on it
being there: a missing key means "not allowed to know", not "active".

A suspended or deleted person's profile is already a `404` for everyone except platform admins and
a moderator with a live report; this field is only readable by those same people.
