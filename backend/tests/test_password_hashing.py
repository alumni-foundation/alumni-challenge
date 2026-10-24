"""
Regression for the register-then-login 401 that appeared now and then in full runs: with the
library's default of four Argon2 lanes, about 2.5% of hash-then-verify rounds in our container
gave a wrong answer (20 of 800), so a correct password was refused. See security.py.
"""

from argon2 import PasswordHasher

from app.modules.identity.security import hash_password, verify_password

PASSWORD = "correct-horse-battery"


def test_new_hashes_use_one_lane_and_keep_the_memory_and_time_cost() -> None:
    parts = hash_password(PASSWORD).split("$")
    assert parts[1] == "argon2id"
    assert parts[3] == "m=65536,t=3,p=1"


def test_a_hash_made_before_the_change_still_verifies() -> None:
    old = PasswordHasher(parallelism=4).hash(PASSWORD)
    assert "p=4" in old
    assert verify_password(PASSWORD, old)
    assert not verify_password(PASSWORD + "x", old)


def test_a_fresh_hash_always_verifies_and_a_wrong_password_never_does() -> None:
    # A smoke check, not a proof: the four-lane fault hit about one round in forty.
    for _ in range(30):
        stored = hash_password(PASSWORD)
        assert verify_password(PASSWORD, stored)
    assert not verify_password("not-the-password", stored)
