# Update: web app scaffold + backend support endpoints

## Apply (WSL, from repo root)

    unzip -o /mnt/c/Users/Administrator/Downloads/alumni-challenge-update-2.zip -d ~/projects/alumni-challenge/
    cd ~/projects/alumni-challenge
    docker compose up -d --build
    cd web && npm install && cd ..
    git add . && git commit -m "Web app scaffold (Next.js) + connections/roles/directory API support" && git push

Paste back: the `npm install` output and the GitHub Actions result.

## What changed

Backend (covered by tests, 49/49 passing including 6 new ones, ruff + mypy clean):
- `GET /auth/me/roles` — caller's own active roles, for the sidebar and permission checks in the UI.
- `GET /connections` now also returns the other person's name (`other_full_name`, `other_profile_id`, `other_user_id`), so the UI isn't fetching profiles one by one. Blocked rows are hidden from both sides. Nothing beyond the name is exposed.
- `GET /alumni/directory` cards now include `profession`, `country`, `company` (same privacy rules as before — this only reached fields already visible to an authenticated viewer).
- `GET /organizations/{id}/email-domains` — school admins can list domains they've configured. Restricted the same way the POST already was.

Nothing was removed or changed in existing endpoints beyond adding fields; every prior test still passes unmodified.

## Frontend: `web/`

Next.js 16 (App Router, Turbopack), TypeScript strict, Tailwind v4, TanStack Query. API types are generated from the backend's own OpenAPI schema (`web/src/lib/api/schema.d.ts`) so the client can't silently drift from the API. Regenerate after any backend schema change:

    cd backend && uv run python -c "import json; from app.main import app; json.dump(app.openapi(), open('../web/openapi.json','w'))"
    cd ../web && npx openapi-typescript openapi.json -o src/lib/api/schema.d.ts

**Auth:** the refresh token lives in an httpOnly cookie; the access token never reaches browser JavaScript. Every API call goes through `/api/backend/[...path]`, a route handler that attaches the token server-side, refreshes it on expiry (de-duplicated across parallel requests, since the backend's refresh tokens rotate and reuse triggers a full session wipe), and blocks cross-origin writes.

**Pages built**, matched to what the API supports today: login/register, onboarding (first profile), home dashboard, alumni directory with search, alumni profile detail (connect, vouch, school-admin verify — buttons only appear for someone actually holding that role), profile edit (bio, skills, interests, visibility), connections (incoming/outgoing/accepted, accept/decline/remove), schools & partners list + detail, settings (active sessions, revoke, sign out).

**Not built**, because the backend doesn't have it yet: avatars/file upload, messaging, events, moderation, directory filters beyond search. These show as "Soon" in the sidebar rather than as broken links, so nothing looks half-finished.

`npx tsc --noEmit`, `npx eslint .` (0 errors), and `npx next build` all pass clean in the sandbox.

## Local dev

    cd web
    cp .env.example .env.local   # API_URL=http://localhost:8000
    npm run dev

## What's next (unchanged from HANDOFF.md)

Close the Phase 3 gaps before real users hit the login page: email verification, password recovery, rate limiting/lockout, audit log. The login/register screens are ready and waiting on those.
