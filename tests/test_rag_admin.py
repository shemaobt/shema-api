import pytest

from app.core.auth_middleware import require_platform_admin
from app.core.exceptions import AuthorizationError
from tests.baker import make_user


async def test_require_platform_admin_allows_admin(db_session) -> None:
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    result = await require_platform_admin(user=admin)
    assert result.id == admin.id


async def test_require_platform_admin_rejects_non_admin(db_session) -> None:
    user = await make_user(db_session, email="regular@example.com", is_platform_admin=False)
    with pytest.raises(AuthorizationError, match="Forbidden"):
        await require_platform_admin(user=user)
