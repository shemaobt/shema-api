"""Bootstrap proof for the sound-necklace module: the app + roles are seeded, and
``require_app_access`` gates the whole ``/api/sound-necklace`` surface.
"""

from __future__ import annotations

from sqlalchemy import select

from app.db.models.auth import App, Role
from scripts.seed_apps_roles import APP_ROLES_OVERRIDE, SEED_APPS
from tests.baker import make_user
from tests.test_sound_necklace.conftest import APP_KEY, auth_header, grant_role

SN = "/api/sound-necklace"


async def test_app_and_roles_are_seeded(db_session, sound_necklace_app):
    app = (await db_session.execute(select(App).where(App.app_key == APP_KEY))).scalar_one()
    role_keys = set(
        (await db_session.execute(select(Role.role_key).where(Role.app_id == app.id)))
        .scalars()
        .all()
    )
    assert {"facilitator", "project_admin"} <= role_keys


def test_seed_script_registers_the_app():
    """The real seed script (not just the test fixture) provisions the app + roles."""
    assert any(entry[0] == APP_KEY for entry in SEED_APPS)
    assert APP_ROLES_OVERRIDE[APP_KEY] == ["facilitator", "project_admin"]


async def test_unauthenticated_request_is_rejected(client, sound_necklace_app):
    res = await client.get(f"{SN}/sessions")
    assert res.status_code == 401


async def test_authenticated_without_app_access_is_forbidden(
    client, db_session, sound_necklace_app
):
    outsider = await make_user(db_session, email="outsider@example.com")
    headers = await auth_header(db_session, outsider)
    res = await client.get(f"{SN}/sessions", headers=headers)
    assert res.status_code == 403


async def test_member_passes_the_gate(client, db_session, sound_necklace_app):
    member = await make_user(db_session, email="member@example.com")
    await grant_role(db_session, sound_necklace_app.id, member.id, "facilitator")
    headers = await auth_header(db_session, member)
    res = await client.get(f"{SN}/sessions", headers=headers)
    # Gate passed → the member reaches the route, and reaches no one else's sessions.
    assert res.status_code == 200
    assert res.json() == {"sessions": []}
