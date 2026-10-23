# Backend update: dev-only account with every role

Gives ONE email access to every part of the app (super admin, admin, moderator, school admin,
partner admin, member) so the frontend's development sign-in picker has something to switch
between. Apply after the earlier zips. No database migration.

## Apply

```bash
cd ~/projects/alumni-challenge
git status --short            # check for uncommitted work BEFORE unzipping
cp /mnt/c/Users/*/Downloads/dev-account-update.zip ~/projects/
unzip -o ~/projects/dev-account-update.zip -d ~/projects/alumni-challenge/
docker compose up -d --build
docker compose exec api uv run pytest -q
```

Expected: `148 passed`. (If one random test fails with `401 Invalid access token`, that is the
Windows clock problem, not this change.)

## Create your development account

```bash
docker compose exec api uv run python -m app.cli create-dev-account dev@example.com
```

It asks for a password (10 characters or more). To skip the prompt in development:
add `--password 'your-password-here'`.

Safe to run again: it never makes duplicates, switches back on any role that was revoked, and
leaves the password alone for an existing account.

## What the account gets

- Platform-wide: super_admin, admin, moderator
- Demo school (slug `demo-school`): school_admin, event_manager, sports_manager
- Demo partner (slug `demo-partner`): partner_admin
- A verified email address and a verified alumni profile, so the member view works at once
  and no "verify your email" banner gets in the way

The demo school and partner are created if missing. Nothing else is created.

## Safety

- The command refuses to run unless `ENVIRONMENT=development`. It exits with an error in
  staging and production, before touching the database (tested).
- There is no backend "log in as" shortcut. The picker the frontend adds only chooses which
  screen to land on after a normal login. The server still decides what the account can do
  from its real roles.

## Important limit

This one account has the UNION of every role's powers. It is good for looking at every screen.
It is NOT good for testing what a limited role is blocked from doing (for example "a school
admin cannot reactivate a user" or "a moderator cannot see another school's data"), because
this account is also a super admin. For that, the demo data step will create a separate
account per role.

## Checks done

- 10 new tests: every role granted to the right place, ready-to-use account, the real login
  and `/auth/me/roles` show all roles, the roles really open each area through the API, safe to
  run twice, a revoked role is switched back on, weak or missing password rejected, and the
  production and staging refusal.
- Mutation checks, each broken on purpose and confirmed to fail a test, then restored: guard
  removed, guard blocking production only, partner role missing, email not verified, not
  repeatable, revoked role left off, no profile, school roles attached to the wrong organization.
- ruff, ruff format, mypy strict clean. 148 tests pass (138 before + 10 new).

## Needs frontend

See section 14 in the frontend doc ("Development sign-in picker").
