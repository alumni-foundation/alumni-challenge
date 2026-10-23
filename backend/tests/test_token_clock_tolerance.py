import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest

from app.core.config import get_settings
from app.modules.identity import security

settings = get_settings()


def _token(*, token_type: str, exp_offset: int, iat_offset: int = 0) -> str:
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": str(uuid.uuid4()),
        "type": token_type,
        "iat": now + timedelta(seconds=iat_offset),
        "exp": now + timedelta(seconds=exp_offset),
    }
    return jwt.encode(
        payload, settings.secret_key.get_secret_value(), algorithm=settings.jwt_algorithm
    )


def test_the_leeway_is_never_more_than_ten_seconds() -> None:
    assert 0 < security.JWT_LEEWAY_SECONDS <= 10


def test_an_access_token_that_expired_a_moment_ago_is_still_accepted() -> None:
    security.decode_access_token(_token(token_type="access", exp_offset=-3))


def test_an_access_token_expired_beyond_the_leeway_is_rejected() -> None:
    with pytest.raises(jwt.ExpiredSignatureError):
        security.decode_access_token(_token(token_type="access", exp_offset=-30))


def test_an_access_token_issued_two_minutes_in_the_future_is_rejected() -> None:
    # What a clock that is two minutes wrong looks like to the other side. This must
    # fail: the leeway is not there to hide a machine with the wrong time.
    with pytest.raises(jwt.ImmatureSignatureError):
        security.decode_access_token(_token(token_type="access", exp_offset=900, iat_offset=120))


def test_a_purpose_token_expired_beyond_the_leeway_is_rejected() -> None:
    with pytest.raises(jwt.ExpiredSignatureError):
        security.decode_purpose_token(
            _token(token_type="email_verify", exp_offset=-30), purpose="email_verify"
        )


def test_a_purpose_token_expired_a_moment_ago_is_still_accepted() -> None:
    security.decode_purpose_token(
        _token(token_type="email_verify", exp_offset=-3), purpose="email_verify"
    )
