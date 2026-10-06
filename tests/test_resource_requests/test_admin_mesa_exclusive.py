"""OBT-568: an account cannot be Admin and mesa, as it cannot be Gestor and mesa.

Daniel's decision of 6/oct/2026, in the issue's comments, after the Admin took the Gestor's
capabilities: an Admin on the mesa would be the mesa + Gestor union under another name. The
rule lives where the mesa/Gestor one already lived — ``resource_request_access/_rules.py`` —
and is exercised here through the one door that grants roles, the PME's surface
(``POST /api/shema/access/grants``), in both directions, plus the service call that invite
acceptance makes. ``admin`` + ``gestor`` stays allowed: it is the Admin's own account shape.
"""

from __future__ import annotations

import pytest

from app.api.shema._deps import FORM_APP_KEY
from app.core.exceptions import ConflictError
from app.services.resource_request_access._rules import (
    MUTUALLY_EXCLUSIVE,
    assert_role_compatible,
)
from app.services.shema._scope import ADMIN_ROLE, GESTOR_ROLE, MESA_ROLE
from tests.baker import make_user
from tests.shema_admin_harness import make_account, make_admin, surface_client
from tests.test_resource_requests.conftest import grant

GRANTS = "/api/shema/access/grants"


def _grant(user_id: str, role: str) -> dict[str, str]:
    return {"userId": user_id, "appKey": FORM_APP_KEY, "roleKey": role}


def test_the_rule_is_symmetric_and_names_the_pairs_it_keeps_apart() -> None:
    """A one-way entry would refuse one direction and let the other through."""
    for role, counterparts in MUTUALLY_EXCLUSIVE.items():
        for counterpart in counterparts:
            assert role in MUTUALLY_EXCLUSIVE[counterpart], f"{role} ↔ {counterpart}"

    assert ADMIN_ROLE in MUTUALLY_EXCLUSIVE[MESA_ROLE]
    assert GESTOR_ROLE in MUTUALLY_EXCLUSIVE[MESA_ROLE]
    assert GESTOR_ROLE not in MUTUALLY_EXCLUSIVE[ADMIN_ROLE], "admin + gestor is the Admin's shape"


@pytest.mark.parametrize(("held", "wanted"), [(ADMIN_ROLE, MESA_ROLE), (MESA_ROLE, ADMIN_ROLE)])
async def test_the_pme_refuses_admin_to_a_mesa_and_mesa_to_an_admin(
    db_session, rrf_app, shema_app, held: str, wanted: str
) -> None:
    """Both directions through the grant route: 409, and the account keeps what it had."""
    _admin, headers = await make_admin(db_session, shema_app, rrf_app)
    person = await make_account(db_session, "person@rrf.test", (rrf_app, held))

    async with surface_client(db_session) as client:
        res = await client.post(GRANTS, json=_grant(person.id, wanted), headers=headers)

    assert res.status_code == 409, res.text
    assert "mutually exclusive" in res.json()["detail"]
    assert wanted in res.json()["detail"] and held in res.json()["detail"]


async def test_the_pme_still_grants_gestor_to_an_admin(db_session, rrf_app, shema_app) -> None:
    """The pair the decision leaves alone — and the one that proves the rule is not
    *admin excludes every seat*."""
    _admin, headers = await make_admin(db_session, shema_app, rrf_app)
    person = await make_account(db_session, "admin-gestor@rrf.test", (rrf_app, ADMIN_ROLE))

    async with surface_client(db_session) as client:
        res = await client.post(GRANTS, json=_grant(person.id, GESTOR_ROLE), headers=headers)

    assert res.status_code == 200, res.text


@pytest.mark.parametrize(("held", "wanted"), [(ADMIN_ROLE, MESA_ROLE), (MESA_ROLE, ADMIN_ROLE)])
async def test_the_service_rule_refuses_the_pair_where_invite_acceptance_asks_it(
    db_session, rrf_app, held: str, wanted: str
) -> None:
    """``accept_invite`` calls the same function, so an invite to the other seat is refused at
    the click even when it was written before the account took its current role."""
    person = await make_user(db_session, email=f"{held}-then-{wanted}@rrf.test")
    await grant(db_session, person, rrf_app, held)

    with pytest.raises(ConflictError, match="mutually exclusive"):
        await assert_role_compatible(db_session, person.id, rrf_app.id, wanted)


async def test_the_service_rule_is_silent_where_the_app_has_no_mesa(
    db_session, rrf_app, shema_app
) -> None:
    """The ``admin`` grant writes both apps and the check runs per app: under ``shema`` there
    is no ``mesa`` role to collide with, so a mesa member's Admin grant is refused by the
    form's check and not by a false positive on the PME's."""
    person = await make_user(db_session, email="mesa-shema@rrf.test")
    await grant(db_session, person, rrf_app, MESA_ROLE)

    await assert_role_compatible(db_session, person.id, shema_app.id, ADMIN_ROLE)
