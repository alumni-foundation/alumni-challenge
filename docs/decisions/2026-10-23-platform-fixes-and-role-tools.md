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
