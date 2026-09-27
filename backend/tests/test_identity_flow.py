import uuid

from httpx import AsyncClient


def _unique_email() -> str:
    return f"test-{uuid.uuid4().hex[:12]}@example.com"


async def test_register_creates_user(client: AsyncClient) -> None:
    email = _unique_email()
    response = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": "correct-horse-battery"}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == email
    assert body["status"] == "active"
    assert "id" in body


async def test_register_duplicate_email_is_rejected(client: AsyncClient) -> None:
    email = _unique_email()
    payload = {"email": email, "password": "correct-horse-battery"}

    first = await client.post("/api/v1/auth/register", json=payload)
    assert first.status_code == 201

    second = await client.post("/api/v1/auth/register", json=payload)
    assert second.status_code == 409


async def test_login_with_correct_credentials_returns_tokens(client: AsyncClient) -> None:
    email = _unique_email()
    password = "correct-horse-battery"
    await client.post("/api/v1/auth/register", json={"email": email, "password": password})

    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"


async def test_login_with_wrong_password_is_rejected(client: AsyncClient) -> None:
    email = _unique_email()
    await client.post(
        "/api/v1/auth/register", json={"email": email, "password": "correct-horse-battery"}
    )

    response = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "wrong-password"}
    )
    assert response.status_code == 401


async def test_login_nonexistent_user_gives_same_error_as_wrong_password(
    client: AsyncClient,
) -> None:
    """
    Security property, not just a status code: the error must be
    indistinguishable whether the email exists or not, so a client
    can't enumerate registered accounts.
    """
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": _unique_email(), "password": "anything-at-all"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Invalid email or password."


async def test_me_requires_authentication(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


async def test_me_returns_current_user_with_valid_token(client: AsyncClient) -> None:
    email = _unique_email()
    password = "correct-horse-battery"
    await client.post("/api/v1/auth/register", json={"email": email, "password": password})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    access_token = login.json()["access_token"]

    response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200
    assert response.json()["email"] == email


async def test_refresh_rotates_token_and_old_one_stops_working(client: AsyncClient) -> None:
    email = _unique_email()
    password = "correct-horse-battery"
    await client.post("/api/v1/auth/register", json={"email": email, "password": password})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    old_refresh = login.json()["refresh_token"]

    refresh_response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": old_refresh}
    )
    assert refresh_response.status_code == 200
    new_access = refresh_response.json()["access_token"]
    new_refresh = refresh_response.json()["refresh_token"]
    # The refresh token must always be a new one — this is what
    # session rotation actually guarantees. The access token's JWT
    # payload has second-level precision, so it can legitimately be
    # identical if login and refresh land in the same second; that's
    # not a security property to assert on.
    assert new_refresh != old_refresh

    # The new access token must actually work.
    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {new_access}"})
    assert me.status_code == 200

    # Reusing the OLD refresh token must now fail — it was rotated out.
    reuse = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert reuse.status_code == 401


async def test_logout_revokes_the_session(client: AsyncClient) -> None:
    email = _unique_email()
    password = "correct-horse-battery"
    await client.post("/api/v1/auth/register", json={"email": email, "password": password})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    access_token = login.json()["access_token"]
    refresh_token = login.json()["refresh_token"]

    logout = await client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert logout.status_code == 204

    # The refresh token must be dead now.
    reuse = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert reuse.status_code == 401


async def test_list_sessions_shows_only_own_sessions(client: AsyncClient) -> None:
    email = _unique_email()
    password = "correct-horse-battery"
    await client.post("/api/v1/auth/register", json={"email": email, "password": password})
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    access_token = login.json()["access_token"]

    response = await client.get(
        "/api/v1/auth/sessions", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert response.status_code == 200
    sessions = response.json()
    assert len(sessions) == 1
