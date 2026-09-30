# Update: eCitizen-style top bar, flatter cards

## Apply (WSL, from repo root)

    unzip -o /mnt/c/Users/Administrator/Downloads/alumni-challenge-update-7.zip -d ~/projects/alumni-challenge/
    cd ~/projects/alumni-challenge
    git add . && git commit -m "Top bar with Messages/Notifications icons, flatten card shadows" && git push

3 files only — no backend, no migration. Restart the dev server if it's running (`cd web && npm run dev`).

`npx tsc --noEmit`, `npx eslint .` (0 errors), and `npx next build` all pass clean.

## What changed

- **Top bar** (desktop and mobile): a search field (visually present, disabled — no global search endpoint exists yet, so it's honest about not working rather than faking it) and two plain circular icon buttons — Messages and Notifications — styled like eCitizen's outline icon buttons rather than filled chips. Both are correctly placed but inert, matching the "Soon" treatment already used in the sidebar for those same two features.
- **Cards are flatter now** — shadows across the whole app were carrying too much of the visual weight; cut them down to almost nothing and let a solid border do the defining instead. This is a one-line token change in `globals.css` (`--shadow-resting/raised/lifted`), so every card in the app picked it up at once — directory cards, school/partner cards, the home page — without needing to touch each page individually.

## Next, once you've looked at it

Tell me which specific pages still don't feel right against the eCitizen reference — the list-card layout (logo + title + description + corner icon, like their "Agencies" grid) is the next natural piece if you want that pattern on Schools/Partners/Alumni, and a working global search is the other obvious follow-up once you're ready for it.
