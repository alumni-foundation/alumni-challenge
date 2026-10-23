# Deploying the Alumni Challenge API

For the person setting up the servers. This covers the backend (API + worker). The web app
(`web/`, Next.js) is deployed separately and only needs to know the API's address.

Everything below was run by hand against the real image, except where a line says **not
yet tested**. If a step surprises you, the step is wrong: tell the developer.

## 1. What runs

| Service | What | How many | Notes |
|---|---|---|---|
| **api** | The HTTP API (uvicorn) | 1 or more | Stateless. Port 8000. Put it behind Cloudflare. |
| **worker** | Background jobs: sends every email, retries failures | **exactly 1** | Same image as the API, different command. |
| **migrate** | `alembic upgrade head` | one-off, each deploy | Same image. Runs **before** the new API starts. |
| **PostgreSQL 17** | The database | 1 | Back it up (section 8). |
| **Redis 7** | Rate limits and login lockouts. No data you cannot lose. | 1 | If Redis is down, sign-in and other writes fail until it is back; reading pages still works. |
| **Object storage** | Cloudflare R2: uploaded pictures | 1 bucket | **Private** bucket. The API serves the files; browsers never talk to the bucket. |
| **Resend** | Sends email | external | Needs a verified sending domain (section 3). |
| **Sentry** | Error reports | external | Optional but expected in production. |
| **Cloudflare** | DNS, TLS, proxy, firewall | external | Section 7. |

One image runs all three roles. Only the command differs.

## 2. Build

From the repository root:

```
docker build --target production -t alumni-api:<version> backend
```

Use the git commit as `<version>` so a running container can always be traced to its code
(for example `alumni-api:bd98b29`). Keep the last few images so a rollback is one redeploy.

The image runs as a normal user (not root), contains no tests and no `.env`, and has its own
health check on `GET /health/live`.

## 3. Before the first deploy (accounts and DNS)

1. **Domain.** For example `api.example.org` for the API and `example.org` for the web app.
2. **Resend.** Add the sending domain in Resend and create the DNS records it shows
   (SPF, DKIM) plus a DMARC record. Wait until Resend says the domain is verified. Without
   this, verification and password-reset emails land in spam or are refused. Create an API key.
3. **Cloudflare R2.** Create a bucket (for example `alumni-uploads`), leave it **private**
   (no public access, no custom public domain), turn on object versioning if offered, and
   create an API token with read and write on that bucket only. Note the S3 endpoint
   (`https://<account-id>.r2.cloudflarestorage.com`).
4. **Second bucket for backups** (for example `alumni-backups`), with a different token. Never
   store backups in the uploads bucket.
5. **Sentry.** Create a project (platform: Python) and copy its DSN.
6. **Secrets.** Generate the secret key:
   `python -c "import secrets; print(secrets.token_urlsafe(48))"`

## 4. Environment variables

Set these on **both the api and the worker** (the same values). "Secret" means: put it in the
platform's secret store, never in git, never in a chat message.

When `ENVIRONMENT=production` the app **refuses to start** unless: `SECRET_KEY` is at least 32
characters and not a placeholder, `STORAGE_BACKEND=r2` with all four storage settings,
`MAIL_BACKEND=resend` with `RESEND_API_KEY`, and `FRONTEND_URL` starts with `https://`.

| Variable | Secret | Required | Default | Meaning |
|---|---|---|---|---|
| `ENVIRONMENT` | no | yes | `development` | `production` (or `staging`). Switches on the checks above and turns off the API docs page. |
| `SECRET_KEY` | **yes** | yes | none | Signs login tokens. Changing it signs everyone out. 32+ random characters. |
| `DATABASE_URL` | **yes** | yes | none | `postgresql+asyncpg://user:password@host:5432/dbname`. The password is in it. |
| `REDIS_URL` | **yes** | yes | none | `redis://host:6379/0`. If Redis has a password it is in the URL. |
| `FRONTEND_URL` | no | yes | `http://localhost:3000` | The web app's address, no trailing slash. Email links are built from it: `<FRONTEND_URL>/verify-email?token=...` and `<FRONTEND_URL>/reset-password?token=...`. Must be `https://` in production. |
| `CORS_ALLOWED_ORIGINS` | no | yes | `["http://localhost:3000"]` | JSON list of web app origins allowed to call the API, for example `["https://example.org"]`. |
| `STORAGE_BACKEND` | no | yes | `local` | `r2` in production. `local` (disk) is refused in production because container disks are wiped on redeploy. |
| `STORAGE_ENDPOINT_URL` | no | with r2 | none | The R2 S3 endpoint. |
| `STORAGE_ACCESS_KEY` | **yes** | with r2 | none | R2 access key id. |
| `STORAGE_SECRET_KEY` | **yes** | with r2 | none | R2 secret access key. |
| `STORAGE_BUCKET_NAME` | no | with r2 | none | The private uploads bucket. |
| `STORAGE_LOCAL_PATH` | no | no | `var/uploads` | Development only. |
| `MAIL_BACKEND` | no | yes | `logging` | `resend` in production. `logging` sends nothing. |
| `MAIL_FROM` | no | yes | `Alumni Challenge <no-reply@localhost>` | The From line, on the verified Resend domain: `Alumni Challenge <no-reply@example.org>`. |
| `RESEND_API_KEY` | **yes** | with resend | none | Resend API key. |
| `SMTP_HOST` | no | with smtp | none | Only if `MAIL_BACKEND=smtp` (development Mailpit). |
| `SMTP_PORT` | no | no | `1025` | SMTP only. |
| `SMTP_USERNAME` | no | no | none | SMTP only. |
| `SMTP_PASSWORD` | **yes** | no | none | SMTP only. |
| `SMTP_STARTTLS` | no | no | `false` | SMTP only. |
| `SENTRY_DSN` | **yes** | recommended | none | Empty means Sentry is off. Treat the DSN as a secret. |
| `SENTRY_TRACES_SAMPLE_RATE` | no | no | `0.1` | Share of requests traced for performance (0 to 1). |
| `SENTRY_RELEASE` | no | recommended | none | The image version, so errors show which deploy caused them. |
| `TRUSTED_CLIENT_IP_HEADER` | no | yes behind Cloudflare | `none` | Set `cf-connecting-ip` when the API is behind Cloudflare. Otherwise every visitor shares the proxy's address and rate limits lock everyone out together. Leave `none` if visitors reach the API directly (the header could be forged). |
| `DATABASE_POOL_SIZE` | no | no | `10` | Connections kept open per process. See sizing below. |
| `DATABASE_MAX_OVERFLOW` | no | no | `5` | Extra connections allowed per process in a burst. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | no | no | `15` | Life of a login token. |
| `REFRESH_TOKEN_EXPIRE_DAYS` | no | no | `30` | How long a device stays signed in. |
| `JWT_ALGORITHM` | no | no | `HS256` | Leave alone. |
| `API_V1_PREFIX` | no | no | `/api/v1` | Leave alone: the web app expects it. |
| `APP_NAME` | no | no | `Alumni Challenge API` | Title shown in the API docs. |
| `DEBUG` | no | no | `false` | Never `true` in production (logs every SQL statement). |
| `WEB_CONCURRENCY` | no | no | `2` | uvicorn processes per api container (set in the image). Not read by the app itself. |

**Database connection sizing.** Each api process can open up to `DATABASE_POOL_SIZE +
DATABASE_MAX_OVERFLOW` = 15 connections. With `WEB_CONCURRENCY=2` that is 30 per api container,
plus about 15 for the worker. PostgreSQL allows 100 by default, so run **at most 2 api
containers** with these defaults, or lower the pool size. The formula:
`api_containers x WEB_CONCURRENCY x (pool + overflow) + 15 < max_connections`.

## 5. Start commands

All three use the image from section 2.

**Migrations (run first, to completion, on every deploy):**

```
alembic upgrade head
```

In Coolify this is the "pre-deployment command" of the api service, or a separate one-off
service. If it fails, **do not start the new api**: the old one keeps running on the old
schema. Take a database backup (section 8) before any deploy that adds a migration.

**API (the image's default command, nothing to set):**

```
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${WEB_CONCURRENCY} --no-access-log
```

Health check URL for the platform: `GET /health/live` (is the process alive). To decide
whether to send traffic, use `GET /health/ready` (database reachable).

**Worker (override the command, run exactly one):**

```
arq app.worker.WorkerSettings
```

The worker needs the same environment variables as the API. Healthcheck for it:
`arq --check app.worker.WorkerSettings` (exit 0 means healthy). Two workers would not break
anything (jobs are locked per row) but are not needed.

**First administrator** (one time, after the first deploy; opens a prompt for the password):

```
python -m app.cli create-super-admin you@example.org
```

Run it as a one-off command in the api container. `seed-demo` exists for developers and
**refuses to run unless `ENVIRONMENT=development`**; never run it here.

## 6. Order of a deploy

1. Back up the database (section 8) if this deploy has a migration.
2. Build and push the image `alumni-api:<version>`.
3. Run the migration command with the new image. Wait for it to finish successfully.
4. Start the new api containers; wait until `/health/ready` is OK; then stop the old ones.
5. Restart the worker on the new image (it must run the same code as the api).
6. Run the post-deploy tests (section 9).

**Rollback.** Redeploy the previous image tag for the api and the worker. Migrations are not
rolled back automatically: most are additive and the old code runs fine on the new schema. If
a migration must be undone, restore the pre-deploy backup (section 8) rather than running
`alembic downgrade` on live data.

## 7. Cloudflare

* Proxy the API's DNS record (orange cloud). SSL/TLS mode: **Full (strict)**.
* Set `TRUSTED_CLIENT_IP_HEADER=cf-connecting-ip` (section 4).
* Firewall the origin so only Cloudflare can reach port 8000 / 443. If the origin is reachable
  directly, anyone can send a fake `CF-Connecting-IP` and dodge the rate limits.
* The API already sends the right cache headers: public pictures (`/api/v1/files/<id>/content`
  for logos and posters) are cacheable for a year; private ones (avatars) are not shared-cacheable.
  A Cloudflare cache rule for that path is optional and **not yet tested**.
* Enable the managed WAF rules and a rate-limiting rule on `/api/v1/auth/*` as a second layer.
  **Not yet tested**; the app has its own limits on every write route regardless.

## 8. Backups

`scripts/backup-db.sh` writes one compressed, owner-only dump and reads it back to prove it is
valid. `scripts/restore-db.sh` restores one, and refuses a non-empty target unless told.

```
# on a machine with postgresql-client-17 installed (or inside the postgres container)
DATABASE_URL='postgresql://user:password@host:5432/alumni' scripts/backup-db.sh /backups/alumni-$(date -u +%F).dump
```

Do this every day (a scheduled task in Coolify), then **copy the file off the server** to the
backups bucket, for example `aws s3 cp --endpoint-url https://<account-id>.r2.cloudflarestorage.com
/backups/alumni-2026-11-07.dump s3://alumni-backups/`. Keep 30 days of dailies. A dump that only
exists on the database server is not a backup.

**Rehearse a restore once a month, and before launch**, into a new empty database, never the
live one:

```
createdb alumni_restore_test
scripts/restore-db.sh alumni-2026-11-07.dump postgresql://user:password@host:5432/alumni_restore_test
```

It prints every table's row count and the schema version. Compare with the live database.
The scripts were run against the development database (59 users): counts and schema version matched,
a non-empty target and a corrupt file were both refused. The off-server copy step and the
schedule are **not yet tested**: they depend on your R2 token and your scheduler.

Uploaded pictures live in the R2 bucket, not the database. Keep object versioning on, and
restore a lost picture from a previous version.

## 9. Test after every deploy

Replace `API` with the API address. A second person should do the email steps with an address
they can read.

1. `curl -s API/health/live` is `{"status":"alive"}`.
2. `curl -s API/health/ready` is `{"status":"ready","database":"up","redis":"up"}`.
3. `curl -s -o /dev/null -w '%{http_code}' API/api/v1/docs` is **404** in production (the docs
   page is off).
4. Response headers on any call include `strict-transport-security`, `x-content-type-options:
   nosniff` and `x-request-id`: `curl -sI API/health/live`.
5. **Sign up** in the web app with a real address. Within about a minute a "Verify your
   Alumni Challenge email" message arrives. Its link starts with the `FRONTEND_URL`, followed by
   `/verify-email?token=`. Click it: the account shows as verified.
6. **Forgot password:** request a reset, receive the email (link ends `/reset-password?token=`),
   set a new password, sign in with it. Using the same link a second time fails.
7. If an email does not arrive in five minutes, check the worker is running and look at the queue:
   `select event_type, attempts, last_error from domain_events where status <> 'dispatched' order by created_at;`
   Events with `status = 'failed'` gave up after 5 tries (waits of 30 s, 2 min, 10 min, 1 h).
8. **Upload:** in the profile page set an avatar. It shows. Copy the picture's address (it ends
   `?token=...`), remove the `?token=...` part and open it: **404**. The first address, within
   five minutes, works.
9. **Logo:** as an organization admin set a logo. Open its address in a private window with no
   login: it loads.
10. **Rate limit:** `for i in $(seq 1 35); do curl -s -o /dev/null -w '%{http_code} ' -X POST
    API/api/v1/auth/logout -H 'content-type: application/json' -d '{"refresh_token":"x"}'; done`
    shows `401` thirty times, then `429`. (Wait a minute before real use from that address.)
11. **Real visitor address:** after step 10, sign in from a different network. If that is also
    answered `429`, `TRUSTED_CLIENT_IP_HEADER` is not set and everyone shares one address.
12. **Sentry:** run in the api container
    `python -c "from app.core.config import get_settings; from app.core.observability import init_sentry; import sentry_sdk; init_sentry(get_settings()); sentry_sdk.capture_message('deploy check'); sentry_sdk.flush()"`
    and see "deploy check" in the Sentry project, with no token or email address in it.
13. **Worker:** `arq --check app.worker.WorkerSettings` exits 0 in the worker container.
14. **Backup:** run `scripts/backup-db.sh` once and restore it to a scratch database (section 8).
15. **Deletion and export:** as a throwaway account, download "my data", then delete the
    account. Sign-in with it no longer works, and the same address can register again.

## 10. What is not done

* No automatic deploy pipeline: CI builds and tests the image on every push, but does not
  publish or deploy it. A container registry and Coolify's git/webhook deploy are yours to set up.
* No staging environment has been created; the same steps apply with `ENVIRONMENT=staging`.
* No metrics dashboard or alerting beyond Sentry errors and the platform's health checks.
* Uploads are not virus-scanned and have no thumbnails yet.
* After a password change, another device's already-issued login token works for up to 15
  minutes (its refresh token is revoked at once).
* Events, bookings and payments are not built yet.
