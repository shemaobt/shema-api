"""BE-00's whole promise: this product is an application of the existing auth.

Nothing here tests authentication — that is shared surface, already covered.
What is tested is the registration: that the app key and the three role keys are
the ones the frontend already committed to, and that the guard they hang off
admits and refuses the right people.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import select

from app.api.resource_requests._deps import APP_KEY
from app.db.models.auth import Role
from app.services.access_request._default_roles import default_role_for
from scripts.seed_apps_roles import APP_ROLES_OVERRIDE, SEED_APPS
from tests.baker import grant_app_role, make_app, make_user
from tests.test_resource_requests.conftest import MESA_PROBE, PROBE, auth_header, grant

# The ids in resource-request-form/src/constants/capabilities.ts, in its order.
# BE-03 replaces this literal with a CI check against FE-22's contract.
FRONTEND_ROLE_IDS = ["equipe", "mesa", "gestor"]


class TestRegistration:
    def test_the_app_key_is_the_one_the_frontend_sends(self) -> None:
        # resource-request-form/src/constants/auth.ts — APP_KEY
        assert APP_KEY == "resource-request-form"

    def test_the_app_is_seeded_with_a_url(self) -> None:
        entry = next((row for row in SEED_APPS if row[0] == APP_KEY), None)
        assert entry is not None, f"{APP_KEY} missing from SEED_APPS"

        _key, name, app_url = entry
        assert name == "Resource Request Form"
        # Not decoration: request_password_reset builds {app_url}/reset-password?token=…
        assert app_url and app_url.startswith("https://")

    def test_the_seeded_roles_are_the_frontends_role_ids(self) -> None:
        assert APP_ROLES_OVERRIDE[APP_KEY] == FRONTEND_ROLE_IDS

    def test_seed_apps_has_no_duplicate_keys(self) -> None:
        keys = [row[0] for row in SEED_APPS]
        assert len(keys) == len(set(keys))

    def test_an_approved_access_request_grants_a_role_this_app_actually_has(self) -> None:
        """Without its own entry the dispatch falls back to `analyst`, which this app
        does not have — approval would raise RoleError instead of granting. The same
        regression translation-helper already hit once.
        """
        assert default_role_for(APP_KEY) == "equipe"
        assert default_role_for(APP_KEY) in APP_ROLES_OVERRIDE[APP_KEY]

    def test_the_app_key_is_named_once_in_the_module(self) -> None:
        """The DoD's own line, kept honest as the module grows past _deps.py."""
        module = Path(__file__).resolve().parents[2] / "app" / "api" / "resource_requests"
        offenders = [
            path.name
            for path in sorted(module.glob("*.py"))
            if path.name != "_deps.py" and APP_KEY in path.read_text()
        ]
        assert offenders == [], f"app key duplicated outside _deps.py: {offenders}"


class TestTheGuard:
    async def test_a_granted_account_reaches_a_guarded_route(
        self, db_session, client, rrf_app
    ) -> None:
        user = await make_user(db_session, email="mesa@rrf.test")
        await grant(db_session, user, rrf_app, "mesa")

        res = await client.get(PROBE, headers=await auth_header(db_session, user))

        assert res.status_code == 200
        assert res.json() == {"email": "mesa@rrf.test"}

    async def test_an_account_with_no_role_is_refused_with_403(
        self, db_session, client, rrf_app
    ) -> None:
        """The message matters as much as the status — it is what tells a person what to do."""
        user = await make_user(db_session, email="norole@rrf.test")

        res = await client.get(PROBE, headers=await auth_header(db_session, user))

        assert res.status_code == 403
        assert APP_KEY in res.json()["detail"]
        assert "contact support" in res.json()["detail"].lower()

    async def test_a_role_from_another_app_does_not_carry_over(
        self, db_session, client, rrf_app
    ) -> None:
        """Access is per application; holding `mesa` somewhere else is not holding it here."""
        other = await make_app(db_session, app_key="some-other-app", name="Other")
        user = await make_user(db_session, email="elsewhere@rrf.test")
        await grant_app_role(db_session, user, other, role_key="mesa")

        res = await client.get(PROBE, headers=await auth_header(db_session, user))

        assert res.status_code == 403

    @pytest.mark.parametrize("role_key", ["equipe", "gestor"])
    async def test_the_wrong_role_is_refused_by_the_role_alias(
        self, db_session, client, rrf_app, role_key
    ) -> None:
        """App access and role are different gates.

        Passing the first is not passing the second — which is the distinction BE-03
        builds its capability checks on.
        """
        user = await make_user(db_session, email=f"{role_key}@rrf.test")
        await grant(db_session, user, rrf_app, role_key)

        headers = await auth_header(db_session, user)

        assert (await client.get(PROBE, headers=headers)).status_code == 200
        refused = await client.get(MESA_PROBE, headers=headers)
        assert refused.status_code == 403
        assert "mesa" in refused.json()["detail"]

    async def test_a_platform_admin_passes_without_a_grant(
        self, db_session, client, rrf_app
    ) -> None:
        user = await make_user(db_session, email="admin@rrf.test", is_platform_admin=True)

        res = await client.get(PROBE, headers=await auth_header(db_session, user))

        assert res.status_code == 200

    async def test_an_anonymous_call_is_401_not_403(self, client, rrf_app) -> None:
        assert (await client.get(PROBE)).status_code == 401


class TestMyRoles:
    async def test_my_roles_reports_the_granted_role_for_this_app(
        self, db_session, client, rrf_app
    ) -> None:
        """The call FE-24 makes to hydrate a session."""
        user = await make_user(db_session, email="hydrate@rrf.test")
        await grant(db_session, user, rrf_app, "gestor")

        res = await client.get(
            f"/api/auth/my-roles?app_key={APP_KEY}",
            headers=await auth_header(db_session, user),
        )

        assert res.status_code == 200
        assert [(r["app_key"], r["role_key"]) for r in res.json()] == [(APP_KEY, "gestor")]

    async def test_my_roles_is_empty_for_an_account_with_no_grant(
        self, db_session, client, rrf_app
    ) -> None:
        user = await make_user(db_session, email="empty@rrf.test")

        res = await client.get(
            f"/api/auth/my-roles?app_key={APP_KEY}",
            headers=await auth_header(db_session, user),
        )

        assert res.status_code == 200
        assert res.json() == []


class TestTheSeededRolesExist:
    async def test_all_three_roles_are_grantable(self, db_session, rrf_app) -> None:
        result = await db_session.execute(select(Role.role_key).where(Role.app_id == rrf_app.id))
        assert sorted(result.scalars().all()) == sorted(FRONTEND_ROLE_IDS)
