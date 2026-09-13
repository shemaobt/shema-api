"""The region axis, and the negative cases the DoD names one by one.

A test that a coordinator sees their own region proves almost nothing — the query would
have returned it with no predicate at all. What is asserted here is the other half: that
the same coordinator **cannot reach another region's project by direct id, cannot page past
their scope, and cannot see it in any aggregate count.**

**No account in this file is a platform admin**, except the one test that is about platform
admins. Both platform guards return early on ``is_platform_admin``, so an admin account
would make every refusal below pass for the wrong reason and keep passing after the
predicate was deleted.

The cross-region answer being asserted is *nothing*: out of scope is absent from the
collection, absent from the counts, and a direct id raises ``NotFoundError`` — never
``AuthorizationError``. ``app/services/shema/_scope.py`` carries the argument, and
``test_a_direct_id_refusal_is_indistinguishable_from_a_missing_row`` is where the sharp end
of it is pinned.
"""

from __future__ import annotations

import ast
import logging
from pathlib import Path

import pytest

from app.api.shema._deps import APP_KEY
from app.core.exceptions import AuthorizationError, NotFoundError
from app.db.models.shema_enums import ShemaRegionKey
from app.services.shema import (
    RegionScope,
    count_projects,
    count_projects_by_region,
    get_project,
    list_projects,
    reaches,
    region_scope,
    set_region_scope,
    visible_projects,
)
from tests.baker import make_user
from tests.test_shema.conftest import SCOPE_PROBE, auth_header, grant, make_scoped_user
from tests.test_shema.conftest import make_shema_project as make_project

AFRICA = ShemaRegionKey.AFRICA
ASIA = ShemaRegionKey.ASIA
EUROPE = ShemaRegionKey.EUROPE


@pytest.fixture()
async def three_regions(db_session):
    """One project in each of three regions, so every negative case has somewhere to fail."""
    await make_project(db_session, project_id="wolof", region_key=AFRICA, language_name="Wolof")
    await make_project(db_session, project_id="hmong", region_key=ASIA, language_name="Hmong")
    await make_project(db_session, project_id="basque", region_key=EUROPE, language_name="Basque")


# --- the scope value itself ----------------------------------------------------------


async def test_a_regional_role_reaches_the_regions_it_was_granted(db_session, shema_app):
    user = await make_scoped_user(
        db_session, shema_app, email="africa@shema.test", role_key="coordinator", regions=[AFRICA]
    )

    scope = await region_scope(db_session, user, APP_KEY)

    assert scope.global_ is False
    assert scope.regions == frozenset({"africa"})


async def test_a_regional_role_with_no_region_reaches_nothing(db_session, shema_app):
    """**The fail-closed floor, and the one reading of ``docs/shema.md`` §6.1 this issue
    narrows on purpose.**

    "No rows means global" names who the empty case serves — the ``globalStrategist``, and
    any account the client wants unscoped — and reading it as *anyone with no rows is
    global* inverts the product's own sentence. It also has a live path to it:
    ``app/services/access_request`` grants a role on approval and grants no region, so every
    approved account would land globally scoped by default.
    """
    user = await make_scoped_user(
        db_session, shema_app, email="unscoped@shema.test", role_key="coordinator", regions=[]
    )

    scope = await region_scope(db_session, user, APP_KEY)

    assert scope.global_ is False
    assert scope.regions == frozenset()


async def test_the_global_strategist_reaches_every_region_with_no_rows(db_session, shema_app):
    """The one role the empty case is for. It has no seat in the org chart for the same
    reason: the chart's three roles are per region and this one is not regional."""
    user = await make_scoped_user(
        db_session, shema_app, email="strategist@shema.test", role_key="globalStrategist"
    )

    scope = await region_scope(db_session, user, APP_KEY)

    assert scope.global_ is True


async def test_a_platform_admin_is_global_without_any_grant(db_session, shema_app):
    """Short-circuits before either query, as they pass every guard in this repository."""
    admin = await make_user(db_session, email="admin@scope.test", is_platform_admin=True)

    scope = await region_scope(db_session, admin, APP_KEY)

    assert scope.global_ is True


async def test_holding_two_roles_keeps_the_narrower_scope(db_session, shema_app):
    """A regional ``coordinator`` who is also ``resourceCircle`` is the ordinary account
    ``docs/shema.md`` §4.2 names, not an exotic one — and holding a second **regional** role
    does not widen the reach, because reach comes from the region table and not the grant."""
    user = await make_scoped_user(
        db_session, shema_app, email="two@shema.test", role_key="coordinator", regions=[AFRICA]
    )
    await grant(db_session, user, shema_app, "resourceCircle")

    scope = await region_scope(db_session, user, APP_KEY)

    assert scope.global_ is False
    assert scope.regions == frozenset({"africa"})


async def test_a_regional_role_plus_global_strategist_is_global(db_session, shema_app):
    """The explicit way to make a scoped account unscoped, which is the point of it being
    explicit — the alternative the module refuses is an account that drifts global by
    having no row."""
    user = await make_scoped_user(
        db_session, shema_app, email="both@shema.test", role_key="coordinator", regions=[AFRICA]
    )
    await grant(db_session, user, shema_app, "globalStrategist")

    assert (await region_scope(db_session, user, APP_KEY)).global_ is True


async def test_the_scope_ignores_a_grant_in_another_application(db_session, shema_app):
    """``list_roles`` is asked for this app key, so ``globalStrategist`` somewhere else — if
    another product ever coins the key — is not ``globalStrategist`` here."""
    from tests.baker import grant_app_role, make_app

    other = await make_app(db_session, app_key="other-product", name="Other")
    user = await make_scoped_user(
        db_session, shema_app, email="crossapp@shema.test", role_key="coordinator", regions=[ASIA]
    )
    await grant_app_role(db_session, user, other, role_key="globalStrategist")

    scope = await region_scope(db_session, user, APP_KEY)

    assert scope.global_ is False
    assert scope.regions == frozenset({"asia"})


# --- the collection ------------------------------------------------------------------


async def test_the_collection_carries_only_the_callers_regions(
    db_session, shema_app, three_regions
):
    user = await make_scoped_user(
        db_session, shema_app, email="listing@shema.test", role_key="coordinator", regions=[AFRICA]
    )
    scope = await region_scope(db_session, user, APP_KEY)

    assert [p.id for p in await list_projects(db_session, scope)] == ["wolof"]


async def test_a_two_region_scope_carries_both_and_nothing_else(
    db_session, shema_app, three_regions
):
    user = await make_scoped_user(
        db_session,
        shema_app,
        email="two-regions@shema.test",
        role_key="coordinator",
        regions=[AFRICA, EUROPE],
    )
    scope = await region_scope(db_session, user, APP_KEY)

    assert sorted(p.id for p in await list_projects(db_session, scope)) == ["basque", "wolof"]


async def test_a_global_caller_carries_the_whole_collection(db_session, shema_app, three_regions):
    user = await make_scoped_user(
        db_session, shema_app, email="global-list@shema.test", role_key="globalStrategist"
    )
    scope = await region_scope(db_session, user, APP_KEY)

    assert len(await list_projects(db_session, scope)) == 3


async def test_an_empty_scope_carries_nothing(db_session, shema_app, three_regions):
    """The floor as a query rather than as a branch: ``within_scope`` answers a literal
    false, so a reader cannot leak by forgetting to check the set was empty first."""
    user = await make_scoped_user(
        db_session, shema_app, email="empty@shema.test", role_key="obtLab", regions=[]
    )
    scope = await region_scope(db_session, user, APP_KEY)

    assert await list_projects(db_session, scope) == []


# --- the negative cases the DoD names ------------------------------------------------


async def test_a_direct_id_does_not_reach_another_region(db_session, shema_app, three_regions):
    """**Negative case 1 — direct-ID access.** The id is real, correctly spelled, and out of
    reach."""
    user = await make_scoped_user(
        db_session, shema_app, email="direct@shema.test", role_key="coordinator", regions=[AFRICA]
    )
    scope = await region_scope(db_session, user, APP_KEY)

    assert (await get_project(db_session, scope, "wolof", user=user)).id == "wolof"

    with pytest.raises(NotFoundError):
        await get_project(db_session, scope, "hmong", user=user)


async def test_a_direct_id_refusal_is_indistinguishable_from_a_missing_row(
    db_session, shema_app, three_regions
):
    """**The visibility decision, pinned where it can be undone by accident.**

    The issue asks what a caller sees of another region's project — nothing, or the
    existence without detail — and the answer is *nothing*. A 403 here would be the
    existence answer delivered by status code: a caller able to tell *this slug is real but
    not yours* from *no such slug* holds an oracle over the whole collection, and a Shemá
    slug names a language and a place.

    So the two refusals must be the same exception with the same message. Asserting the
    message too, because a helpful one added later — *"outside your region"* — re-opens the
    oracle without changing a status code anybody would notice.
    """
    user = await make_scoped_user(
        db_session, shema_app, email="oracle@shema.test", role_key="coordinator", regions=[AFRICA]
    )
    scope = await region_scope(db_session, user, APP_KEY)

    with pytest.raises(NotFoundError) as out_of_scope:
        await get_project(db_session, scope, "hmong", user=user)
    with pytest.raises(NotFoundError) as never_existed:
        await get_project(db_session, scope, "no-such-project-at-all", user=user)

    assert str(out_of_scope.value) == str(never_existed.value)
    assert not isinstance(out_of_scope.value, AuthorizationError)
    for word in ("region", "africa", "asia", "scope", "forbidden"):
        assert word not in str(out_of_scope.value).lower()


async def test_paging_cannot_walk_past_the_scope(db_session, shema_app):
    """**Negative case 2 — pagination.**

    Five in reach and five out, interleaved by the order the window is taken in, so an
    offset that ran over an unscoped select would land on a foreign row rather than on
    nothing. Every window is asked, including the ones past the end.
    """
    for index in range(5):
        await make_project(
            db_session,
            project_id=f"mine-{index}",
            region_key=AFRICA,
            language_name=f"aaa-{index}",
        )
        await make_project(
            db_session,
            project_id=f"theirs-{index}",
            region_key=ASIA,
            language_name=f"aab-{index}",
        )

    user = await make_scoped_user(
        db_session, shema_app, email="paging@shema.test", role_key="coordinator", regions=[AFRICA]
    )
    scope = await region_scope(db_session, user, APP_KEY)

    walked: list[str] = []
    for offset in range(0, 12, 2):
        page = await list_projects(db_session, scope, limit=2, offset=offset)
        walked.extend(project.id for project in page)

    assert walked == [f"mine-{index}" for index in range(5)]
    assert await list_projects(db_session, scope, limit=100) == await list_projects(
        db_session, scope
    )
    assert await list_projects(db_session, scope, offset=5) == []


async def test_an_aggregate_count_does_not_count_another_region(
    db_session, shema_app, three_regions
):
    """**Negative case 3 — aggregate counts.**

    A number does not look like data, which is why a count written for a badge is the one
    nobody thinks to scope. A caller told *3* has learned about two regions they cannot
    open.
    """
    user = await make_scoped_user(
        db_session, shema_app, email="counting@shema.test", role_key="obtLab", regions=[AFRICA]
    )
    scope = await region_scope(db_session, user, APP_KEY)

    assert await count_projects(db_session, scope) == 1
    assert await count_projects(db_session, RegionScope(global_=True, regions=frozenset())) == 3


async def test_the_per_region_breakdown_names_no_region_outside_the_scope(
    db_session, shema_app, three_regions
):
    """A key with a zero beside it answers *there is nothing in Asia* to somebody who may
    not know either way, which is the existence answer arriving through the back door."""
    user = await make_scoped_user(
        db_session, shema_app, email="breakdown@shema.test", role_key="coordinator", regions=[ASIA]
    )
    scope = await region_scope(db_session, user, APP_KEY)

    assert await count_projects_by_region(db_session, scope) == {"asia": 1}


async def test_an_empty_scope_counts_zero_rather_than_everything(
    db_session, shema_app, three_regions
):
    """The failure mode a count has that a list does not: an unscoped ``COUNT`` returns a
    number rather than rows, so nothing about the response looks wrong."""
    user = await make_scoped_user(
        db_session, shema_app, email="zero@shema.test", role_key="resourceCircle", regions=[]
    )
    scope = await region_scope(db_session, user, APP_KEY)

    assert await count_projects(db_session, scope) == 0
    assert await count_projects_by_region(db_session, scope) == {}


# --- the property that keeps the three above true ------------------------------------


def test_no_service_reads_the_project_table_without_reaching_for_the_scope() -> None:
    """**The mechanism, not a convention.**

    The issue's line is that a query which can return an out-of-scope row is a bug even if
    no endpoint calls it that way. The way to make that true is for there to be no unscoped
    query to write: ``_scope.py`` owns the region predicate, and a service that names
    ``ShemaProject`` at all must also name ``within_scope`` or ``visible_projects``. The
    collection builds on the second, the counts compose the first into their own aggregate,
    and neither can be written without one.

    Read off the syntax tree rather than off the text, because prose in a docstring that
    *describes* the rule is not a breach of it — the first spelling of this test failed on
    ``__init__.py``'s own paragraph about the rule.

    What counts as reading the table is **building a** ``select`` **over it**, not naming the
    class. Naming it is what a file does when it takes a row somebody else already fetched:
    ``_consent.py``, ``_redaction.py``, ``_media_sharing.py`` and ``_audit.py`` all annotate a
    ``project: ShemaProject`` parameter, and ``read_record.py`` does the same — none of them
    can reach a row the scope did not hand them, which is the property, and flagging them
    would only teach the next author to drop the annotation. The one file that composes a
    query from a scoped one, ``browse_projects.py``, does it through ``list_projects``.

    A check and not a review item, which is the same argument ``docs/shema.md`` §6.4 makes
    for the consent gate. A file that genuinely needs an exemption has to change this test,
    and that is a line in a diff a reviewer reads.
    """
    package = Path(__file__).resolve().parents[2] / "app" / "services" / "shema"
    offenders = []
    for path in sorted(package.glob("*.py")):
        if path.name == "_scope.py":
            continue
        names = _names_used(path)
        if _selects_projects(path) and not names & {"within_scope", "visible_projects"}:
            offenders.append(path.name)

    assert offenders == [], f"reads shema_projects without the scope predicate: {offenders}"


def _selects_projects(path: Path) -> bool:
    """Whether the module builds a ``select`` whose subtree names ``ShemaProject``.

    ``select(ShemaProject)``, ``select(ShemaProject.id)`` and any ``.where``/``.join`` chain
    hanging off them all carry the ``Call`` node this looks for. A ``ShemaProject`` that only
    appears in an annotation or an ``isinstance`` does not.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
        if name != "select":
            continue
        for inner in ast.walk(node):
            if isinstance(inner, ast.Name) and inner.id == "ShemaProject":
                return True
    return False


def _names_used(path: Path) -> set[str]:
    """Every identifier the module actually uses, docstrings and comments excluded."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.id if isinstance(node, ast.Name) else node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Name | ast.Attribute)
    } | {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }


def test_no_router_in_the_module_issues_a_query() -> None:
    """``docs/shema.md`` §6.2's first refused temptation, and ADR 0009.

    The router may declare the scope dependency and hand the value down; it may not
    ``WHERE`` anything. A filter applied in a handler is a filter the next handler writes
    slightly differently.
    """
    package = Path(__file__).resolve().parents[2] / "app" / "api" / "shema"
    offenders = [
        path.name
        for path in sorted(package.glob("*.py"))
        if {"select", "execute", "scalars"} & _names_used(path)
    ]
    assert offenders == [], f"a router issues a query: {offenders}"


def test_the_scoped_select_is_composable_without_branching_on_the_scope() -> None:
    """Every scope produces a statement, including the two that have no regions to name.

    A global caller gets a literal true and an empty one a literal false, so a consumer
    never branches — and the branch that is never written is the one that is never written
    wrong.
    """
    for scope in (
        RegionScope(global_=True, regions=frozenset()),
        RegionScope(global_=False, regions=frozenset()),
        RegionScope(global_=False, regions=frozenset({"africa"})),
    ):
        assert str(visible_projects(scope)).lower().startswith("select")
        assert "where" in str(visible_projects(scope)).lower()


def test_the_python_and_sql_spellings_of_the_rule_agree() -> None:
    """``reaches`` is the write path's question and ``within_scope`` is the read path's.
    Two spellings of one rule is what this module is trying not to have, so they are
    adjacent in the source and asserted against the same cases here."""
    scoped = RegionScope(global_=False, regions=frozenset({"africa"}))
    empty = RegionScope(global_=False, regions=frozenset())
    everything = RegionScope(global_=True, regions=frozenset())

    assert reaches(scoped, AFRICA) and reaches(scoped, "africa")
    assert not reaches(scoped, ASIA)
    assert not reaches(empty, AFRICA)
    assert reaches(everything, AFRICA) and reaches(everything, ASIA)


# --- writing the scope ---------------------------------------------------------------


async def test_setting_a_scope_replaces_it_rather_than_appending(db_session, shema_app):
    """Narrowing somebody must not be a two-call operation: the call that removes is the one
    an operator forgets."""
    user = await make_scoped_user(
        db_session, shema_app, email="rewrite@shema.test", role_key="coordinator", regions=[AFRICA]
    )

    await set_region_scope(db_session, user.id, [ASIA, EUROPE])

    scope = await region_scope(db_session, user, APP_KEY)
    assert scope.regions == frozenset({"asia", "europe"})


async def test_re_stating_a_scope_does_not_restamp_the_rows_that_did_not_change(
    db_session, shema_app
):
    """An audit question asked later should not find every seat stamped with the day
    somebody added one region."""
    from sqlalchemy import select

    from app.db.models.shema_region import ShemaUserRegion

    user = await make_scoped_user(
        db_session, shema_app, email="restamp@shema.test", role_key="coordinator", regions=[AFRICA]
    )
    stmt = select(ShemaUserRegion.granted_at).where(
        ShemaUserRegion.user_id == user.id, ShemaUserRegion.region_key == AFRICA
    )
    before = (await db_session.execute(stmt)).scalar_one()

    await set_region_scope(db_session, user.id, [AFRICA, ASIA])

    assert (await db_session.execute(stmt)).scalar_one() == before


async def test_clearing_a_scope_leaves_the_account_reaching_nothing(
    db_session, shema_app, three_regions
):
    """Not everything. This is the call that can put an account on the floor by accident,
    and the floor is where it lands."""
    user = await make_scoped_user(
        db_session, shema_app, email="cleared@shema.test", role_key="coordinator", regions=[AFRICA]
    )

    await set_region_scope(db_session, user.id, [])

    scope = await region_scope(db_session, user, APP_KEY)
    assert await list_projects(db_session, scope) == []
    assert await count_projects(db_session, scope) == 0


async def test_a_region_key_outside_the_seven_is_refused_by_the_enum(db_session, shema_app):
    """The vocabulary is closed and the column is a native enum. A typo is a ``ValueError``
    at the call rather than a row nobody ever matches."""
    user = await make_scoped_user(
        db_session, shema_app, email="typo@shema.test", role_key="coordinator", regions=[]
    )

    with pytest.raises(ValueError):
        await set_region_scope(db_session, user.id, ["south_america"])


# --- the log line --------------------------------------------------------------------


async def test_a_refusal_is_logged_with_the_caller_and_without_the_protected_row(
    db_session, shema_app, three_regions, caplog
):
    """**The DoD's last line.**

    What has to be in the line: who asked, in what operation, with what reach. Without it a
    404 that is really a refusal is invisible, and that is the cost of having chosen an
    indistinguishable response.

    What must **not** be in it: anything about the row being protected. Its region is
    precisely the fact the refusal withholds, and a log is read by more people and kept
    longer than a response body. ``project_id`` is in the line because the caller supplied
    it — echoing back a value they already hold leaks nothing, and without it the event
    names no object and cannot be chased.
    """
    user = await make_scoped_user(
        db_session, shema_app, email="logged@shema.test", role_key="coordinator", regions=[AFRICA]
    )
    scope = await region_scope(db_session, user, APP_KEY)

    with (
        caplog.at_level(logging.WARNING, logger="app.services.shema._scope"),
        pytest.raises(NotFoundError),
    ):
        await get_project(db_session, scope, "hmong", user=user, operation="record_read")

    record = next(r for r in caplog.records if "out of region scope" in r.getMessage())
    assert record.shema_user_id == user.id
    assert record.shema_operation == "record_read"
    assert record.shema_project_id == "hmong"
    assert record.shema_scope_regions == ["africa"]
    assert record.shema_scope_global is False

    rendered = f"{record.getMessage()} {record.__dict__}"
    assert "asia" not in rendered.lower()
    assert "Hmong" not in rendered


async def test_the_refusal_log_does_not_carry_the_protected_rows_columns(
    db_session, shema_app, caplog
):
    """The row's own fields, asked for by name so a future ``extra`` that helpfully adds one
    fails here rather than in production."""
    await make_project(
        db_session, project_id="secret-tongue", region_key=ASIA, language_name="Secretish"
    )
    user = await make_scoped_user(
        db_session, shema_app, email="columns@shema.test", role_key="coordinator", regions=[AFRICA]
    )
    scope = await region_scope(db_session, user, APP_KEY)

    with (
        caplog.at_level(logging.WARNING, logger="app.services.shema._scope"),
        pytest.raises(NotFoundError),
    ):
        await get_project(db_session, scope, "secret-tongue", user=user)

    record = next(r for r in caplog.records if "out of region scope" in r.getMessage())
    for forbidden in ("region_key", "language_name", "location", "team", "sensitive"):
        assert not any(key.endswith(forbidden) for key in record.__dict__)


async def test_a_missing_id_reaches_the_same_line_and_is_not_called_an_authorization_refusal(
    db_session, shema_app, three_regions, caplog
):
    """**The indistinguishable answer, felt on the logging side.**

    ``get_project``'s branch fires on any miss of the scoped statement, so an id that never
    existed is logged by the same line an out-of-region one is. That is not a gap: settling
    which case it was would take the unscoped query the 404 exists to avoid.

    What the line must therefore not do is claim a decision the service never made. A
    mistyped slug counted as a refused authorization is a false positive on whatever reads
    these lines, so the message classifies the outcome — no row, for one of two reasons —
    and this asserts the wording in both directions, because the helpful shorter one is what
    a later reader restores.
    """
    user = await make_scoped_user(
        db_session,
        shema_app,
        email="typo-log@shema.test",
        role_key="coordinator",
        regions=[AFRICA],
    )
    scope = await region_scope(db_session, user, APP_KEY)

    with (
        caplog.at_level(logging.WARNING, logger="app.services.shema._scope"),
        pytest.raises(NotFoundError),
    ):
        await get_project(db_session, scope, "no-such-project-at-all", user=user)

    (record,) = [r for r in caplog.records if r.name == "app.services.shema._scope"]
    assert record.shema_project_id == "no-such-project-at-all"
    assert record.shema_scope_regions == ["africa"]
    assert "no such id" in record.getMessage()
    assert "authorization refused" not in record.getMessage()


# --- the router hands the value down, and nothing else -------------------------------


async def test_the_router_receives_the_scope_the_service_computed(
    db_session, client, shema_app
) -> None:
    """The dependency is declared in ``app/api/shema/`` and computed in
    ``app/services/shema/``. This asserts the seam, through the real chain."""
    user = await make_scoped_user(
        db_session, shema_app, email="probe@shema.test", role_key="coordinator", regions=[ASIA]
    )

    res = await client.get(SCOPE_PROBE, headers=await auth_header(db_session, user))

    assert res.status_code == 200
    assert res.json() == {"global": False, "regions": ["asia"]}
