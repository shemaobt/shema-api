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
from app.services.authorization import list_roles
from app.services.resource_request import (
    ADMIN_CAPABILITIES,
    CAPABILITIES,
    CAPABILITY_ROLES,
    RETIRED_ROLES,
    ROLE_CAPABILITIES,
    ROLES,
    holds_capability,
)
from app.services.shema._scope import ADMIN_ROLE
from scripts.seed_apps_roles import seeded_roles
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


def _emitted_rows() -> dict[str, list[str]]:
    return {role["id"]: sorted(role["can"]) for role in EMISSION["roles"]}


def test_the_map_is_the_emission_role_by_role() -> None:
    """The mirror, in the direction that catches a cell this repository invented.

    The emission carries four rows and the map writes three: the Admin's is derived here
    (``ADMIN_CAPABILITIES``, OBT-568) and compared to the emitted row directly, so an emission
    that dropped the row or moved it off the Gestor's set fails rather than passing quietly.
    """
    emitted = _emitted_rows()
    written = {role: sorted(held) for role, held in ROLE_CAPABILITIES.items()}

    assert ADMIN_ROLE in emitted, "the emission lost the Admin's row"
    assert emitted == {**written, ADMIN_ROLE: sorted(ADMIN_CAPABILITIES)}


def test_the_map_is_the_emission_capability_by_capability() -> None:
    """The same fact read the other way, which is the direction a guard asks in.

    Not redundant with the test above: ``CAPABILITY_ROLES`` is derived — over the frontend's
    rows and the Admin's — and a derivation that silently dropped a capability or a carrier
    would leave the role table intact.
    """
    emitted = {
        capability: sorted(role["id"] for role in EMISSION["roles"] if capability in role["can"])
        for capability in EMISSION["capabilities"]
    }
    derived = {capability: sorted(roles) for capability, roles in CAPABILITY_ROLES.items()}

    assert derived == emitted


def test_the_admins_row_is_the_gestors() -> None:
    """OBT-568 (Daniel, 6/oct/2026): *"o admin deve ter o mesmo nível de permissão que o
    gestor no formulário"*. Identity and not equality: a copy of the set would let the two rows
    drift apart on the day one of them moved, and the decision is *the same level*."""
    assert ADMIN_CAPABILITIES is ROLE_CAPABILITIES["gestor"]
    assert ADMIN_ROLE not in ROLE_CAPABILITIES, "the mirror of the emission stays the frontend's"
    assert "edit_evaluation" not in ADMIN_CAPABILITIES
    assert "assign_fund" not in ADMIN_CAPABILITIES


def test_the_roles_are_the_ones_this_app_seeds() -> None:
    """The map and the role rows have to name the same roles, or a cell reaches nobody.

    The seed also carries the retired ones (FE-49, OBT-517): a row existing installations
    have, holding no capability here.
    """
    seeded = [key for key, _ in seeded_roles(APP_KEY)]

    assert sorted((*ROLES, *RETIRED_ROLES, ADMIN_ROLE)) == sorted(seeded)
    assert not set(ROLES) & set(RETIRED_ROLES)
    assert sorted(ROLE_CAPABILITIES) == sorted(ROLES)


def test_every_capability_has_a_probe() -> None:
    """So the sweep below cannot quietly stop covering one."""
    assert sorted(CAP_PROBES) == sorted(CAPABILITIES)


@pytest.mark.parametrize("role", ROLES)
@pytest.mark.parametrize("capability", CAPABILITIES)
async def test_the_guard_answers_the_table(
    db_session, client, rrf_app, role: str, capability: str
) -> None:
    """The whole table, asserted end to end through HTTP — 36 cells, one per case.

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


@pytest.mark.parametrize("capability", CAPABILITIES)
async def test_the_guard_answers_the_gestors_row_for_the_admin(
    db_session, client, rrf_app, capability: str
) -> None:
    """The Admin's row through HTTP, one cell per case — the same sweep as the table's,
    against ``ADMIN_CAPABILITIES`` instead of a row of the frontend's (OBT-568).

    The account holds ``admin`` **alone** and is not a platform admin, so a 403 here is the
    guard refusing and not a short-circuit admitting; the two negative cells are
    ``edit_evaluation`` and ``assign_fund``, which the Gestor does not hold either.
    """
    user = await make_user(db_session, email=f"admin-{capability}@rrf.test")
    await grant(db_session, user, rrf_app, ADMIN_ROLE)

    res = await client.get(CAP_PROBES[capability], headers=await auth_header(db_session, user))

    expected = 200 if capability in ADMIN_CAPABILITIES else 403
    assert res.status_code == expected, (
        f"admin · {capability}: got {res.status_code}, the Gestor's row says {expected}"
    )


async def test_the_admin_and_the_gestor_answer_alike_on_every_cell(
    db_session, client, rrf_app
) -> None:
    """The DoD's own sentence — *exatamente as capacidades do Gestor* — measured end to end
    rather than read off the table: two accounts, one grant each, the same answer on all eight."""
    admin = await make_user(db_session, email="admin-alike@rrf.test")
    gestor = await make_user(db_session, email="gestor-alike@rrf.test")
    await grant(db_session, admin, rrf_app, ADMIN_ROLE)
    await grant(db_session, gestor, rrf_app, "gestor")
    admin_headers = await auth_header(db_session, admin)
    gestor_headers = await auth_header(db_session, gestor)

    for capability in CAPABILITIES:
        as_admin = (await client.get(CAP_PROBES[capability], headers=admin_headers)).status_code
        as_gestor = (await client.get(CAP_PROBES[capability], headers=gestor_headers)).status_code

        assert as_admin == as_gestor, f"{capability}: admin {as_admin}, gestor {as_gestor}"


async def test_an_admin_who_also_sits_on_the_mesa_answers_by_the_union(
    db_session, client, rrf_app
) -> None:
    """``admin`` + ``mesa`` is the pair the Admin's row makes possible, and the one that tells
    the union apart: the mesa brings ``edit_evaluation`` and ``assign_fund``, the Admin brings
    ``allocate_funds`` and ``administer_funds``, and only an answer over both says 200 to all.

    What it pins is the arithmetic, not the policy. This union is what ``mesa`` + ``gestor``
    would answer — the pair our rule of 28/aug/2026 keeps off one account, applied where a
    grant is written — and with the Admin's row it reassembles through the Admin. Whether an
    Admin may also sit on the mesa is the user's decision, raised with OBT-568's PR; the guard
    has to answer correctly whether or not that pair is ever granted.
    """
    user = await make_user(db_session, email="admin-mesa@rrf.test")
    await grant(db_session, user, rrf_app, ADMIN_ROLE)
    await grant(db_session, user, rrf_app, "mesa")
    headers = await auth_header(db_session, user)

    union = ADMIN_CAPABILITIES | ROLE_CAPABILITIES["mesa"]
    assert union == set(CAPABILITIES), "the pair covers the table, or the loop proves less"
    for capability in CAPABILITIES:
        res = await client.get(CAP_PROBES[capability], headers=headers)

        assert res.status_code == 200, f"admin+mesa lost {capability}"


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

    # Derivada da tabela, e não escrita à mão: a lista tinha oito nomes quando havia
    # nove capacidades, então a décima (``grant_access``, 8/set/2026) entrou sem ninguém
    # afirmar que a equipe não a alcança — que é exatamente a asserção deste teste. Agora
    # a décima primeira entra sozinha, e um dia em que ``equipe`` ganhe uma segunda
    # capacidade este laço a exclui sem mentir sobre as outras.
    for capability in CAPABILITIES:
        if capability in ROLE_CAPABILITIES["equipe"]:
            continue
        res = await client.get(CAP_PROBES[capability], headers=headers)
        assert res.status_code == 403, f"equipe reached {capability}"
        assert capability in res.json()["detail"]


async def test_a_retired_lider_grant_opens_nothing(db_session, client, rrf_app) -> None:
    """The Líder de Base's role row survives the retirement (FE-49, OBT-517) and holds nothing.

    ``20260930_rr12`` revoked every grant on it, and the map no longer names it — so a grant
    that somehow survived answers 403 on every capability, which is the whole point of
    retiring a role rather than leaving it in the table with a column nobody reads.
    """
    user = await make_user(db_session, email="lider@rrf.test")
    await grant(db_session, user, rrf_app, "lider")
    headers = await auth_header(db_session, user)

    for capability in CAPABILITIES:
        res = await client.get(CAP_PROBES[capability], headers=headers)

        assert res.status_code == 403, f"lider · {capability}: got {res.status_code}"


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


@pytest.mark.parametrize("privileged", ("mesa", "gestor"))
async def test_an_account_with_two_roles_answers_by_their_union(
    db_session, client, rrf_app, privileged: str
) -> None:
    """Two roles on one account is an ordinary shape here, not a curiosity.

    Since BE-19 (OBT-520) the two halves come from different places: ``equipe`` from a live
    membership of a PME project, which is the only way a team account holds it after
    ``20260928_rr08`` revoked the grants, and ``mesa`` or ``gestor`` from a grant. A project
    member who also sits on the mesa is that account, and the grant must add to the
    membership rather than stand in for it.

    Asserted through the whole table against the **union** of the two roles, because that is
    what ``held & CAPABILITY_ROLES[capability]`` computes and the sweep above never exercised
    — its fourteen accounts hold exactly one role each.
    """
    user = await make_user(db_session, email=f"equipe-{privileged}@rrf.test")
    await grant(db_session, user, rrf_app, "equipe")
    await grant(db_session, user, rrf_app, privileged)
    headers = await auth_header(db_session, user)

    assert await list_roles(db_session, user.id, APP_KEY) == [(APP_KEY, privileged)], (
        "equipe is held through the membership, never as a grant"
    )

    union = ROLE_CAPABILITIES["equipe"] | ROLE_CAPABILITIES[privileged]
    for capability in CAPABILITIES:
        res = await client.get(CAP_PROBES[capability], headers=headers)

        expected = 200 if capability in union else 403
        assert res.status_code == expected, (
            f"equipe+{privileged} · {capability}: got {res.status_code}, union says {expected}"
        )


async def test_the_union_answers_where_one_role_alone_would_refuse(
    db_session, client, rrf_app
) -> None:
    """``mesa`` and ``gestor`` on one account — the only pair that tells a union apart.

    ``equipe``'s one capability is held by both of the others, so the test above stays green
    even if the guard read a single role and dropped the rest. This pair does not: reading
    only the first leaves ``allocate_funds`` refused, reading only the last leaves
    ``edit_evaluation`` and ``assign_fund`` refused, and the pair's whole union answers 200
    **only** for an answer taken over it. The union is not everything either: ``grant_access``
    and the fund verbs split between the two, which is what the per-capability loop reads.

    The exclusivity that keeps these two off one account is a rule of ours (28/aug/2026) and
    not a sentence of the client's, and it is applied where a grant is written rather than
    here — so this function has to answer correctly whether it exists or not, which is why
    the combination it forbids is the one written here. Should it ever be enforced in the
    schema, this test is where that is discovered, and the discriminating half moves to
    whatever pair the rule then allows.
    """
    user = await make_user(db_session, email="mesa-gestor@rrf.test")
    await grant(db_session, user, rrf_app, "mesa")
    await grant(db_session, user, rrf_app, "gestor")
    headers = await auth_header(db_session, user)

    union = ROLE_CAPABILITIES["mesa"] | ROLE_CAPABILITIES["gestor"]
    for capability in CAPABILITIES:
        res = await client.get(CAP_PROBES[capability], headers=headers)

        expected = 200 if capability in union else 403
        assert res.status_code == expected, f"the union lost {capability}"


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
