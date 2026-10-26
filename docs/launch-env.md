# Production environment variables

The variables to set before launch: **names and rules only, no values.** Never put a value in
git, in this file or in a chat message; use the platform's secret store. The full table (defaults,
what each one does, sizing) is in [DEPLOYMENT.md, section 4](DEPLOYMENT.md#4-environment-variables).
The template for a local file is [`backend/.env.example`](../backend/.env.example).

Set the same values on **both the api and the worker**.

With `ENVIRONMENT=production` the app refuses to start if a rule marked "checked at start" is
broken (`backend/app/core/config.py`). Fix the variable; do not work around the check.

## Must be set

| Variable | Rule |
|---|---|
| `ENVIRONMENT` | `production`. Turns on the start-up checks, turns off the API docs page and sends HSTS. |
| `SECRET_KEY` | Secret. At least 32 random characters, not a placeholder such as `change-me…` (checked at start). Generate with `python -c "import secrets; print(secrets.token_urlsafe(48))"`. Signs login, email-verification and password-reset tokens: changing it signs everyone out and voids outstanding links. |
| `TICKET_SIGNING_KEY` | Secret. **32 or more random characters and different from `SECRET_KEY`** (checked at start). Signs the QR codes on event tickets. **Never change it after launch:** every ticket already issued (printed or emailed) stops working. Keep a copy in the secret store. |

## Database and Redis

| Variable | Rule |
|---|---|
| `DATABASE_URL` | Secret (the password is in it). `postgresql+asyncpg://user:password@host:5432/dbname`. |
| `DATABASE_POOL_SIZE`, `DATABASE_MAX_OVERFLOW` | Optional. Connections per process; keep `api containers x WEB_CONCURRENCY x (pool + overflow) + 15` below the database's `max_connections` (formula in DEPLOYMENT.md). |
| `REDIS_URL` | Secret if Redis has a password. `redis://host:6379/0`. Holds rate limits and login lockouts, not data you cannot lose. |

## Storage

| Variable | Rule |
|---|---|
| `STORAGE_BACKEND` | `r2`. `local` is refused in production (checked at start). |
| `STORAGE_ENDPOINT_URL`, `STORAGE_ACCESS_KEY`, `STORAGE_SECRET_KEY`, `STORAGE_BUCKET_NAME` | All four required with `r2` (checked at start). The access key and secret are secret. The bucket must be **private**, with a token limited to that bucket. Backups go in a different bucket with a different token. |

## Email and links

| Variable | Rule |
|---|---|
| `MAIL_BACKEND` | `resend`. `logging` sends nothing and is refused in production (checked at start). |
| `RESEND_API_KEY` | Secret. Required with `resend` (checked at start). |
| `MAIL_FROM` | An address on the domain verified with the mail provider. |
| `FRONTEND_URL` | The web app's address, **starting with `https://`** (checked at start), no trailing slash. Email links are built from it. |
| `CORS_ALLOWED_ORIGINS` | JSON list of the web app's origins, for example `["https://example.org"]`. |

## Behind a proxy and under load

| Variable | Rule |
|---|---|
| `TRUSTED_CLIENT_IP_HEADER` | `none` (default), `cf-connecting-ip`, `x-forwarded-for` or `x-visitor-ip`. Set it when the API is behind a proxy, otherwise every visitor shares the proxy's address and the rate limits lock everyone out together. **If it is anything but `none`, the API must not be reachable directly from the internet:** anyone who can reach it can forge the header and dodge every rate limit. Only the one named header is read. |
| `PASSWORD_HASH_CONCURRENCY` | Optional, 1 to 16, default `2`. How many password hashes run at once; each needs 64 MiB, so keep the number times 64 MiB inside the memory left after the app starts, and no higher than the CPU cores. Keep `2` unless you have measured a need. |

## Recommended

| Variable | Rule |
|---|---|
| `SENTRY_DSN` | Secret. Empty turns error reporting off. `SENTRY_RELEASE` should be the image version. |
| `DEBUG` | Never `true` in production. |

Everything else in DEPLOYMENT.md section 4 has a safe default; leave it alone unless that
section says otherwise. The web app's own variables are in DEPLOYMENT.md, W2.
