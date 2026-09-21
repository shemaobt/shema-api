import pytest

from app.core.exceptions import AuthenticationError, AuthorizationError, ConflictError
from app.models.auth import UserSignupRequest
from app.services import auth_service
from app.utils.jwt import decode_token
from tests.baker import make_user


def test_hash_password_and_verify() -> None:
    password = "super-secret-123"
    hashed = auth_service.hash_password(password)
    assert hashed != password
    assert auth_service.verify_password(password, hashed)
    assert not auth_service.verify_password("wrong-password", hashed)


async def test_get_user_by_email_returns_user(db_session) -> None:
    await make_user(db_session, email="alice@example.com")
    user = await auth_service.get_user_by_email(db_session, "alice@example.com")
    assert user is not None
    assert user.email == "alice@example.com"


async def test_get_user_by_email_returns_none_when_missing(db_session) -> None:
    user = await auth_service.get_user_by_email(db_session, "nobody@example.com")
    assert user is None


async def test_get_user_by_id_returns_user(db_session) -> None:
    created = await make_user(db_session, email="bob@example.com")
    user = await auth_service.get_user_by_id(db_session, created.id)
    assert user is not None
    assert user.id == created.id


async def test_get_user_by_id_returns_none_when_missing(db_session) -> None:
    user = await auth_service.get_user_by_id(db_session, "00000000-0000-0000-0000-000000000000")
    assert user is None


async def test_signup_user_creates_user(db_session) -> None:
    payload = UserSignupRequest(
        email="new@example.com",
        password="password123",
        display_name="New User",
    )
    user = await auth_service.signup_user(db_session, payload)
    assert user.email == "new@example.com"
    assert user.display_name == "New User"
    assert auth_service.verify_password("password123", user.password_hash)


async def test_signup_user_raises_conflict_when_email_exists(db_session) -> None:
    await make_user(db_session, email="taken@example.com")
    payload = UserSignupRequest(
        email="taken@example.com",
        password="password123",
        display_name="Duplicate",
    )
    with pytest.raises(ConflictError, match="Email already exists"):
        await auth_service.signup_user(db_session, payload)


async def test_authenticate_user_returns_user_when_valid(db_session) -> None:
    await make_user(db_session, email="valid@example.com", password="secret456")
    user = await auth_service.authenticate_user(db_session, "valid@example.com", "secret456")
    assert user is not None
    assert user.email == "valid@example.com"


async def test_authenticate_user_raises_when_wrong_password(db_session) -> None:
    await make_user(db_session, email="valid@example.com", password="secret456")
    with pytest.raises(AuthenticationError, match="Invalid credentials"):
        await auth_service.authenticate_user(db_session, "valid@example.com", "wrong")


async def test_authenticate_user_raises_when_user_inactive(db_session) -> None:
    await make_user(db_session, email="inactive@example.com", is_active=False)
    with pytest.raises(AuthorizationError, match="Inactive user"):
        await auth_service.authenticate_user(db_session, "inactive@example.com", "password123")


async def test_issue_tokens_returns_pair_and_persists_refresh(db_session) -> None:
    user = await make_user(db_session, email="token-user@example.com")
    access_token, refresh_token = await auth_service.issue_tokens(db_session, user)
    assert access_token
    assert refresh_token
    assert access_token != refresh_token
    payload = decode_token(access_token)
    assert payload.get("type") == "access"
    assert payload.get("sub") == user.id


async def test_refresh_access_token_returns_new_access_when_valid(db_session) -> None:
    user = await make_user(db_session, email="refresh@example.com")
    _, refresh_token = await auth_service.issue_tokens(db_session, user)
    new_access = await auth_service.refresh_access_token(db_session, refresh_token)
    assert new_access
    payload = decode_token(new_access)
    assert payload.get("type") == "access"
    assert payload.get("sub") == user.id


async def test_refresh_access_token_raises_when_token_revoked(db_session) -> None:
    user = await make_user(db_session, email="revoked@example.com")
    _, refresh_token = await auth_service.issue_tokens(db_session, user)
    await auth_service.revoke_refresh_token(db_session, refresh_token)
    with pytest.raises(AuthenticationError, match="revoked"):
        await auth_service.refresh_access_token(db_session, refresh_token)


async def test_get_current_user_from_access_token_returns_user(db_session) -> None:
    user = await make_user(db_session, email="me@example.com")
    access_token, _ = await auth_service.issue_tokens(db_session, user)
    current = await auth_service.get_current_user_from_access_token(db_session, access_token)
    assert current.id == user.id
    assert current.email == user.email


async def test_get_current_user_from_access_token_raises_when_inactive(db_session) -> None:
    user = await make_user(db_session, email="inactive-me@example.com", is_active=False)
    access_token, _ = await auth_service.issue_tokens(db_session, user)
    with pytest.raises(AuthorizationError, match="Inactive user"):
        await auth_service.get_current_user_from_access_token(db_session, access_token)


async def test_revoke_refresh_token_idempotent_when_already_revoked(db_session) -> None:
    user = await make_user(db_session, email="double-revoke@example.com")
    _, refresh_token = await auth_service.issue_tokens(db_session, user)
    await auth_service.revoke_refresh_token(db_session, refresh_token)
    await auth_service.revoke_refresh_token(db_session, refresh_token)
