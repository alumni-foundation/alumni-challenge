# Update: move icon row below the hero, fill the space with copy

## Apply (WSL, from repo root)

    unzip -o /mnt/c/Users/Administrator/Downloads/alumni-challenge-update-11.zip -d ~/projects/alumni-challenge/
    cd ~/projects/alumni-challenge
    git add . && git commit -m "Move quick-action icons out of hero onto the page body" && git push

1 file. Restart `npm run dev` if running. Typecheck/lint/build all clean.

## What changed

The icon row (Browse alumni, Connections, Schools, etc.) is no longer inside the dark hero/search area — it's moved down onto the plain page body, right below the hero, on the normal light background (icons and labels switched from white to dark to match). The space that opened up under the search bar, inside the hero, is filled with a line of copy for now — swap that sentence for a real image whenever you're ready; the layout doesn't need to change to do it.
