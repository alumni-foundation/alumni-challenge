# Update: email verification, password reset, rate limiting, login lockout

## Apply (WSL, from repo root)

    unzip -o /mnt/c/Users/Administrator/Downloads/alumni-challenge-update-3.zip -d ~/projects/alumni-challenge/
    cd ~/projects/alumni-challenge
    docker compose up -d --build
    docker compose exec api uv run alembic upgrade head
    git add . && git commit -m "Email verification, password reset, rate limiting, login lockout" && git push

Paste back: the migration output and the GitHub Actions result.

## What changed

**New endpoints** (`/api/v1/auth/...`), all tested — 57/57 backend tests pass, ruff + mypy clean:

- `POST /email/verify/request` — signed in, sends a 24h verification link. Rate limited: 5/hour per user.
- `POST /email/verify/confirm` — body `{token}`. Sets `email_verified_at`. This is also what switches on school email-domain auto-verify (HANDOFF.md flagged this as inert until email verification existed — it's live now).
- `POST /password/forgot` — body `{email}`. Always returns 202 whether or not the email is registered, so a caller can never use it to check which emails have accounts. Rate limited: 5/hour per IP.
- `POST /password/reset` — body `{token, new_password}`. 30-minute link, single-use (using it, or requesting a new one, invalidates any other outstanding reset link for that account), and resetting force-signs-out every other device. Rate limited: 10/hour per IP.

**Login lockout:** 5 wrong passwords for one email within 15 minutes locks that email for 15 minutes — even the correct password is rejected until it clears. A successful login resets the counter. This trades a small amount of account-enumeration resistance (a locked account's error message differs from "wrong password") for stopping unlimited password guessing — the standard, deliberate OWASP trade-off.

**Rate limiting:** `/register` (10/hour/IP), `/login` (20/15min/IP, on top of the lockout above). Built as a reusable Redis-backed dependency (`app/core/rate_limit`) — attaching it to any other endpoint later is a one-line `Depends(...)`.

**Email sending:** no Resend account exists yet, so this ships against a fake mailer (`app/core/mail`) that logs the full email — link included — to `docker compose logs -f api`, so you can grab a verification or reset link by hand while testing. `get_mailer()` in `app/core/mail/dependencies.py` is the one place to point at a real Resend-backed mailer later; nothing else changes when you do.

**Migration:** adds `users.security_stamp` (a UUID, regenerated on every password reset). This is what makes reset links single-use without a separate token-tracking table — a reset link carries the stamp it was issued against, so using it (or issuing a newer one) invalidates every other outstanding link instantly.

## What this doesn't cover yet (from HANDOFF.md, still open)

Audit log, account suspend/delete endpoints, Google/Apple sign-in hooks, security headers/request-size limits. Rate limiting is applied to auth only for now — the framework is reusable, so extending it to messaging/search/uploads later (per PLAN.md Phase 2) is small follow-up work, not a redesign.

## Frontend note

The login/register screens built in the last update don't have "forgot password" or "verify your email" UI yet — those endpoints are ready and waiting. That's naturally the next slice of `web/` to build once you've confirmed this is working end to end.
