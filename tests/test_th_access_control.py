import re
from pathlib import Path

import pytest
from sqlalchemy import select

from app.db.models.auth import App
from app.services.access_request._default_roles import (
    DEFAULT_ROLE_BY_APP_KEY,
    default_role_for,
)
from app.services.access_request.review_access_request import review_access_request
from app.services.authorization.has_role import has_role
from app.services.authorization.list_roles import list_roles
from scripts.seed_apps_roles import APP_ROLES_OVERRIDE, DEFAULT_ROLES, SEED_APPS
from tests.baker import grant_app_role, make_access_request, make_role, make_user


@pytest.mark.asyncio
async def test_user_without_th_role_has_no_access(db_session) -> None:
    user = await make_user(db_session, email="th_ac_a@test.com")
    roles = await list_roles(db_session, user.id, "translation-helper")
    assert roles == []


@pytest.mark.asyncio
async def test_user_with_th_role_can_access(db_session) -> None:
    th_app = (
        await db_session.execute(select(App).where(App.app_key == "translation-helper"))
    ).scalar_one()
    user = await make_user(db_session, email="th_ac_b@test.com")
    await grant_app_role(db_session, user, th_app, role_key="user", label="User")

    roles = await list_roles(db_session, user.id, "translation-helper")
    assert roles == [("translation-helper", "user")]
    assert await has_role(db_session, user.id, "translation-helper", "user") is True


@pytest.mark.asyncio
async def test_platform_admin_bypasses_role_in_access_control() -> None:
    """`require_app_access` short-circuits for platform admins (see access_control.py)."""
    from app.core.access_control import require_app_access

    dep = require_app_access("translation-helper")
    assert dep is not None


def test_default_role_map_pins_translation_helper_to_user() -> None:
    assert DEFAULT_ROLE_BY_APP_KEY["translation-helper"] == "user"
    assert default_role_for("translation-helper") == "user"
    assert default_role_for("meaning-map-generator") == "analyst"
    assert default_role_for("some-unknown-app") == "analyst"


#: Apps registered by their own Alembic migration rather than by the seed script, mapped to
#: the roles that migration inserts. The seed script's apps are derived rather than listed —
#: see ``_roles_defined_by_app``. ``test_migration_registered_apps_are_all_known`` fails if a
#: migration registers an app missing from here, which is how the next one gets caught.
ROLES_FROM_MIGRATIONS: dict[str, set[str]] = {
    "translation-helper": {"user"},
    "project-health": {"user", "admin"},
    "annotation-studio": {"admin", "facilitator"},
    "internalization-room": {"facilitator", "admin"},
}

#: Migrations that INSERT INTO apps declare their key in a module constant named ``APP_KEY``
#: or ``<PREFIX>_APP_KEY``; this finds those declarations without importing the migrations.
_MIGRATION_APP_KEY = re.compile(r'^[A-Z_]*APP_KEY[A-Z_]* *= *"([a-z0-9-]+)"', re.MULTILINE)
_VERSIONS_DIR = Path(__file__).resolve().parent.parent / "alembic" / "versions"


def _roles_defined_by_app() -> dict[str, set[str]]:
    """Every app the platform can approve access to, with the roles it actually defines.

    Derived from ``scripts/seed_apps_roles.py`` rather than restated, so an app added to
    ``SEED_APPS`` gets a case without anyone remembering to add one here. Migration-
    registered apps are layered on top and win, since their migration creates the rows.
    """
    roles = {key: set(APP_ROLES_OVERRIDE.get(key, DEFAULT_ROLES)) for key, *_ in SEED_APPS}
    return roles | ROLES_FROM_MIGRATIONS


ROLES_DEFINED_BY_APP = _roles_defined_by_app()


def test_migration_registered_apps_are_all_known() -> None:
    """A migration that registers an app must have its roles recorded here.

    Without this the parametrised guard below is only as good as someone's memory: an app it
    has never heard of produces no case at all and the suite stays green. That is exactly how
    ``internalization-room`` survived a change titled "every app".
    """
    registered = {
        key
        for path in _VERSIONS_DIR.glob("*.py")
        if "INSERT INTO apps" in (text := path.read_text())
        for key in _MIGRATION_APP_KEY.findall(text)
    }
    assert registered, "found no app-registering migrations — the discovery pattern broke"
    assert registered <= set(ROLES_DEFINED_BY_APP), (
        f"{sorted(registered - set(ROLES_DEFINED_BY_APP))} registered by migration but "
        f"absent from ROLES_DEFINED_BY_APP — add the roles their migration inserts"
    )


@pytest.mark.parametrize("app_key", sorted(ROLES_DEFINED_BY_APP))
def test_every_app_is_approvable(app_key: str) -> None:
    """Approval resolves to a role the app defines, for every app.

    Guards a bug that has now recurred four times. ``default_role_for`` falls back to
    ``analyst`` for any app missing from ``DEFAULT_ROLE_BY_APP_KEY``, and an app whose roles
    came from an override or from its own migration does not define ``analyst`` — so
    approval raised ``RoleError`` and granted nothing while the request still read as
    reviewed. ``translation-helper`` was fixed when it hit this, ``project-health`` in the
    commit before this one, and ``oral-collector``, ``sound-necklace`` and
    ``internalization-room`` here.

    The cases come from the seed script and the migration scan rather than from a list kept
    by hand, because a hand-kept list cannot fail for an app nobody remembered to add.
    """
    resolved = default_role_for(app_key)
    assert resolved in ROLES_DEFINED_BY_APP[app_key], (
        f"approving access to {app_key!r} would grant {resolved!r}, "
        f"which it does not define — add it to DEFAULT_ROLE_BY_APP_KEY"
    )


@pytest.mark.asyncio
async def test_review_approve_grants_user_role_for_translation_helper(db_session) -> None:
    """Smoke-tests the full request→approve→access path for translation-helper.

    Regression guard: approval previously hardcoded `"analyst"`, which doesn't
    exist for translation-helper, so approval raised RoleError. Now dispatched
    via DEFAULT_ROLE_BY_APP_KEY.
    """
    th_app = (
        await db_session.execute(select(App).where(App.app_key == "translation-helper"))
    ).scalar_one()
    await make_role(db_session, th_app.id, role_key="user", label="User", is_system=True)

    requester = await make_user(db_session, email="th_req@test.com")
    admin = await make_user(db_session, email="th_admin@test.com", is_platform_admin=True)
    access_request = await make_access_request(db_session, requester.id, th_app.id)

    reviewed = await review_access_request(db_session, admin, access_request.id, status="approved")
    assert reviewed.status == "approved"

    granted_roles = await list_roles(db_session, requester.id, "translation-helper")
    assert granted_roles == [("translation-helper", "user")]


@pytest.mark.asyncio
async def test_review_approve_grants_analyst_role_for_meaning_map(db_session) -> None:
    """Mirror of the TH test — confirms the legacy meaning-map flow is unbroken."""
    mm_app = (
        await db_session.execute(select(App).where(App.app_key == "meaning-map-generator"))
    ).scalar_one()
    await make_role(db_session, mm_app.id, role_key="analyst", label="Analyst", is_system=True)

    requester = await make_user(db_session, email="mm_req@test.com")
    admin = await make_user(db_session, email="mm_admin@test.com", is_platform_admin=True)
    access_request = await make_access_request(db_session, requester.id, mm_app.id)

    reviewed = await review_access_request(db_session, admin, access_request.id, status="approved")
    assert reviewed.status == "approved"

    granted_roles = await list_roles(db_session, requester.id, "meaning-map-generator")
    assert granted_roles == [("meaning-map-generator", "analyst")]
