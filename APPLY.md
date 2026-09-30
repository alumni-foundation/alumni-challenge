# Update: frontend visual redesign — depth, sidebar, mobile nav

## Apply (WSL, from repo root)

    unzip -o /mnt/c/Users/Administrator/Downloads/alumni-challenge-update-5.zip -d ~/projects/alumni-challenge/
    cd ~/projects/alumni-challenge
    git add . && git commit -m "Frontend: real depth, richer sidebar, mobile bottom nav" && git push

Only 4 files changed — no backend, no migration, no `npm install` needed. Just restart the dev server if it's running:

    cd web
    npm run dev

`npx tsc --noEmit`, `npx eslint .` (0 errors), and `npx next build` all pass clean.

## What changed, and why

**The flat "SaaS card kit" look** — every card was white, same soft shadow, same red icon. Fixed with:
- A real elevation system (`resting` / `raised` / `lifted` — three distinct shadow weights instead of one uniform shadow everywhere).
- `IconChip` — a small tinted-background icon container (brand red, gold, blue, green) so cards in the same row read as *different kinds of things* rather than four copies of the same card with different text.
- A `StatTile` component for a data-forward stats strip.

**The sidebar looked "patched"** — it was one flat `#16161a` fill. Now it's a gradient (`side` → `side-deep`) with a soft brand-red glow at the top, a proper border under the logo lockup, and active nav items get a filled icon chip instead of just a background color on the whole row. Nav is also split into "primary" and "more" sections with a label, instead of one long flat list.

**Home page felt like a grid of nav buttons, not a real app** — added a hero welcome banner (dark, same gradient as the sidebar, so it reads as one design system) and a stats strip above the quick actions (alumni count, connections, schools, verification status) — all from data the page was already fetching, no new API calls.

**Mobile nav** — this was the biggest functional change. Replaced the hamburger-opens-a-squeezed-sidebar pattern with a **real bottom tab bar** (Home / Alumni / Connections / Schools, plus a "More" tab that opens a bottom sheet for everything else — Partners, the "Soon" items, Settings, sign out). This is the standard mobile-app navigation pattern, not a shrunk desktop nav.

**Color palette** — canvas background moved from a cold flat grey to a warm off-white, added a gold accent for prestige/verification-adjacent content (school badges, verification stat), refined the brand red slightly. A barely-visible dot texture sits behind the main content so it doesn't read as an empty flat fill.

## What this doesn't touch

Only `globals.css`, `ui/index.tsx`, `app-shell.tsx`, and the home page were changed. Every other page (alumni directory, connections, schools, settings, etc.) automatically inherits the new `Card` elevation and colors since they all use the shared `Card` component — but their own layouts weren't individually redesigned. If any of them still look off once you see this live, tell me which ones and I'll do a focused pass on just those.
