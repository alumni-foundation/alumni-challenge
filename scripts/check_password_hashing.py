"""
Post-deploy check: does password hashing give the right answer on THIS server?

Hashes a password and verifies it, N times (default 200), with the app's own hasher and
settings. Exits 1 if any round goes wrong, 0 if all are right. No database or Redis needed.

Why it exists: on one machine the Argon2 library with its default four lanes gave a wrong answer
about 2.5% of the time (a right password refused). The app now uses one lane; run this once
after the first deploy on each new kind of host, and again after a base-image or library bump.

Run it inside the API container, from the app directory (the image has no scripts/ folder, so
send the file in on standard input):

    docker exec -i <api-container> python - 200 < scripts/check_password_hashing.py

or, from a checkout:  cd backend && uv run python ../scripts/check_password_hashing.py 200
"""

import os
import sys
import time

sys.path.insert(0, os.getcwd())  # the app directory, whichever way this is run

from app.modules.identity.security import hash_password, verify_password  # noqa: E402

PASSWORD = "correct-horse-battery"
WRONG = "correct-horse-batterz"


def main() -> int:
    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    first_verify_wrong = never_verifies = accepts_wrong = 0
    started = time.perf_counter()
    for _ in range(rounds):
        stored = hash_password(PASSWORD)
        if not verify_password(PASSWORD, stored):
            if verify_password(PASSWORD, stored):
                first_verify_wrong += 1  # the hash is fine, the first check was wrong
            else:
                never_verifies += 1  # the hash itself is wrong
        if verify_password(WRONG, stored):
            accepts_wrong += 1
    seconds = time.perf_counter() - started
    print(f"hash format: {stored.split('$')[3]}")
    per_operation = seconds / (rounds * 3) * 1000  # a round is one hash and two verifies
    print(f"{rounds} rounds in {seconds:.1f}s (about {per_operation:.0f} ms per hash or verify)")
    print(f"right password refused, hash fine:  {first_verify_wrong}")
    print(f"hash that never verifies:           {never_verifies}")
    print(f"wrong password accepted:            {accepts_wrong}")
    bad = first_verify_wrong + never_verifies + accepts_wrong
    print("OK" if bad == 0 else f"FAIL: {bad} wrong answers. Do not go live; see DEPLOYMENT.md.")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
