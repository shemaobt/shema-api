"""The capability model: the table is the frontend's, and the guard obeys it.

Two things are under test and they fail for different reasons. The **mirror** fails when
this repository's map and the vendored emission disagree — that is drift between the two
stacks, and it is what the DoD means by *synced against FE-22's contract in CI*. The
**sweep** fails when the guard admits or refuses somebody the map does not say to, which
is a defect in the wiring rather than in the table.

Neither is a substitute for the other: a map that mirrors a wrong emission passes the
first, and a guard that ignores a correct map passes neither but only the second says so
in a sentence a reader can act on.

⚠️ **No negative test here may use a platform admin.** ``require_app_access`` returns
early on ``is_platform_admin`` and ``require_capability`` does the same beside it, so an
admin is admitted by every probe and a refusal test written with one would pass while
proving nothing.
"""

from __future__ import annotations

import pytest

from app.api.resource_requests._deps import APP_KEY
from app.services.resource_request import (
    CAPABILITIES,
    CAPABILITY_ROLES,
    ROLE_CAPABILITIES,
    ROLES,
    holds_capability,
)
from scripts.seed_apps_roles import APP_ROLES_OVERRIDE
from tests.baker import make_app, make_role, make_user, make_user_app_role
from tests.test_resource_requests.conftest import (
    CAP_PROBES,
    EMISSION,
    auth_header,
    grant,
)


def test_the_emission_carries_the_frontend_commit_it_came_from() -> None:
    """A copy older than the table is then a visible fact in review, not an invisible one.

    Two ways the emitter can hand over a provenance that does not stand up, and both are
    refused here rather than vendored. It writes ``null`` when ``git`` is unavailable, and
    it suffixes ``-dirty`` when the tree had uncommitted changes — which names a commit
    whose ``capabilities.ts`` is *not* what was emitted. A wrong provenance is worse than
    none, because it is what a reviewer on this side trusts to tell them the copy is
    current.
    """
    origem = EMISSION["emitted_from"]

    assert isinstance(origem, str), "emitted null — re-emit where git can run"
    assert not origem.endswith("-dirty"), (
        f"emitted from a dirty tree ({origem}): commit the frontend change first, "
        "then re-emit, or the field names a commit that does not contain it"
    )
    assert len(origem) == 40, f"not a full commit sha: {origem!r}"


def test_the_capability_list_is_the_emissions_list_in_its_order() -> None:
    assert list(CAPABILITIES) == EMISSION["capabilities"]


def test_the_emission_is_whole() -> None:
    """Screen plus control is every capability — the same assertion the frontend makes.

    It is what catches a truncated or half-copied vendoring, which the per-role comparison
    below would not: a file missing its last role reads as a role that lost every
    capability, and this says the shorter thing first.
    """
    assert sorted(EMISSION["screenCapabilities"] + EMISSION["controlCapabilities"]) == sorted(
        EMISSION["capabilities"]
    )


def test_the_map_is_the_emission_role_by_role() -> None:
    """The mirror, in the direction that catches a cell this repository invented."""
    emitted = {role["id"]: sorted(role["can"]) for role in EMISSION["roles"]}
    written = {role: sorted(held) for role, held in ROLE_CAPABILITIES.items()}

    assert written == emitted


def test_the_map_is_the_emission_capability_by_capability() -> None:
    """The same fact read the other way, which is the direction a guard asks in.

    Not redundant with the test above: ``CAPABILITY_ROLES`` is derived, and a derivation
    that silently dropped a capability would leave the role table intact.
    """
    emitted = {
        capability: sorted(role["id"] for role in EMISSION["roles"] if capability in role["can"])
        for capability in EMISSION["capabilities"]
    }
    derived = {capability: sorted(roles) for capability, roles in CAPABILITY_ROLES.items()}

    assert derived == emitted


def test_the_roles_are_the_ones_this_app_seeds() -> None:
    """The map and the role rows have to name the same three, or a cell reaches nobody."""
    assert sorted(ROLES) == sorted(APP_ROLES_OVERRIDE[APP_KEY])
    assert sorted(ROLE_CAPABILITIES) == sorted(ROLES)


def test_every_capability_has_a_probe() -> None:
    """So the sweep below cannot quietly stop covering one."""
    assert sorted(CAP_PROBES) == sorted(CAPABILITIES)


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("capability", CAPABILITIES)
async def test_the_guard_answers_the_table(
    db_session, client, rrf_app, role: str, capability: str
) -> None:
    """The whole table, asserted end to end through HTTP — 21 cells, one per case.

    The map is read here rather than restated, so this proves the guard obeys whatever the
    table says; the mirror above is what proves the table is the right one.
    """
    user = await make_user(db_session, email=f"{role}-{capability}@rrf.test")
    await grant(db_session, user, rrf_app, role)

    res = await client.get(CAP_PROBES[capability], headers=await auth_header(db_session, user))

    expected = 200 if capability in ROLE_CAPABILITIES[role] else 403
    assert res.status_code == expected, (
        f"{role} · {capability}: got {res.status_code}, table says {expected}"
    )


async def test_a_team_token_reaches_no_evaluation_and_no_fund(db_session, client, rrf_app) -> None:
    """The DoD's own line. The team holds ``edit_requests`` and nothing else.

    Named separately from the sweep because it is the guarantee somebody will come back to
    read: a team account is the one that reaches the product from outside the mesa, and
    what it must not reach is the scoring and the money.
    """
    user = await make_user(db_session, email="equipe@rrf.test")
    await grant(db_session, user, rrf_app, "equipe")
    headers = await auth_header(db_session, user)

    assert (await client.get(CAP_PROBES["edit_requests"], headers=headers)).status_code == 200

    for capability in (
        "view_evaluation",
        "edit_evaluation",
        "manage_funds",
        "move_board",
        "assign_fund",
        "allocate_funds",
    ):
        res = await client.get(CAP_PROBES[capability], headers=headers)
        assert res.status_code == 403, f"equipe reached {capability}"
        assert capability in res.json()["detail"]


async def test_the_gestor_moves_the_board_and_does_not_score(db_session, client, rrf_app) -> None:
    """GATE-02 D3 (OBT-448, 27/aug/2026), both halves, in one place.

    *"Tem acesso a quase tudo em relação aos projetos, só não aprova."* The pre-gate
    reading had ``move_board`` as the mesa's alone; the client moved it. ``edit_evaluation``
    stayed denied, and stayed by the client's answer rather than by our default — which is
    why flipping either of these is a change to a recorded decision and not a tweak.
    """
    user = await make_user(db_session, email="gestor@rrf.test")
    await grant(db_session, user, rrf_app, "gestor")
    headers = await auth_header(db_session, user)

    assert (await client.get(CAP_PROBES["move_board"], headers=headers)).status_code == 200
    assert (await client.get(CAP_PROBES["edit_evaluation"], headers=headers)).status_code == 403


async def test_the_mesa_assigns_the_fund_and_does_not_allocate(db_session, client, rrf_app) -> None:
    """GATE-01 D4 and D6 (OBT-447, 26/aug/2026), which pull in opposite directions.

    D4 asked directly who chooses the fund a request draws from and the answer was *a
    mesa*; D6 offered *"só o Gestor, ou qualquer membro da mesa"* for entering the
    allocated value and the client chose the Gestor. ``allocate_funds`` is therefore the
    first capability the mesa does not hold, and that asymmetry is the answer, not an
    oversight to tidy up.
    """
    user = await make_user(db_session, email="mesa-funds@rrf.test")
    await grant(db_session, user, rrf_app, "mesa")
    headers = await auth_header(db_session, user)

    assert (await client.get(CAP_PROBES["assign_fund"], headers=headers)).status_code == 200
    assert (await client.get(CAP_PROBES["allocate_funds"], headers=headers)).status_code == 403


async def test_manage_funds_is_held_by_the_mesa_and_the_gestor_alike(
    db_session, client, rrf_app
) -> None:
    """The Painel's entry gate, and the cell most likely to be narrowed by mistake.

    Reading ``manage_funds`` as *the money capability* and giving it to the Gestor alone
    would remove the Painel from the mesa entirely. The two fund capabilities above are
    what money is; this one is a door.
    """
    for role in ("mesa", "gestor"):
        user = await make_user(db_session, email=f"{role}-painel@rrf.test")
        await grant(db_session, user, rrf_app, role)

        res = await client.get(
            CAP_PROBES["manage_funds"], headers=await auth_header(db_session, user)
        )

        assert res.status_code == 200, f"{role} lost the Painel"


async def test_an_account_with_no_role_is_refused_by_the_app_gate(
    db_session, client, rrf_app
) -> None:
    """The capability chain hangs behind ``CurrentUser``, so the outer refusal comes first.

    It matters which one answers: the app gate's message tells somebody how to get access,
    and the capability's tells them they are in the wrong seat. An outsider should get the
    first.
    """
    user = await make_user(db_session, email="nobody@rrf.test")

    res = await client.get(CAP_PROBES["edit_requests"], headers=await auth_header(db_session, user))

    assert res.status_code == 403
    assert APP_KEY in res.json()["detail"]


async def test_a_platform_admin_passes_every_capability_without_a_grant(
    db_session, client, rrf_app
) -> None:
    """The installation's standing rule, stated here so a negative test is never written
    with an admin account by accident.

    Refusing them would make this module stricter than the role guard beside it in the same
    file, and buy nothing: a platform admin can grant themselves ``mesa`` in one call.
    """
    user = await make_user(db_session, email="admin@caps.test", is_platform_admin=True)
    headers = await auth_header(db_session, user)

    for capability in CAPABILITIES:
        res = await client.get(CAP_PROBES[capability], headers=headers)
        assert res.status_code == 200, f"admin refused {capability}"


async def test_the_capability_query_reads_the_database_every_time(db_session, rrf_app) -> None:
    """A grant is visible to ``holds_capability`` immediately, with no cache to invalidate.

    ``require_app_access`` memoises for ``AUTH_CACHE_TTL_SECONDS`` and this deliberately
    does not, which is the difference between *may this account use the app* — asked on
    every request, worth caching — and *may it do this one thing*, asked on the writes that
    matter. Called at the service level on purpose: through HTTP the outer gate's cache
    would be what the assertion measured.
    """
    user = await make_user(db_session, email="fresh@rrf.test")

    assert await holds_capability(db_session, user.id, APP_KEY, "move_board") is False

    await grant(db_session, user, rrf_app, "mesa")

    assert await holds_capability(db_session, user.id, APP_KEY, "move_board") is True


async def test_a_role_in_another_app_carries_no_capability_here(db_session, rrf_app) -> None:
    """``list_roles`` is asked for this app key, so a ``mesa`` elsewhere is nobody here."""
    other = await make_app(db_session, app_key="some-other-app", name="Other")
    other_role = await make_role(db_session, other.id, role_key="mesa", label="Mesa")
    user = await make_user(db_session, email="elsewhere@rrf.test")
    await make_user_app_role(db_session, user.id, other.id, other_role.id)

    assert await holds_capability(db_session, user.id, APP_KEY, "edit_evaluation") is False


async def test_an_unknown_capability_raises_instead_of_refusing(db_session) -> None:
    """A typo in a guard would otherwise refuse every user of that route, forever, and read
    in production as a permission decision rather than as the mistake it is.
    """
    user = await make_user(db_session, email="typo@rrf.test")

    with pytest.raises(ValueError, match="Unknown capability"):
        await holds_capability(db_session, user.id, APP_KEY, "move_boards")
