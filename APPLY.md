# Update: real image in the hero, no dark card

## Apply (WSL, from repo root)

    unzip -o /mnt/c/Users/Administrator/Downloads/alumni-challenge-update-10.zip -d ~/projects/alumni-challenge/
    cd ~/projects/alumni-challenge
    git add . && git commit -m "Hero: real background image instead of flat gradient" && git push

2 files — the page and the image itself. No backend touched. Restart `npm run dev` if running.

`npx tsc --noEmit`, `npx eslint .` (0 errors), `npx next build` all pass clean.

## What changed

The hero background is the crowd photo you sent, now living at `web/public/images/hero-demo.jpg`, stretched full-bleed edge to edge with `background-size: cover`. A flat dark overlay sits on top (80% opacity) so the white headline, search bar, and icons stay legible wherever they land on the image — picked flat rather than a fade because the photo is bright sky at the top, exactly where the white headline text sits, so a gradient that lightened toward the top would have made the text unreadable there.

This is explicitly a placeholder, as you said — swap `web/public/images/hero-demo.jpg` for a real photo (graduation, campus, an alumni event) whenever you have one and nothing else changes; same filename, same spot, same overlay treatment.
