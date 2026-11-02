# Security

## Reporting a vulnerability

Please report security problems privately. **Do not open a public issue or pull request for
them.**

Email: **vancellebaraza8@gmail.com**

Include what you found, the steps to reproduce it, and what an attacker could do with it. Do not
include other people's personal data; a description is enough. Please give us reasonable time to
fix the problem before you tell anyone else, and do not read, change or delete other people's
data while testing.

## Supported versions

There are no tagged releases yet (the API version in `backend/pyproject.toml` is `0.1.0`).
Only the code on the `main` branch, which is what gets deployed, is supported. Fixes go into
`main`; older commits are not patched.

## What the code does for security

Everything below is read from the code, not planned. File names are given so you can check.

**Passwords**
* Passwords are hashed with Argon2id (`argon2-cffi`, 64 MiB, time cost 3, one lane), and only
  the hash is stored (`backend/app/modules/identity/security.py`).
* Hashing runs in a small thread pool so it cannot starve the server of memory;
  `PASSWORD_HASH_CONCURRENCY` caps how many run at once.
* Signing in with an unknown email does the same hashing work as a wrong password, and both give
  the same message, so the response does not reveal which emails have accounts.
* After 5 wrong passwords for one email, signing in for that email is blocked for 15 minutes
  (`identity/service.py`).

**Sessions and tokens**
* Access tokens are signed JWTs (HS256) that last 15 minutes by default. Refresh tokens are
  random 512-bit strings; only their SHA-256 hash is stored, so a database copy cannot be used to
  sign in.
* Email-verification and password-reset links are signed, expire, and carry a purpose that is
  checked, so one kind cannot be used as the other. A password-reset link is single-use: the
  account's security stamp changes when the password changes, which kills every other link issued
  before it.
* Every request re-reads the account, so a suspended or deleted account stops working at once,
  not when its token expires.

**Event tickets**
* A ticket code is a random 128-bit id plus a 128-bit HMAC-SHA256 signature made with
  `TICKET_SIGNING_KEY`, compared in constant time (`bookings/tickets.py`). In production the
  app refuses to start unless that key is set, is at least 32 characters and differs from
  `SECRET_KEY`.

**Who may do what**
* Roles live in one table (`memberships`) and every protected route checks them through
  `require_roles` or `require_roles_for_org` (`core/permissions/dependencies.py`). School and
  partner roles apply only to their own organization.
* Platform roles are ranked (super admin, admin, moderator) and the rank decides who may change
  whom (`core/permissions/roles.py`, `memberships/role_changes.py`). Nobody can change their own
  roles, nobody can suspend an account at or above their own level, and the last super admin
  cannot be revoked.
* Lists for admins return only what the screen needs (for example the users list has no hashes,
  tokens or profile details), and an organization's rosters are always filtered by the
  organization in the URL as well as the route's permission check.
* These admin actions are written to an audit log: role grants and removals, suspensions and
  reactivations, alumni verification, adding and removing school email domains, creating an
  organization and reviewing a report. (Editing an organization's name or description and
  changing its logo are not audited yet.)

**Rate limits** (Redis, `core/rate_limit/`)
* Per address: sign-in 20 per 15 minutes, sign-up 10 per hour, token refresh 60 per 15 minutes,
  "forgot password" 5 per hour, password reset 10 per hour, asking for a verification email 5 per
  hour, confirming one 30 per hour. Reports 20 per hour, uploads 100 per hour.
* Every request that changes data is limited app-wide: 120 a minute per signed-in account, 30 a
  minute per address when not signed in.
* `TRUSTED_CLIENT_IP_HEADER` stays `none` unless the API is behind a proxy. Only that one header
  is read, because anyone who can reach the API directly can forge such headers.

**Suspension**
* Suspending an account revokes all its sessions. They stay revoked if the account is
  reactivated, so the person has to sign in again (`identity/account_status.py`).

**Secrets and configuration**
* Real secrets are never in the repository: `backend/.env` is git-ignored and
  `backend/.env.example` holds placeholders only.
* The app refuses to start in staging or production with a placeholder or short `SECRET_KEY`.
  In production only, it also refuses to start with local-disk file storage, with
  `MAIL_BACKEND=logging`, with a `FRONTEND_URL` that is not `https://`, or without a valid
  `TICKET_SIGNING_KEY` (`core/config.py`). Secret settings are held as `SecretStr`, which masks them if a
  settings object is printed.
* Production turns off the API docs page and sends `Strict-Transport-Security`.
* Every response carries `X-Content-Type-Options`, `X-Frame-Options: DENY`, a restrictive
  `Content-Security-Policy`, `Referrer-Policy` and `Permissions-Policy`.

**Uploads and files**
* Uploaded pictures are decoded and re-encoded, which removes EXIF data such as GPS position,
  and are limited per user and per hour (`files/images.py`, `files/service.py`).
* The storage bucket is meant to be private; browsers never talk to it, files are served by
  the API.

**Personal data**
* Deleting an account anonymizes it (the email becomes `deleted-…@deleted.invalid`); records that
  must outlive the person, such as reports, keep only an anonymous id. An account owner can also
  export their own data (`identity/privacy.py`, `identity/self_service.py`).

## Not covered here

This file describes what the code does today. It is not an audit or a certification. Things that
depend on how the service is run (backups, access to the servers, the Cloudflare and database
settings) are in `docs/DEPLOYMENT.md`, and the production variables are in `docs/launch-env.md`.
