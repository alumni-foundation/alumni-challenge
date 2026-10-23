# 23 Oct 2026: platform fixes and role tools

Decided with the owner. Context for why the code looks the way it does.

## Tests are isolated from development

Tests used the development database and flushed the development Redis. They now run on a
`*_test` database and Redis index 15, chosen in `tests/_env.py` before the app is imported,
and refuse to run against anything else. The session start creates the test database if
missing and runs `alembic upgrade head` on it.

## JWT leeway is 10 seconds and a constant

A wide leeway keeps expired and not-yet-valid tokens alive, so it is a constant in
`identity/security.py`, tested to stay at or below 10 seconds and to reject a token issued
2 minutes in the future. A machine with a wrong clock is fixed by correcting the clock.

## Standard columns

`id`, `created_at` and `updated_at` on every table. `created_by` and `updated_by` (through a
mixin) on tables people edit, and `status` only where a record has a real lifecycle. New tables
only; existing tables are not retrofitted.

## Demo accounts

`seed-demo` replaces the one-account-with-every-role command. One account per role, each with
its own address under example.com, development only. A random password is printed once and not
stored; a rerun changes nothing and keeps existing passwords unless `--reset-passwords`.

## Looking people up

`POST /organizations/{id}/user-lookup` only ever returns members of that organization (a role
in it, or a school's declared alumni). Anyone else, existing or not, gets the identical empty
answer, so it cannot tell you who is on the platform. Limited to 30 lookups an hour per admin,
audited with a fingerprint of the address, never the address. A platform-wide lookup for admins
is not built: it cannot hide whether an address exists.

## Changing roles

Platform roles follow a rank rule: a super admin can change any platform role, an admin only
moderator and only for someone below admin, a moderator nothing. Nobody changes their own
roles. The last super admin cannot be revoked; revoking a super admin locks every super_admin
row and re-checks the caller under the lock, so two super admins revoking each other at once
leave one. Organization roles keep the matrix: platform admins appoint and remove organization
admins; an organization's admin appoints and removes its managers. Every change is audited.

## Rosters

A school admin sees their school's alumni (those who declared the school) even when a profile
is private, but only name, graduation year, country and verification state. Never email,
company, profession or bio. Members and roster lists are gated by the organization permission
check and also filtered by organization in the query.

# Files and uploads (step 3)

## What we never trust

The file name and Content-Type a client sends are never read. The type is decided by opening
the bytes (JPEG, PNG or WebP only; no GIF, SVG or animation). The picture is then rebuilt from
its raw pixels and encoded fresh, so location data, comments, colour profiles, text chunks and
anything appended after the image cannot survive. Pictures over 25 megapixels are refused before
they are decoded, whatever their file size. The storage key is made by the server
(`public|private/<purpose>/<uuid>.<ext>`) and is never shown to clients.

## Public and private

Logos and event posters are public: one permanent address, cached for good, and a replacement
gets a new address. Avatars are private: they are fetched through a signed link that works for
five minutes, handed out only inside a profile response, which exists only for viewers who
passed the profile visibility check. Every refusal on the content route is the same plain 404.

## Limits

Per-purpose size and dimension limits; 50 files per person; 20 uploads an hour per person. All
are checked before any image is decoded. Only `POST /files` accepts a body over 2 MiB (6 MiB).

## Not built yet

R2 adapter (interface and local backend are done), malware scanning, thumbnails, and a cleanup
job for uploads that were never attached.
