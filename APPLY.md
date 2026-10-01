# Update: match eCitizen proportions — wider container, no card in hero, bolder icons

## Apply (WSL, from repo root)

    unzip -o /mnt/c/Users/Administrator/Downloads/alumni-challenge-update-9.zip -d ~/projects/alumni-challenge/
    cd ~/projects/alumni-challenge
    git add . && git commit -m "Match eCitizen proportions: wider container, hero without a card, bolder icon buttons" && git push

3 files, no backend touched. Restart `npm run dev` if it's running.

`npx tsc --noEmit`, `npx eslint .` (0 errors), `npx next build` (all 17 routes) all pass clean.

## What was actually wrong, and what changed

1. **The hero had a white card in it — eCitizen's doesn't.** I'd wrapped the search bar and quick-action icons in a separate floating white card below the dark hero. That's not what the reference does: the search bar and icons sit directly on the dark background as one continuous block, in white/light color, with no card boundary anywhere. Cards only start once you're past the hero, in the content below. Fixed — the hero is now one unbroken dark section; the white card is gone.

2. **Container was too narrow everywhere.** `max-w-7xl` (1280px) was capping the nav bar, hero, and page content well short of the screen on any reasonably wide monitor, which is why it read as "squeezed" next to eCitizen's near-edge-to-edge layout. Widened to `1680px` consistently across the top nav, the hero, and the main content area, with more generous side padding to match.

3. **Logo was too small and cramped.** Doubled it (32px → 48px) and reset the type to show full-size always instead of hiding the wordmark below the `xl` breakpoint, matching the generous logo lockup in the reference. Nav bar itself is taller (64px → 96px) and the nav links got bigger text and more padding between them.

4. **Icon buttons had almost no contrast.** They were a thin border with muted gray icons — easy to miss. Now they're a filled light-gray circle with full-contrast dark icons, closer to the visibility eCitizen's icon buttons have.

## Where things stand now

That's the structural match done — wide layout, logo proportions, hero without a card, visible icon buttons. If there's anything left that still looks off once you run it, point me at the specific spot and I'll fix exactly that rather than another broad pass.
