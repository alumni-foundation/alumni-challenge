# Alumni Challenge: web app

Next.js (App Router, TypeScript strict, Tailwind). It talks to the API from the server; the browser only
talks to this app. Read `AGENTS.md` first: this Next.js version differs from older ones.

## Run

You need the API running (`docker compose up -d` in the repo root, API on http://localhost:8000).

```
npm ci
npm run dev        # http://localhost:3000
```

Demo accounts: `docker compose exec api uv run python -m app.cli seed-demo` prints the shared password once.
Keep it in an untracked file (`web/.env.demo-accounts` is ignored by git).

## Check (all must pass before a commit)

```
npm run typecheck
npm run lint
npm test
npm run build
```

After the API's schema changes: `npm run api:types` regenerates `src/lib/api/schema.d.ts`.

## Environment variables

| Variable | When | Meaning |
|---|---|---|
| `API_URL` | runtime, server | The API's address, for example `http://localhost:8000`. Defaults to that in development; **required** in production. |
| `NEXT_PUBLIC_CONTACT_EMAIL` | build time | Address shown for "contact support". Baked into the build: change it, rebuild. |

## Production

`Dockerfile` builds the standalone server (non-root, health check at `/api/health`). Build and start
commands, Cloudflare and the post-deploy checks are in `../docs/DEPLOYMENT.md`, Part 2.
