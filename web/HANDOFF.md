# Web handoff

For a fresh session picking up the frontend (`web/`). Read this first, then `AGENTS.md` (Next.js 16 differs from
older versions: read `node_modules/next/dist/docs/` before using an API you are unsure of). The backend is another
agent's: **never edit `backend/`**. The user is not a developer by trade: report in plain words, with screenshots.

## 1. Design rules (the look is settled; do not drift)

- **Light only.** Ivory canvas `#faf6ee`, surfaces `#fffdf9`, deep warm ink `#1b1713`. There is no dark palette.
  Tokens live in `src/app/globals.css` (colours, radii, shadows, type scale). Nothing outside `components/ui` should
  use a raw colour; the few exceptions are photo overlays (dark scrims, `#ecc98f` gold on photos).
- **Buttons are pills.** Primary on pages is the *dark* ink pill (`<Button variant="dark">`, or `LinkButton variant="dark"`).
  Secondary is a quiet outlined pill. Crest red (`brand`, `brand-ink`) is for small accents: links, badges, active
  rail tile, counts. **Gold** is for highlights only: verified marks, big numbers, progress, date tiles.
- **Fonts.** Cormorant Garamond (`font-serif`) **only for text 28px and up**: landing and section headings, page
  titles (`text-title` = 28px, `text-display`, `text-hero`). Everything smaller is Jost, including card titles, tables,
  forms, buttons, nav. `h1`/`h2` get the serif automatically only with those size classes (see `globals.css`).
  Italic accent word: `<em className="accent-serif">`.
- **Icons.** `Icon3D` (`components/ui/icon3d`) tiles: tones ember, gold, moss, sky, ink, paper; sizes sm/md/lg. Plain
  line icons (lucide) only inside text rows.
- **Bar rows.** Lists on Home, Bookings, Tickets and event lists use `components/home/bars.tsx` (`BarList`, `Bar`,
  `BarHeader`): soft rounded bars about 64px high, subtle hover lift, columns on md+, stacked on phones.
- **Motion** is subtle: CSS keyframes, transform and opacity only, nothing under `prefers-reduced-motion`.
  Entrances: sign-in pages (`auth-*` in `globals.css`, `(auth)/template.tsx`), Home (`.page-enter`), landing cards
  (`components/ui/reveal.tsx`, `[data-reveal]`).
- **Frosted glass** only where asked (`.auth-card`, `.hero-glass`), always with a solid fallback for no-blur and
  `prefers-reduced-transparency`.

## 2. Quality rules (every screen, every time)

- **AA contrast, measured, not eyeballed.** For text on a photo, measure against the *worst pixels* behind it:
  hide the text (`color: transparent` via `addStyleTag`, with `bypassCSP: true`), screenshot, take the lightest and
  darkest pixel under each text range rect, compute WCAG ratio against the text colour (4.5, or 3 for large text).
  Use a viewport as tall as the page (no scrolling) so fixed bars are where the screenshot sees them. Input outlines
  need 3:1 (`.auth-card input` has a darker border for that).
- **Keyboard and focus.** Everything reachable by Tab, visible focus ring (`focus-visible:outline-2`), real buttons
  and links, dialogs return focus, errors announced (`role="alert"`), focus moves to the first field with an error.
- **Widths:** check 375, 768 and 1440 (and 1024 where a layout switches). **No horizontal overflow** (`scrollWidth >
  innerWidth`). Beware `fieldset` (needs `min-w-0`) and grid children (`min-w-0`).
- **Images:** `next/image` (AVIF/WebP, `sizes`, blur placeholder for static imports, `loading="eager"` +
  `fetchPriority="high"` for the one big hero image; Next 16 deprecates `priority`). Committed images <= ~300 KB.
  API pictures (logos, posters) come through the file proxy `/api/v1/files/:id/content`; posters use `next/image`
  via `images.localPatterns` in `next.config.ts`; school and partner logos are still plain `<img>`.
- Skeletons while loading, friendly empty states (never a blank or a broken-looking zero), plain-words errors.
- No `any`. Typecheck, lint, Vitest and build must pass. Light theme only.

## 3. Git rules

- `main` on GitHub rejects direct pushes. **Branch from `origin/development`, open a pull request into
  `development`, never into `main`, never push to either.** (A PR from `development` into `main` is the user's.)
- **Clean-clone gate before every push:** `git clone -b <branch> <local repo or worktree> /tmp/gate`, then in
  `web/`: `npm ci`, `npm run typecheck`, `npm run lint`, `npm test`, `npm run build`. All green, then push.
- `npm run typecheck` runs `next typegen` first, because `next-env.d.ts` is git-ignored (CI failed without it).
- `gh` is not installed and there is no token: you cannot open a PR. Push the branch and give the user the compare
  link `https://github.com/alumni-foundation/alumni-challenge/compare/development...<branch>?expand=1`.
  The repo is public: read workflow runs with `curl https://api.github.com/repos/alumni-foundation/alumni-challenge/actions/runs`.
  The `Web` workflow (`.github/workflows/web.yml`) triggers on pull requests to `main`, so a PR into `development`
  may show no Web run: say so, do not imply one.
- Use a **worktree** (`git worktree add /tmp/<name> -b <branch> origin/development`) for your work: the main
  checkout is shared with the backend agent and has their uncommitted files. Never `git reset --hard` it and never
  touch its `backend/` files. Local `main` carries unpushed commits from both agents.
- Do not change git or GitHub settings, and do not use other credentials. Small commits. Never commit
  `web/.env.demo-accounts`, passwords, or ticket codes. Commit trailer: `Co-Authored-By: Claude ...` as the harness says.
- **Unmerged work (as of writing):** `screen-2-home` (shell + Home), `screen-2b-home-v2` (Home v2, sidebar, bell),
  `screen-4-events-on-development` (events; contains Screens 2 and 2b as well, cherry-picked onto `development`).
  `screen-4-events` is an older copy stacked on 2b: superseded, can be deleted. Check what has merged before branching.

## 4. Screens built so far (routes, components, wiring)

Wiring in one paragraph: the browser never sees tokens. `src/lib/api/client.ts` calls `/api/backend/*` (route
handler `src/app/api/backend/[...path]/route.ts`: adds the bearer token, refreshes it, forwards `Idempotency-Key`
and the visitor's IP as `X-Visitor-IP` taken only from `CF-Connecting-IP`). Login/register/logout/forgot/reset/verify
go through `/api/auth/*`. Server components fetch public data with `src/lib/server/public-api.ts`. `src/proxy.ts`
gates routes (`src/lib/routes.ts` has the lists and `worksWithoutProfile`) and sets the CSP with a nonce.
Types: `src/lib/api/schema.d.ts` is generated (`npm run api:types`, from `http://localhost:8000`); aliases in
`src/lib/api/types.ts`; query hooks in `src/lib/api/hooks.ts`.

| Area | Routes | Main files | Wired to |
|---|---|---|---|
| Landing | `/` | `app/(landing)/*`, `components/landing/hero.tsx`, `sections.tsx`, `components/public/header.tsx` + `nav-links.tsx` | public orgs; header Home/Schools/Partners scroll within the page (`/#schools`), Contact goes to `/contact`; stat strip hidden unless 10+ schools and partners (`MIN_STAT`) |
| Public pages | `/schools`, `/partners` (+ `[id]`), `/terms`, `/privacy`, `/community-rules`, `/contact` | `app/(public)/*`, `components/public/*` | public orgs API |
| Sign-in | `/login`, `/register`, `/forgot-password`, `/reset-password`, `/verify-email` | `app/(auth)/layout.tsx` (photo), `template.tsx` (card, Back to home, caption, entrance), `caption.tsx` | `/api/auth/*`; login never disables its button (errors on submit, focus to first error); generic "Invalid email or password."; `account_suspended` by error code |
| Member shell | all member routes | `components/shell/app-shell.tsx` (dark sidebar rail, phone tabs, top bar, switch view, account menu), `notification-bell.tsx`; layout `app/(app)/layout.tsx` + `app-layout-client.tsx` | sidebar choice in cookie `ac_sidebar` (collapsed by default under 1280px); bell reads `useNotifications` (`lib/notifications.ts`) |
| Home | `/home` | `app/(app)/home/page.tsx`, `components/home/hero.tsx`, `cards.tsx`, `bars.tsx` | `/auth/me`, `alumni/profile/me`, `connections`, directory search, `events?limit=4`; Accept/Decline and Connect are real |
| Directory, Connections, Profile, Settings, Alumni profile | `/directory`, `/connections`, `/profile`, `/settings`, `/alumni/[id]` | `app/(app)/*`, `components/member/*`, `components/profile/*` | older screens: work, **not yet restyled** to the new look |
| Staff | `/admin/*`, `/school/*`, `/partner/*` | `app/(app)/admin`, `school`, `partner`, `components/org/*` | work, **not yet restyled**; they share the new sidebar (nav from `navFor` in `app-shell.tsx`) |
| Events | `/events`, `/events/[id]` | `app/(events)/*` (layout gives the app shell when signed in, public header when not), `components/events/*` | `events`, `events/{id}`, `events/{id}/bookings` (with `Idempotency-Key`); list is drawn on the server, filters in the URL; free/paid is filtered by the page (API has no price filter) |
| Bookings | `/bookings`, `/bookings/[id]` | `app/(app)/bookings/*`, `hold-countdown.tsx` | `bookings`, `bookings/{id}`, `/cancel`, `bookings/{id}/tickets` |
| Tickets | `/tickets` (mine), `/tickets/[code]` (public) | `app/(app)/tickets/page.tsx`, `app/(events)/tickets/[code]/page.tsx`, `ticket-qr.tsx` (QR drawn client-side with `uqr`), `claim-ticket.tsx` | `tickets/mine`, `tickets/{code}` (no sign-in), `tickets/claim` |
| Dev only | `/design-check` | `app/design-check/page.dev.tsx` (route exists only under `next dev`) | shows tokens, Icon3D, top-bar icon states |

Other places that know about events: Home (Next event card, Upcoming events bars), rail and bottom tabs (Events),
account menu (My bookings, My tickets), plain public header (Events link).

## 5. Decisions and known gaps (do not "fix" these without asking)

- **Payment:** `docs/events-api.md` has no payment endpoints yet (slice 5.5). A paid booking shows the hold, the
  amount, and a clearly labelled placeholder "Payment instructions will appear here". Do not invent steps.
- **No chat/messages button** in the live top bar (no messaging backend). The message icon and the bell exist,
  with default/hover/pressed/badge states, on `/design-check` only.
- **Bell** shows connection requests waiting for me, through `useNotifications()` which returns a normalised list;
  when a notifications API exists only that hook's source changes. Accept/Decline work in the panel.
- **Who's going and Connect on events** are not built (backend slice 5.3). Participants are sent with `listed: true`
  (the server default). Organizer screens are not built.
- **Ticket codes** (64 hex) are credentials: never log them, never put them in a URL except `/tickets/<code>`
  (`routes.ts` makes exactly that path public; the 401 redirect drops them; the ticket page is `no-store`, `noindex`,
  `no-referrer`). Logged-out visitors on a ticket page get a plain `/login` link (no `next`).
- **Hold expiry:** the server releases an expired hold when someone tries that session, and every minute by the
  worker job `expire_booking_holds`. The local dev `worker` container had been started before that job existed, so
  it never ran it: `docker compose restart worker` fixes it (not done by this session: the container is shared).
  The UI says "The places are released shortly" when the countdown ends, never "have been released".
- **Suspended banner:** wait until the backend returns `account_status` on profiles; do not fake it.
- **Events without a poster** show a gold date tile. Event view links are `/events/{id}`.
- **Accounts with no alumni profile** (staff, or not onboarded) may open `/events`, `/bookings`, `/tickets` and
  ticket links (`worksWithoutProfile` in `routes.ts`).
- **Windows-only quirk:** a locally built standalone server cannot resize images (libvips DLL missing), so
  `/_next/image` serves the original; the Linux Docker image optimises correctly. `.dockerignore`/`Dockerfile`
  exist; `docs/DEPLOYMENT.md` has the web section (private API, Cloudflare-only origin,
  `TRUSTED_CLIENT_IP_HEADER=x-visitor-ip` on the API).
- `schema.d.ts` was regenerated from the local API, which runs the backend agent's working tree.
- Fonts come from npm (`@fontsource-variable/jost`, `cormorant-garamond`), no network at build.

## 6. Run, preview, test

- **Needs:** Docker stack up (`docker compose up -d`: api on :8000, redis, postgres, mailpit :8025, worker).
  Demo data: `docker compose exec api uv run python -m app.cli seed-demo` (idempotent; adds the demo events
  Demo Alumni Meetup (free), Demo Careers Evening (KES 1,500), Demo Golf Day (KES 3,500, four tee times)).
  The shared demo password is in the untracked `web/.env.demo-accounts` (never commit it). Accounts:
  `demo.alumni.01..40@example.com`, `demo.super-admin@`, `demo.admin@`, `demo.moderator@`,
  `demo.school-admin.a|b|c@`, `demo.partner-admin.1|2@`, `demo.event-manager@`, `demo.sports-manager@`.
- **Production-like preview** (what to check in a browser; PowerShell): in `web/`: `npm ci`, `npm run build`, then
  copy `.next/static` to `.next/standalone/.next/static` and `public` to `.next/standalone/public`, then
  `$env:API_URL="http://localhost:8000"; $env:PORT="3000"; node .next\standalone\server.js`. `npm run start` warns
  with `output: standalone`. `next dev -p 3100` works too (the design-check page only exists there). Rebuild after
  every change. `API_URL` is required in production or every API call is a 503.
- **Tests:** `npm test` (Vitest, node environment: pure helpers in `src/lib/*.test.ts`, route handlers). UI is
  checked in a real browser with Playwright scripts (keep them in the session scratchpad, not the repo). Use the
  Playwright copy in the npx cache (`...\npm-cache\_npx\e41f203b7505f1fb`), `bypassCSP: true` for style injection.
- **Rate limits:** login is 20 per 15 minutes per IP. Clear between runs:
  `docker compose exec -T redis sh -c "redis-cli --scan --pattern 'ratelimit:*' | xargs -r redis-cli del"`. Never loosen
  a server rule to make a test pass.
- **Mail** goes to Mailpit (`http://localhost:8025`, API `/api/v1/search?query=to:<addr>` and `/api/v1/message/<id>`); it arrives from the worker queue, so allow a few seconds.
- Shell notes (Windows): no `pkill` (use `Get-NetTCPConnection -LocalPort 3000` and `Stop-Process`); Git Bash rewrites
  `/paths` in arguments (`MSYS_NO_PATHCONV=1`); `networkidle` can hang on pages that prefetch, use
  `domcontentloaded` plus a short wait; a Playwright `fullPage` screenshot moves fixed bars, so take screenshots in a
  viewport as tall as the page instead.
- Test data left in the dev DB: `qa.*` members, cancelled QA events. Cancel any throw-away event you publish
  (`POST /events/{id}/cancel` as `demo.super-admin`); do not leave test events published.

## 7. Screenshot folders (for the user, `C:\Users\Administrator\Pictures\Screenshots\`)

`hero-redo` (landing and shell), `login-redesign` (sign-in pages), `polish` (landing nav, sign-in entrance filmstrips
and videos), `screen2-home`, `screen2b` (Home v2, sidebar, bell, design-check), `screen4-events` (events,
bookings, tickets; `holdtest` has the one-seat sold-out / already-booked / hold-expiry run).
The reference images the user gave are in the same parent folder (`landing page.png`).

## 8. Next

The next job is the **admin dashboard** (staff shells: `/admin`, `/school/[id]`, `/partner/[id]`, restyle to the new
look). They already sit inside the new sidebar. Start from `origin/development`, follow section 3.
