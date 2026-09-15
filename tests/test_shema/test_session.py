"""``GET /api/shema/session`` — the shape FE-44 §9.13 froze, and the name rule BE-03 decided.

The endpoint exists because ``GET /api/auth/my-roles`` cannot answer it: the platform's
grant has no region. What it adds over the platform's session is the region and the org
chart's name, and each of the three fields is asserted here against the place that owns it.
"""

from __future__ import annotations

import pytest

from app.api.shema._deps import APP_KEY
from app.db.models.shema_enums import ShemaRegionKey, ShemaRoleKey
from app.db.models.shema_org_chart import ShemaRegionTeam
from app.models.shema_session import ShemaSession
from app.services.shema import get_session, set_region_scope
from tests.baker import make_user
from tests.test_shema.conftest import SESSION, auth_header, grant, make_scoped_user

AFRICA = ShemaRegionKey.AFRICA
ASIA = ShemaRegionKey.ASIA


async def seat(db_session, region: ShemaRegionKey, role: ShemaRoleKey, holder: str) -> None:
    """Fill one of the twenty-one org-chart seats.

    All twenty-one ship unassigned on purpose — the prototype's names were real people
    hardcoded in a file — so a test that wants a name has to put one there, which is the
    right amount of friction.
    """
    db_session.add(ShemaRegionTeam(region_key=region, role=role, holder_name=holder))
    await db_session.commit()


# --- the wire shape ------------------------------------------------------------------


async def test_the_response_carries_the_three_frozen_keys(db_session, client, shema_app):
    """``{role, regionScope, name}``, camelCase, exactly as the console reads it.

    The ``regionScope`` spelling is asserted on the JSON and not on the Python attribute,
    because the alias is the only thing standing between the house's snake_case and a
    contract the frontend already ships against.
    """
    user = await make_scoped_user(
        db_session, shema_app, email="shape@shema.test", role_key="coordinator", regions=[AFRICA]
    )

    res = await client.get(SESSION, headers=await auth_header(db_session, user))

    assert res.status_code == 200
    assert sorted(res.json()) == ["name", "regionScope", "role"]
    assert res.json()["role"] == "coordinator"
    assert res.json()["regionScope"] == ["africa"]


async def test_a_global_scope_is_null_and_not_an_empty_list(db_session, client, shema_app):
    """``null`` means global and ``[]`` means an account with a regional role and no region
    granted. They are opposite answers and the transport spells them differently, which is
    the whole reason the field is nullable rather than always a list."""
    user = await make_scoped_user(
        db_session, shema_app, email="null@shema.test", role_key="globalStrategist"
    )

    res = await client.get(SESSION, headers=await auth_header(db_session, user))

    assert res.json()["regionScope"] is None


async def test_an_account_with_a_role_and_no_region_answers_an_empty_list(
    db_session, client, shema_app
):
    """The other half of the pair above — the console shows nothing, which is correct."""
    user = await make_scoped_user(
        db_session, shema_app, email="emptylist@shema.test", role_key="obtLab", regions=[]
    )

    res = await client.get(SESSION, headers=await auth_header(db_session, user))

    assert res.json()["regionScope"] == []


async def test_the_region_list_is_sorted(db_session, client, shema_app):
    """The frontend renders it, and an unordered list would reshuffle between requests for
    no reason a reader could explain."""
    user = await make_scoped_user(
        db_session,
        shema_app,
        email="sorted@shema.test",
        role_key="coordinator",
        regions=[ShemaRegionKey.OCEANIA, AFRICA, ASIA],
    )

    res = await client.get(SESSION, headers=await auth_header(db_session, user))

    assert res.json()["regionScope"] == ["africa", "asia", "oceania"]


# --- the role ------------------------------------------------------------------------


async def test_one_role_is_answered_for_an_account_holding_two(db_session, shema_app):
    """The contract owes one ``SessionRole`` and an account legitimately holds more than one
    grant. Widest first, off the one tuple that also seeds the app — so the guard and the
    session cannot disagree about what the four keys are."""
    user = await make_scoped_user(
        db_session, shema_app, email="multi@shema.test", role_key="resourceCircle", regions=[ASIA]
    )
    await grant(db_session, user, shema_app, "coordinator")

    assert (await get_session(db_session, user, APP_KEY)).role == "coordinator"


async def test_the_global_strategist_wins_over_a_regional_role(db_session, shema_app):
    user = await make_scoped_user(
        db_session, shema_app, email="widest@shema.test", role_key="coordinator", regions=[ASIA]
    )
    await grant(db_session, user, shema_app, "globalStrategist")

    assert (await get_session(db_session, user, APP_KEY)).role == "globalStrategist"


async def test_the_endpoint_needs_no_role_alias_of_its_own(db_session, client, shema_app):
    """Every one of the four personas reaches it. A role alias here would refuse three of
    the four the endpoint exists to describe."""
    for role in ("globalStrategist", "coordinator", "obtLab", "resourceCircle"):
        user = await make_scoped_user(
            db_session, shema_app, email=f"{role.lower()}@persona.test", role_key=role
        )
        res = await client.get(SESSION, headers=await auth_header(db_session, user))
        assert res.status_code == 200, role
        assert res.json()["role"] == role


# --- the name ------------------------------------------------------------------------


async def test_the_name_comes_from_the_org_chart_seat(db_session, shema_app):
    """FE-44 §5.3's fourth consumer: renaming a role-holder renames who the session says
    you are. The account's own ``display_name`` is deliberately different here, so a
    passing test cannot be reading the wrong field."""
    await seat(db_session, AFRICA, ShemaRoleKey.COORDINATOR, "Ana Coordenadora")
    user = await make_scoped_user(
        db_session, shema_app, email="seat@shema.test", role_key="coordinator", regions=[AFRICA]
    )
    user.display_name = "Some Account Name"
    await db_session.commit()

    assert (await get_session(db_session, user, APP_KEY)).name == "Ana Coordenadora"


async def test_renaming_the_seat_renames_the_session(db_session, shema_app):
    """The property the chart is the single source for, asserted as a change rather than
    as a value — a stored copy would pass the test above and fail this one."""
    await seat(db_session, ASIA, ShemaRoleKey.OBT_LAB, "Before")
    user = await make_scoped_user(
        db_session, shema_app, email="rename@shema.test", role_key="obtLab", regions=[ASIA]
    )
    assert (await get_session(db_session, user, APP_KEY)).name == "Before"

    row = await db_session.get(ShemaRegionTeam, (ASIA, ShemaRoleKey.OBT_LAB))
    row.holder_name = "After"
    await db_session.commit()

    assert (await get_session(db_session, user, APP_KEY)).name == "After"


async def test_the_global_strategist_falls_back_to_the_accounts_display_name(db_session, shema_app):
    """**Open question 4 of ``docs/shema.md`` §10, answered.**

    ``globalStrategist`` has no seat — the chart's three roles are per region — so there is
    no fact being duplicated and no rename to follow, and the *never duplicate a
    role-holder's name* rule does not reach it. ``null`` was the alternative and would
    guarantee that the console's ``GLOBAL_STRATEGIST_NAME`` hardcode stays, which is what
    this endpoint exists to retire.
    """
    user = await make_user(db_session, email="strategist@name.test", display_name="Karina")
    await grant(db_session, user, shema_app, "globalStrategist")

    assert (await get_session(db_session, user, APP_KEY)).name == "Karina"


async def test_an_unassigned_seat_falls_back_to_the_display_name(db_session, shema_app):
    """Not the edge case but the normal one: all twenty-one seats ship unassigned, so on
    day one every regional account takes this path."""
    user = await make_user(db_session, email="noseat@shema.test", display_name="Sem Assento")
    await grant(db_session, user, shema_app, "coordinator")
    await set_region_scope(db_session, user.id, [AFRICA])

    assert (await get_session(db_session, user, APP_KEY)).name == "Sem Assento"


async def test_a_two_region_scope_falls_back_rather_than_picking_a_seat(db_session, shema_app):
    """There is no single seat to name, and picking one of two silently would make the
    session say something the chart does not."""
    await seat(db_session, AFRICA, ShemaRoleKey.COORDINATOR, "Africa Person")
    await seat(db_session, ASIA, ShemaRoleKey.COORDINATOR, "Asia Person")
    user = await make_user(db_session, email="twoseats@shema.test", display_name="Own Name")
    await grant(db_session, user, shema_app, "coordinator")
    await set_region_scope(db_session, user.id, [AFRICA, ASIA])

    assert (await get_session(db_session, user, APP_KEY)).name == "Own Name"


async def test_the_seat_of_another_role_in_the_same_region_is_not_read(db_session, shema_app):
    """A seat is ``(region, role)``. Reading the region alone would hand an ``obtLab``
    account the coordinator's name."""
    await seat(db_session, AFRICA, ShemaRoleKey.COORDINATOR, "The Coordinator")
    user = await make_user(db_session, email="otherrole@shema.test", display_name="Lab Person")
    await grant(db_session, user, shema_app, "obtLab")
    await set_region_scope(db_session, user.id, [AFRICA])

    assert (await get_session(db_session, user, APP_KEY)).name == "Lab Person"


async def test_the_name_is_null_when_there_is_no_seat_and_no_display_name(
    db_session, client, shema_app
):
    """``string | null`` is the contract, and ``null`` is what is left when nobody has
    written a name anywhere. An empty string would be a third state the console has to
    special-case."""
    user = await make_user(db_session, email="nameless@shema.test", display_name=None)
    await grant(db_session, user, shema_app, "resourceCircle")
    await set_region_scope(db_session, user.id, [ASIA])

    res = await client.get(SESSION, headers=await auth_header(db_session, user))

    assert res.json()["name"] is None


# --- the guard -----------------------------------------------------------------------


async def test_an_account_with_no_shema_role_is_refused(db_session, client, shema_app):
    """``require_app_access`` refuses before the handler runs, so the endpoint never has to
    answer ``role: null`` on the wire."""
    user = await make_user(db_session, email="outsider@shema.test")

    res = await client.get(SESSION, headers=await auth_header(db_session, user))

    assert res.status_code == 403


async def test_the_service_answers_a_null_role_where_the_guard_has_not_run(db_session, shema_app):
    """Unreachable through the endpoint and reachable from anywhere else, which is why the
    type carries it: answering a role nobody granted is the wrong half to guess on."""
    user = await make_user(db_session, email="ungranted@shema.test")

    assert (await get_session(db_session, user, APP_KEY)).role is None


# --- the model -----------------------------------------------------------------------


def test_the_model_serialises_by_alias_and_accepts_the_python_name() -> None:
    """The mechanism itself, asserted once so a ``populate_by_name`` removed later fails
    here rather than in every construction site."""
    session = ShemaSession(role="coordinator", region_scope=["africa"], name=None)

    assert session.model_dump(by_alias=True)["regionScope"] == ["africa"]
    assert "region_scope" not in session.model_dump(by_alias=True)


def test_the_model_does_not_restate_the_role_vocabulary() -> None:
    """``app/models/`` may not import ``app/services/`` — the inversion that closed an
    import cycle once — so the four keys are not re-typed here as a ``Literal``. This
    asserts the absence, because a helpful ``Literal`` added later would be a second copy
    of a vocabulary whose whole value is that there is one.

    Read off the syntax tree: the module's prose **does** name the four keys, and naming
    them in a sentence a reader follows to their owner is the opposite of copying them into
    a type two files can disagree about.
    """
    import ast
    from pathlib import Path

    from app.services.shema._scope import ROLE_KEYS

    source = Path(__file__).resolve().parents[2] / "app" / "models" / "shema_session.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))

    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert "Literal" not in names

    docstrings = {ast.get_docstring(node) for node in ast.walk(tree) if hasattr(node, "body")}
    literals = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node.value not in docstrings
    }
    assert not literals & set(ROLE_KEYS), f"the role vocabulary is restated here: {literals}"


@pytest.mark.parametrize("field", ["role", "region_scope", "name"])
def test_every_field_is_nullable(field: str) -> None:
    """All three are ``| null`` in the contract, each for its own reason, and a required
    one would 500 rather than answer."""
    assert ShemaSession().model_dump()[field] is None
