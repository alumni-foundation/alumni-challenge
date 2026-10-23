# Admin section, step 1

Frontend only. No backend changes, no new packages.

    unzip -o admin-step1.zip -d ~/projects/alumni-challenge/
    cd ~/projects/alumni-challenge && git add . && git commit -m "Admin section: landing, organizations, activity log" && git push

Routes: /admin, /admin/organizations, /admin/organizations/[id], /admin/activity
Nav: "Admin" link shows only for admin, super_admin, moderator, school_admin, partner_admin.
Reports card on /admin is marked "Coming soon" until the moderation screens are built.
