# Deploying the Alumni Challenge API and web app

For the person setting up the servers. Sections 1 to 10 cover the backend (API + worker). The web app (`web/`, Next.js) is deployed separately
and only needs to know the API's address: its section is **Part 2** at the end.

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

## 2. The image

CI builds and publishes the production image to GitHub Container Registry on every push to
`main` that passes the tests. You do not build it yourself. It is named after the repository,
with `-api` on the end, and tagged with the git commit:

```
ghcr.io/<github-owner>/<repository>-api:<commit>
```

`<commit>` is either the full 40-character commit hash or its first 7 characters (for example
`ghcr.io/example-org/alumni-challenge-api:3d6bc54`). There is **no `latest` tag**: always
deploy a specific commit, so a running container can be traced to its code. Keep the last few
tags in use so a rollback is one redeploy.

The package is private by default. To pull it, create a GitHub token (a "personal access
token (classic)" with only `read:packages`) and enter your GitHub username and that token as the registry
login in your platform. In the repository's package settings, "Manage
Actions access" must list this repository with write access (it does by default for a package
CI creates).

Building by hand, only if you must (for example from a fork):

```
docker build --target production -t alumni-api:<commit> backend
```

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
`MAIL_BACKEND=resend` with `RESEND_API_KEY`, `TICKET_SIGNING_KEY` is set (32+ characters, different from `SECRET_KEY`), and `FRONTEND_URL` starts with `https://`.

| Variable | Secret | Required | Default | Meaning |
|---|---|---|---|---|
| `ENVIRONMENT` | no | yes | `development` | `production` (or `staging`). Switches on the checks above and turns off the API docs page. |
| `SECRET_KEY` | **yes** | yes | none | Signs login tokens. Changing it signs everyone out. 32+ random characters. |
| `TICKET_SIGNING_KEY` | **yes** | yes in production | derived from `SECRET_KEY` in development | Signs the QR codes on event tickets. Needs **32+ random characters** and must be **different from `SECRET_KEY`**. **Changing or losing it invalidates every ticket already issued** (printed or emailed QR codes stop working; an organizer can re-issue them one at a time). Keep a copy in the secret store. |
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
| `TRUSTED_CLIENT_IP_HEADER` | no | yes behind a proxy | `none` | Which request header carries the visitor's real address: `none`, `cf-connecting-ip` (API behind Cloudflare), `x-visitor-ip` (the web app sends it on every server-side call; API on the private network) or `x-forwarded-for`. Only the one named header is read; all others are ignored. Without it every visitor shares the proxy's address and rate limits lock everyone out together. **When this is set to anything but `none`, the API must not be publicly reachable** (no public address, or the origin locked to Cloudflare's ranges): anyone who can reach it directly can send that header and pick their own address, and so dodge every rate limit. Leave `none` if visitors reach the API directly. |
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
2. Wait for CI to publish the image for the commit you are deploying (section 2); a deploy
   of a commit whose CI run failed has no image.
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
16. **Password hashing:** once, after the first deploy (and after any base-image or library
    update), run `docker exec -i <api-container> python - 200 < scripts/check_password_hashing.py`.
    It needs no database, takes under a minute, and must end with `OK` and exit 0. Any
    "FAIL" means the host gives wrong Argon2 answers (a right password refused): do not go live;
    run a memory test on the host and tell the developers. Background: on one development
    machine the library's default four lanes gave a wrong answer about 2.5% of the time, so the
    app hashes with one lane (`app/modules/identity/security.py`). Whether that machine or the
    library was at fault is not confirmed.

## 10. What is not done

* No automatic deploy: CI publishes the image to GitHub Container Registry on every push to
  `main` (section 2), but nothing deploys it. Pointing Coolify (or whatever runs the
  containers) at the registry, and any webhook that triggers a redeploy, is yours to set up.
* The published image has not yet been pulled by a real server: the first push to `main` after
  this change is the first real test of the workflow. **Not yet tested.**
* No staging environment has been created; the same steps apply with `ENVIRONMENT=staging`.
* No metrics dashboard or alerting beyond Sentry errors and the platform's health checks.
* Uploads are not virus-scanned and have no thumbnails yet.
* After a password change, another device's already-issued login token works for up to 15
  minutes (its refresh token is revoked at once).
* **Registration reveals whether an email already has an account.** Registering with an
  address that exists answers 409, a new one 201. Left as is for launch on purpose: making
  both look the same means the sign-up screen could no longer sign the person in straight
  away (they would have to click the email link first), which costs real sign-ups. It is
  limited to 10 attempts an hour per address. Revisit if people report being targeted.
* **Failed sign-ins lock an account, not just the attacker.** After 5 wrong passwords for one
  email within 15 minutes that account refuses sign-in for 15 minutes, even with the right
  password. Anyone who knows an email can therefore lock that person out for short periods.
  Kept on purpose: it is the standard trade against unlimited password guessing, and the
  same wait applies to the real owner, who can also reset the password by email.
* Events, bookings and payments are not built yet.

---

# Part 2: the web app

The web app is a Next.js server (`web/`). It talks to the API **from the server**: the browser only
ever talks to the web app's own address, which forwards calls to the API. So the API does not need to
be reachable from visitors' browsers at all: in production it should stay on the private network and
only the web app should be public (see W4). Email links to the web app are built from the API's
`FRONTEND_URL`.

Proven by hand: the image below was built and run locally against the development API (health
check, sign-in, pictures, cookies, and the visitor-address header against unit tests). **Not yet tested:** behind a real Cloudflare zone on a real domain.

## W1. Build

From the repository root:

```
docker build -t alumni-web:<version> --build-arg NEXT_PUBLIC_CONTACT_EMAIL=support@example.org web
```

Use the git commit as `<version>`. The image runs as the unprivileged `node` user, contains no
`.env` and no source, and has its own health check.

Without Docker, from `web/`: `npm ci`, then `npm run build`, then start with
`API_URL=https://api.example.org npm run start` (port 3000, override with `PORT`).

## W2. Environment variables

| Variable | When read | Required | Meaning |
|---|---|---|---|
| `API_URL` | **runtime**, on the server | **yes** in production (the server answers 503 to every API call without it) | The API's address with no path and no trailing slash, as the web server reaches it: `https://api.example.org` or an internal address such as `http://api:8000`. Change it and restart; no rebuild. |
| `NEXT_PUBLIC_CONTACT_EMAIL` | **build time** (baked into the JavaScript) | no | Where "contact support" points. If unset, the contact page shows no address. Changing it needs a **rebuild** (`--build-arg`), not a restart. |
| `PORT` | runtime | no | Default `3000`. |
| `HOSTNAME` | runtime | no | Set to `0.0.0.0` in the image so the container is reachable. |
| `NODE_ENV` | | no | Set to `production` by the image and by `npm run start`. |

Anything else starting with `NEXT_PUBLIC_` would also be baked in at build time, so never put a
secret in one. The web app holds **no secrets**: sign-in cookies are issued from the API's tokens.

## W3. Start and health check

The image's default command is `node server.js`. Run as many copies as you like **except** that
token refresh sharing is per process: with more than one web container a visitor's parallel requests
can occasionally each refresh the same token and be signed out. Run **one** web container until
that is moved to Redis.

Health check URL for the platform: `GET /api/health` returns `{"status":"ok"}` while the process is
up. It does not call the API on purpose, so a short API outage does not restart the web app. The
image already runs this check every 30 seconds.

## W4. Behind Cloudflare

* Proxy the web DNS record (orange cloud). SSL/TLS mode **Full (strict)**; the origin must offer
  https to Cloudflare, or use Cloudflare Tunnel / the platform's own TLS.
* The app sets the `Secure` flag on its sign-in cookies when the request arrived over https. It
  decides from the `X-Forwarded-Proto` header, which Cloudflare and Coolify's proxy send. If your
  proxy does not send it and terminates TLS, cookies will not be marked Secure: tell the developer.
* **HSTS is left to Cloudflare.** Turn on "HTTP Strict Transport Security" in Cloudflare
  (SSL/TLS, Edge Certificates) once https works everywhere; the web app does not send it itself.
* **Content-Security-Policy** is sent by the web app on every page, with a new random nonce per
  request (so pages are never cached by Cloudflare, and a "Cache Everything" rule on HTML would break
  scripts: do not add one). Scripts, styles, images, fonts and connections are limited to the app's own
  address. If you add a third-party script (analytics, a chat widget), it will be blocked until the
  developer allows it in `web/src/lib/csp.ts`. Browser console messages starting "Refused to ..." are this policy.
* Pictures are fetched at `https://<web address>/api/v1/files/<id>/content`, which the web app
  forwards to the API. Public ones (logos) are sent with a one-year cache header. Cloudflare does not
  cache an address with no file extension by default; a cache rule for that path is optional and
  **not yet tested**.
* **The visitor's address.** The API limits sign-ins, sign-ups and resets per address, but every
  call it gets comes from the web server. So the web app reads `CF-Connecting-IP` (set by Cloudflare,
  not by the browser) and sends it to the API as `X-Visitor-IP` on **every** server-side call. Any
  `X-Visitor-IP` a browser sends is ignored (tested: `web/src/lib/server/visitor.test.ts`). A
  request with no `CF-Connecting-IP` gets no `X-Visitor-IP`, and the API then uses the web server's own
  address. In development, with no Cloudflare, the connection address is used instead.
  **API setting that goes with it: `TRUSTED_CLIENT_IP_HEADER=x-visitor-ip`** (not `cf-connecting-ip`,
  which is only right when Cloudflare sits in front of the API itself, as in Part 1 section 7).
  Leave it at `none` and the limits stay shared by all visitors.
* **Network shape.** Only the web app is public. The API stays on the private network: no public
  address, no Cloudflare record, reachable only from the web container (`API_URL=http://api:8000`).
  This is what makes `X-Visitor-IP` safe to believe: nobody else can send it to the API. If the API is
  also reachable from the internet, anyone can forge it and dodge every rate limit.
  Email links point at the web app (`FRONTEND_URL`), so nothing needs the API to be public.
* **The web origin accepts traffic only from Cloudflare.** Otherwise someone who finds the origin's
  address can send their own `CF-Connecting-IP` and be counted as anyone they like. Firewall the web
  server so ports 80/443 accept only [Cloudflare's address ranges](https://www.cloudflare.com/ips/)
  (or use Cloudflare Tunnel, which has no open port at all, or authenticated origin pulls). Check:
  `curl -s -H 'CF-Connecting-IP: 1.2.3.4' https://<origin address directly>/api/health` must time out or
  be refused, never answer. **Not yet tested on a real server.**
* Add Cloudflare's managed WAF rules and a rate-limiting rule on `/api/auth/*`. **Not yet tested.**

## W5. Test after every web deploy

Replace `WEB` with the web address.

1. `curl -s WEB/api/health` is `{"status":"ok"}`.
2. Open `WEB/` in a private window: the home page loads with no errors in the browser console.
3. Open a public school page (`WEB/schools`): its logo shows. In a private window too.
4. Sign in. In the browser's developer tools (Application, Cookies) `ac_access` and `ac_refresh` are
   `HttpOnly` and `Secure`.
5. Open Profile: your photo shows (if you have one). Copy the photo's address, remove `?token=...`
   and open it: **404**.
6. **Visitor address:** with `TRUSTED_CLIENT_IP_HEADER=x-visitor-ip` set on the API, sign in wrongly
   25 times from your own connection (20 are allowed per 15 minutes): the last ones answer "too many
   attempts". Then try once from a phone on mobile data: it must **not** be blocked. If it is, the
   address is not reaching the API.
7. **Origin closed:** `curl -s -H 'CF-Connecting-IP: 1.2.3.4' http://<origin address>/api/health` from
   outside Cloudflare times out or is refused.
