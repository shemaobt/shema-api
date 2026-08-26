"""ENG-449 — the necklace served bead by bead, instead of four numbers.

`CoverageView` answers `{engaged, surfaced, total, absence_index}`, and those aggregates are
exactly what the product forbids putting in front of a facilitator. This route answers the
opposite: every element of the passage, named in three languages, typed, placed in its scene,
and carrying its own coverage state.

Three of these carry the slice.

**Behaviour 2** is the only one that can see the difference between a state read off one
session and a state rebuilt from the team's history. Coverage does not survive a session —
`create_session` opens every one with `initial_state` — so a bead engaged in session A and
merely surfaced in session B has no single row that knows it is engaged. A route reading
`coverage_state` passes every other test here and fails this one.

**Behaviour 7** is the non-enumeration rule from ENG-443 and ENG-444 repeated on a third
route, plus the ordering that keeps it true now that a second refusal exists: the team gate
runs before the label gate, so the pericope's own message never tells a stranger whether a
team id is real.

**Behaviour 3** asserts an absence. It is the only one that catches an aggregate leaking back
in, and it pins the field set exactly rather than checking that the expected fields are
present, because the failure worth catching is a field nobody thought to look for. It walks
the body's names at every depth — names and not text, since `not_encountered` contains
"count" and `engaged` is a coverage state this route is supposed to speak.
"""

import itertools

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ProjectRole
from app.services.internalization_room import sessions as room
from app.services.internalization_room.canon.elements import ElementKind, element_keys
from app.services.internalization_room.coverage import CoverageStatus
from tests.baker import (
    grant_facilitator_app_role,
    make_language,
    make_project,
    make_project_user_access,
    make_user,
    open_ir_session,
)

TEAM_NOT_FOUND = "Team not found"

SURFACED = CoverageStatus.SURFACED.value
PARTIALLY_ENGAGED = CoverageStatus.PARTIALLY_ENGAGED.value
ENGAGED = CoverageStatus.ENGAGED.value
NOT_ENCOUNTERED = CoverageStatus.NOT_ENCOUNTERED.value

#: What the versioned canon serves for the pilot's four passages, and what the Desk draws.
#: Written out rather than derived from `elements_for`, so a canon that silently loses a bead
#: fails here instead of agreeing with itself.
PILOT = {
    "P01": {"elements": 29, "scenes": [1, 2, 3, 4], "preserved": 5},
    "P02": {"elements": 24, "scenes": [1, 2, 3], "preserved": 4},
    "P05": {"elements": 34, "scenes": [1, 2, 3, 4], "preserved": 5},
    "P14": {"elements": 10, "scenes": [1], "preserved": 0},
}

#: Real canon, no labels written for it. Ten of Ruth's fourteen are in this position.
UNLABELLED = "P03"

#: A name the canon never had, which is the one thing this route still refuses. The ordering
#: test has to use this rather than `UNLABELLED`: since ENG-442 an untranslated passage is
#: served, so a case built on it would pass with the two gates in either order.
OUTSIDE_THE_BOOK = "P99"


def coverage_url(team_id: str, pericope: str | None = None) -> str:
    url = f"/api/facilitator/teams/{team_id}/coverage"
    return url if pericope is None else f"{url}?pericope={pericope}"


@pytest.fixture()
async def client(db_session: AsyncSession):
    from fastapi import FastAPI

    from app.api.facilitator.teams import facilitator_teams_router
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    test_app = FastAPI()
    test_app.include_router(facilitator_teams_router, prefix="/api/facilitator/teams")
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def auth_header(db: AsyncSession, user) -> dict[str, str]:
    from app.services.auth.issue_tokens import issue_tokens

    access, _refresh = await issue_tokens(db, user)
    return {"Authorization": f"Bearer {access}"}


_codes = itertools.count()


async def a_facilitator(db: AsyncSession, *, email="facilitator@example.com"):
    """A user who facilitates one team. The language code is counted, not derived from the
    email: two addresses sharing a prefix collide on a unique column and fail the test for a
    reason that has nothing to do with what it asserts."""
    user = await make_user(db, email=email)
    language = await make_language(db, name=f"Lang {email}", code=f"t{next(_codes):02d}")
    project = await make_project(db, language.id, name=f"Team {email}")
    await make_project_user_access(db, project.id, user.id, role=ProjectRole.FACILITATOR)
    await grant_facilitator_app_role(db, user.id)
    return user, project, await auth_header(db, user)


async def a_session_that_moved(
    db: AsyncSession, *, project_id: str | None, pericope: str, moved: dict[str, str]
):
    """A session of this team that advanced these beads.

    The events are written by `apply_coverage` rather than inserted, so the fixture cannot
    agree with a route that reads them differently from how they are written. The session row
    itself comes from the room wherever the room still opens the passage — see
    `open_ir_session`.
    """
    session = await open_ir_session(db, pericope=pericope, project_id=project_id)
    await room.apply_coverage(db, session.id, moved)
    return session


def by_key(body: list[dict]) -> dict[str, dict]:
    return {element["key"]: element for element in body}


def names_in(body) -> set[str]:
    """Every field name anywhere in the body, however deeply nested.

    Names, not text: `not_encountered` contains "count" and `engaged` is a coverage state, so
    scanning the serialised body for words finds the vocabulary this route is *supposed* to
    speak. What must not appear is a field carrying a number about the team.
    """
    if isinstance(body, dict):
        return set(body) | {name for value in body.values() for name in names_in(value)}
    if isinstance(body, list):
        return {name for item in body for name in names_in(item)}
    return set()


class QueryCounter:
    """Counts statements against the session's connection, between enter and exit."""

    def __init__(self, db: AsyncSession) -> None:
        self._engine = db.get_bind().engine
        self.statements: list[str] = []

    def _record(self, conn, cursor, statement, parameters, context, executemany) -> None:
        self.statements.append(statement)

    def __enter__(self) -> "QueryCounter":
        event.listen(self._engine, "before_cursor_execute", self._record)
        return self

    def __exit__(self, *exc) -> None:
        event.remove(self._engine, "before_cursor_execute", self._record)

    def against(self, table: str) -> list[str]:
        return [s for s in self.statements if table in s]


# ---------------------------------------------------------------- behaviour 1: the four sizes


@pytest.mark.parametrize("pericope", sorted(PILOT))
async def test_a_pilot_passage_serves_its_exact_beads(
    client, db_session: AsyncSession, pericope: str
) -> None:
    """Behaviour 1 — each pilot passage serves its own count, scenes and preservation group.

    P14 is a case of this and not a test of its own: one scene, and the fifth group empty.
    Both are real passages of Ruth rather than edge cases, and asserting them twice would be
    the same branch covered under two names.
    """
    _user, project, headers = await a_facilitator(db_session, email=f"b1{pericope}@x.com")

    response = await client.get(coverage_url(project.id, pericope), headers=headers)

    assert response.status_code == 200
    body = response.json()
    expected = PILOT[pericope]
    assert len(body) == expected["elements"]
    assert sorted({e["scene"] for e in body if e["scene"] is not None}) == [
        f"scene:{number}" for number in expected["scenes"]
    ]
    preserved = [e for e in body if e["kind"] == ElementKind.PRESERVED.value]
    assert len(preserved) == expected["preserved"]
    assert all(e["scene"] is None for e in preserved)
    assert all(e["scene"] is not None for e in body if e not in preserved)


async def test_every_bead_is_named_in_three_languages(client, db_session: AsyncSession) -> None:
    """Behaviour 1 — no bead reaches the Desk as an identifier.

    Non-empty is not the assertion. Serving `preserved:R3` as its own label is non-empty and
    is exactly the failure the label catalogue exists to prevent, so the key is asserted
    absent and the names asserted distinct from each other — a facilitator has to be able to
    tell two beads apart by reading them.

    What is deliberately *not* asserted is that the three languages differ. `being:B10` is
    Rute in all three, and demanding a difference would demand a mistranslation.
    """
    _user, project, headers = await a_facilitator(db_session, email="b1lang@x.com")

    body = (await client.get(coverage_url(project.id, "P02"), headers=headers)).json()

    assert len(body) == PILOT["P02"]["elements"]
    for element in body:
        for language in ("pt", "en", "es"):
            named = element[f"label_{language}"]
            assert named.strip()
            assert named != element["key"]
    assert len({element["label_pt"] for element in body}) == len(body)


# ------------------------------------------------------------- behaviour 2: touched_in_session


async def test_touched_in_session_names_the_last_session_to_move_the_bead(
    client, db_session: AsyncSession
) -> None:
    """Behaviour 2 — across several sessions, the answer is the last one that moved it."""
    _user, project, headers = await a_facilitator(db_session, email="b3@x.com")
    first, second = element_keys("P02")[0], element_keys("P02")[1]

    earlier = await a_session_that_moved(
        db_session, project_id=project.id, pericope="P02", moved={first: SURFACED}
    )
    later = await a_session_that_moved(
        db_session,
        project_id=project.id,
        pericope="P02",
        moved={first: ENGAGED, second: SURFACED},
    )

    body = by_key((await client.get(coverage_url(project.id, "P02"), headers=headers)).json())

    assert body[first]["touched_in_session"]["session_id"] == later.id
    assert body[second]["touched_in_session"]["session_id"] == later.id
    assert body[first]["touched_in_session"]["at"]
    assert earlier.id != later.id


async def test_status_is_the_furthest_the_team_ever_reached(
    client, db_session: AsyncSession
) -> None:
    """Behaviour 2 — the state is the team's history, not one session's tracker.

    Coverage does not survive a session: the second session opens at `not_encountered` for
    every bead. A route reading `coverage_state` answers `surfaced` here.
    """
    _user, project, headers = await a_facilitator(db_session, email="b3furthest@x.com")
    bead = element_keys("P02")[0]

    await a_session_that_moved(
        db_session, project_id=project.id, pericope="P02", moved={bead: ENGAGED}
    )
    await a_session_that_moved(
        db_session, project_id=project.id, pericope="P02", moved={bead: SURFACED}
    )

    body = by_key((await client.get(coverage_url(project.id, "P02"), headers=headers)).json())

    assert body[bead]["status"] == ENGAGED


async def test_the_named_session_is_the_one_that_reached_the_status_shown(
    client, db_session: AsyncSession
) -> None:
    """Behaviour 2 — status and session are one statement and must not contradict each other.

    The common case, not an edge: every session opens at `initial_state`, so a bead the team
    engaged on Tuesday earns a fresh `surfaced` event the moment Wednesday's Guide mentions it
    again — `record_transitions` compares against Wednesday's own tracker, where the bead
    really did move. At team level it did not move at all.

    Naming Wednesday would put "Trabalhado · last touched Wednesday" in front of a facilitator
    for a session that only surfaced it. The session named is the one that carried the bead to
    where it now stands.
    """
    _user, project, headers = await a_facilitator(db_session, email="b2reached@x.com")
    bead = element_keys("P02")[0]

    reached = await a_session_that_moved(
        db_session, project_id=project.id, pericope="P02", moved={bead: ENGAGED}
    )
    later = await a_session_that_moved(
        db_session, project_id=project.id, pericope="P02", moved={bead: SURFACED}
    )

    body = by_key((await client.get(coverage_url(project.id, "P02"), headers=headers)).json())

    assert body[bead]["status"] == ENGAGED
    assert body[bead]["touched_in_session"]["session_id"] == reached.id
    assert body[bead]["touched_in_session"]["session_id"] != later.id


async def test_holding_a_bead_where_it_already_stood_does_not_rename_it(
    client, db_session: AsyncSession
) -> None:
    """Behaviour 2 — two sessions reaching the same status: the one that moved it is the first.

    Once a bead is engaged it has nowhere further to go, so a later session reaching `engaged`
    again moved nothing. "Which session last moved it" is the session it last actually moved
    in, which is when it arrived where it stands.
    """
    _user, project, headers = await a_facilitator(db_session, email="b2held@x.com")
    bead = element_keys("P02")[0]

    moved = await a_session_that_moved(
        db_session, project_id=project.id, pericope="P02", moved={bead: ENGAGED}
    )
    held = await a_session_that_moved(
        db_session, project_id=project.id, pericope="P02", moved={bead: ENGAGED}
    )

    body = by_key((await client.get(coverage_url(project.id, "P02"), headers=headers)).json())

    assert body[bead]["touched_in_session"]["session_id"] == moved.id
    assert moved.id != held.id


async def test_an_untouched_bead_says_so_and_names_no_session(
    client, db_session: AsyncSession
) -> None:
    """Behaviour 2 — a passage nobody worked serves a whole necklace, not an empty list."""
    _user, project, headers = await a_facilitator(db_session, email="b3untouched@x.com")

    body = (await client.get(coverage_url(project.id, "P14"), headers=headers)).json()

    assert len(body) == 10
    assert {e["status"] for e in body} == {NOT_ENCOUNTERED}
    assert all(e["touched_in_session"] is None for e in body)


async def test_the_fourth_state_reaches_the_desk(client, db_session: AsyncSession) -> None:
    """Behaviour 2 — `partially_engaged` is served as itself, not folded into a neighbour."""
    _user, project, headers = await a_facilitator(db_session, email="b3fourth@x.com")
    bead = element_keys("P02")[0]

    await a_session_that_moved(
        db_session, project_id=project.id, pericope="P02", moved={bead: PARTIALLY_ENGAGED}
    )

    body = by_key((await client.get(coverage_url(project.id, "P02"), headers=headers)).json())

    assert body[bead]["status"] == PARTIALLY_ENGAGED


async def test_another_teams_work_on_the_same_bead_does_not_leak(
    client, db_session: AsyncSession
) -> None:
    """Behaviour 2 — element keys are the canon's, so two teams carry the same `being:B3`."""
    _user, mine, headers = await a_facilitator(db_session, email="b3mine@x.com")
    _other_user, theirs, _other = await a_facilitator(db_session, email="b3theirs@x.com")
    bead = element_keys("P02")[0]

    await a_session_that_moved(
        db_session, project_id=theirs.id, pericope="P02", moved={bead: ENGAGED}
    )

    body = by_key((await client.get(coverage_url(mine.id, "P02"), headers=headers)).json())

    assert body[bead]["status"] == NOT_ENCOUNTERED
    assert body[bead]["touched_in_session"] is None


async def test_a_session_belonging_to_no_team_is_not_this_teams_work(
    client, db_session: AsyncSession
) -> None:
    """Behaviour 2 — `project_id` is nullable, and null is nobody rather than everybody."""
    _user, project, headers = await a_facilitator(db_session, email="b3null@x.com")
    bead = element_keys("P02")[0]

    await a_session_that_moved(db_session, project_id=None, pericope="P02", moved={bead: ENGAGED})

    body = by_key((await client.get(coverage_url(project.id, "P02"), headers=headers)).json())

    assert body[bead]["status"] == NOT_ENCOUNTERED


async def test_another_passage_of_the_same_team_does_not_leak(
    client, db_session: AsyncSession
) -> None:
    """Behaviour 2 — a key alone does not name a bead; the passage is half of its identity."""
    _user, project, headers = await a_facilitator(db_session, email="b3passage@x.com")
    shared = next(key for key in element_keys("P02") if key in element_keys("P05"))

    await a_session_that_moved(
        db_session, project_id=project.id, pericope="P05", moved={shared: ENGAGED}
    )

    body = by_key((await client.get(coverage_url(project.id, "P02"), headers=headers)).json())

    assert body[shared]["status"] == NOT_ENCOUNTERED


# ------------------------------------------------------------- behaviour 3: no aggregate ships


async def test_no_aggregate_reaches_the_facilitator(client, db_session: AsyncSession) -> None:
    """Behaviour 3 — the counts this product forbids are absent from the whole body.

    Read off the serialised response rather than off named fields: an aggregate added at the
    top level, or inside an element, or under a name nobody here thought of, is the failure
    this test exists for.
    """
    _user, project, headers = await a_facilitator(db_session, email="b4@x.com")
    bead = element_keys("P02")[0]
    await a_session_that_moved(
        db_session, project_id=project.id, pericope="P02", moved={bead: ENGAGED}
    )

    response = await client.get(coverage_url(project.id, "P02"), headers=headers)

    assert isinstance(response.json(), list)
    served = {name for element in response.json() for name in element}
    assert served == {
        "key",
        "label_pt",
        "label_en",
        "label_es",
        "kind",
        "scene",
        "status",
        "touched_in_session",
    }
    forbidden = {"engaged", "surfaced", "total", "percent", "percentage", "absence_index"}
    assert not forbidden & names_in(response.json())


# --------------------------------------------------------------- behaviour 4: one query


async def test_the_whole_necklace_costs_one_query(client, db_session: AsyncSession) -> None:
    """Behaviour 4 — 34 beads is 34 chances to write an N+1 over the events table."""
    _user, project, headers = await a_facilitator(db_session, email="b5@x.com")
    for key in element_keys("P05")[:5]:
        await a_session_that_moved(
            db_session, project_id=project.id, pericope="P05", moved={key: ENGAGED}
        )

    with QueryCounter(db_session) as counted:
        response = await client.get(coverage_url(project.id, "P05"), headers=headers)

    assert response.status_code == 200
    assert len(response.json()) == 34
    assert len(counted.against("ir_coverage_events")) == 1


# ------------------------------------------------------- behaviour 5: the pericope is required


async def test_the_pericope_omitted_means_the_one_the_team_is_on(
    client, db_session: AsyncSession
) -> None:
    """Behaviour 5 — required when this route landed, defaulted now that ENG-450 resolves.

    It answered 422 because nothing in this codebase knew where a team stood, and falling back
    to a constant would have answered every team about the first passage with full confidence.
    The default is not that constant: it is the team's own next unfinished passage, so a team
    that has closed the first is answered about the second.
    """
    _user, project, headers = await a_facilitator(db_session, email="b6@x.com")
    await a_session_that_moved(
        db_session,
        project_id=project.id,
        pericope="P01",
        moved=dict.fromkeys(element_keys("P01"), PARTIALLY_ENGAGED),
    )

    response = await client.get(coverage_url(project.id), headers=headers)
    named = await client.get(coverage_url(project.id, "P02"), headers=headers)

    assert response.status_code == 200
    assert response.json() == named.json()


async def test_a_team_that_has_not_started_is_answered_about_the_first_passage(
    client, db_session: AsyncSession
) -> None:
    _user, project, headers = await a_facilitator(db_session, email="b6start@x.com")

    body = (await client.get(coverage_url(project.id), headers=headers)).json()

    assert [bead["key"] for bead in body] == element_keys("P01")


async def test_a_team_that_closed_the_book_has_no_passage_to_default_to(
    client, db_session: AsyncSession
) -> None:
    """409 rather than 400 or 404: the request is well formed and the team exists.

    There is simply no passage they are on, which is the end of the walk. Naming one answers.
    """
    from app.services.internalization_room.canon.parse_map import ROOM_BOOK, load_book

    _user, project, headers = await a_facilitator(db_session, email="b6end@x.com")
    for meaning_map in load_book(ROOM_BOOK):
        await a_session_that_moved(
            db_session,
            project_id=project.id,
            pericope=meaning_map.pericope_num,
            moved=dict.fromkeys(element_keys(meaning_map.pericope_num), PARTIALLY_ENGAGED),
        )

    refused = await client.get(coverage_url(project.id), headers=headers)
    named = await client.get(coverage_url(project.id, "P01"), headers=headers)

    assert refused.status_code == 409
    assert named.status_code == 200


# ------------------------------------------------------------- behaviour 6: the two refusals


async def test_an_unlabelled_passage_is_served_with_the_two_translations_absent(
    client, db_session: AsyncSession
) -> None:
    """Behaviour 6 — a real passage the pilot has not written labels for.

    This route refused it until ENG-442 landed. It does not any more, and the reason is worth
    keeping: the canon serves all fourteen of Ruth, D-03 walks every team through them, and
    refusing ten of the fourteen would have taken the whole necklace down for a passage the
    team is genuinely working on. English comes almost free from the canon; Portuguese and
    Spanish are absent rather than filled in with it, which is what stops a sentence a
    facilitator does not read arriving under the name of their own language.
    """
    _user, project, headers = await a_facilitator(db_session, email="b7@x.com")

    response = await client.get(coverage_url(project.id, UNLABELLED), headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body, "a passagem sem catalogo respondeu vazia em vez de vir do canon"
    assert all(bead["label_en"] for bead in body)
    assert all(bead["label_pt"] is None and bead["label_es"] is None for bead in body)


async def test_a_pericope_outside_the_book_is_refused(client, db_session: AsyncSession) -> None:
    """Behaviour 6 — a name the canon never had is refused, not answered empty.

    The message is asserted, not only the status: a route that does not exist answers 404
    too, and this test has to be able to tell the two apart.
    """
    _user, project, headers = await a_facilitator(db_session, email="b7canon@x.com")

    response = await client.get(coverage_url(project.id, OUTSIDE_THE_BOOK), headers=headers)

    assert response.status_code == 404
    assert OUTSIDE_THE_BOOK in response.json()["detail"]


async def test_the_scene_a_bead_sits_in_is_served_as_a_key_and_not_as_a_number(
    client, db_session: AsyncSession
) -> None:
    """The scene a bead belongs to is named the way every other bead is named.

    It served the bare number, which obliges the client to build `scene:{n}` before it can
    relate a bead to the scene bead beside it on the necklace — and building a key on the
    client is what this whole route exists to prevent. The day the key's shape changes, a
    client composing it composes the wrong one, and nothing anywhere goes red: the necklace
    simply stops joining up.

    Asserted as membership rather than as a string, which is the difference that matters. A
    case comparing against a literal `"scene:1"` passes just as well when the server invents a
    format nothing else uses; this one only passes while the value is a key the same response
    actually carries.
    """
    _user, project, headers = await a_facilitator(db_session, email="b8scene@x.com")

    body = (await client.get(coverage_url(project.id, "P01"), headers=headers)).json()

    served = {bead["key"] for bead in body}
    scenes = {bead["scene"] for bead in body if bead["scene"] is not None}

    assert scenes, "nenhuma conta disse em que cena está"
    assert scenes <= served, f"a cena servida não é uma conta deste colar: {scenes - served}"
    assert all(bead["scene"] == bead["key"] for bead in body if bead["kind"] == "scene")


async def test_a_preservation_rule_still_belongs_to_no_scene(
    client, db_session: AsyncSession
) -> None:
    """The absence stays an absence, and it is not the empty string.

    Written beside the case above because that one only asserts about beads that have a
    scene, so a change that gave every bead a scene would leave it green.
    """
    _user, project, headers = await a_facilitator(db_session, email="b8noscene@x.com")

    body = (await client.get(coverage_url(project.id, "P01"), headers=headers)).json()

    assert [bead["scene"] for bead in body if bead["kind"] == "preserved"] == [None] * 5


# ---------------------------------------------- behaviour 7: non-enumeration, and its ordering


async def test_a_team_the_caller_does_not_facilitate_reads_as_absent(
    client, db_session: AsyncSession
) -> None:
    """Behaviour 7 — the ENG-443 rule on a third route."""
    _user, _mine, headers = await a_facilitator(db_session, email="b8mine@x.com")
    _other_user, theirs, _other = await a_facilitator(db_session, email="b8theirs@x.com")

    refused = await client.get(coverage_url(theirs.id, "P02"), headers=headers)
    absent = await client.get(coverage_url("no-such-team", "P02"), headers=headers)

    assert refused.status_code == absent.status_code == 404
    assert refused.json()["detail"] == absent.json()["detail"] == TEAM_NOT_FOUND


async def test_the_team_gate_runs_before_the_label_gate(client, db_session: AsyncSession) -> None:
    """Behaviour 7 — the ordering that keeps the rule true now there are two 404s.

    The pericope's own message names the passage, so a stranger who could reach it by asking
    about a team id would learn that the id is real. Checking the team first means that
    message is only ever read by someone already through the gate.
    """
    _user, _mine, headers = await a_facilitator(db_session, email="b8order@x.com")
    _other_user, theirs, _other = await a_facilitator(db_session, email="b8ordertheirs@x.com")

    response = await client.get(coverage_url(theirs.id, OUTSIDE_THE_BOOK), headers=headers)

    assert response.status_code == 404
    assert response.json()["detail"] == TEAM_NOT_FOUND


async def test_an_anonymous_caller_reads_nothing(client, db_session: AsyncSession) -> None:
    """Behaviour 7 — the route is behind the same auth as the rest of the panel."""
    _user, project, _headers = await a_facilitator(db_session, email="b8anon@x.com")

    response = await client.get(coverage_url(project.id, "P02"))

    assert response.status_code in (401, 403)


# ------------------------------------------------------------------ behaviour 8: the bead order


async def test_the_served_order_is_the_canons_bead_order(client, db_session: AsyncSession) -> None:
    """Behaviour 8 — the server serves the order; the client does not re-sort it."""
    _user, project, headers = await a_facilitator(db_session, email="b9@x.com")

    body = (await client.get(coverage_url(project.id, "P01"), headers=headers)).json()

    assert [element["key"] for element in body] == element_keys("P01")
