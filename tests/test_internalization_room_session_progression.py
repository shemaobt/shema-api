"""ENG-450 — the session opens where the team actually stands.

`create_session` took `pericope: str = DEFAULT_PERICOPE`, so a room that did not name a
passage was answered P01 with full confidence, whoever was asking and however much of the
book they had already walked. This is the other half of the resolution: not "what does the
server know about this team" but "what does the server do with it".

Two of these carry the slice.

**`test_a_line_prepared_for_a_passage_the_team_has_since_left_is_not_handed_over`** is the
one that cannot be replaced by re-deriving the resolution at hand-over time. The old guard
compared the opening's passage against `DEFAULT_PERICOPE`, and it only worked because one
constant appeared in both places. Re-deriving looks equivalent and is not: if the team's
history moves between the panorama and the opening — another device of the same team closing
the passage — both derivations agree on the *new* passage while the prepared line was written
from the *old* one, and the guard waves through exactly the case it exists to stop. To people
who cannot read, delivered as the passage's own framing.

**`test_no_constant_passage_is_left_in_the_source`** is the criterion that a slice can
otherwise appear to satisfy while one path still answers P01 to everybody.
"""

from __future__ import annotations

import ast
import itertools
import re
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.db.models.internalization_room import IRSession, IRSessionStatus
from app.services.internalization_room import sessions as room
from app.services.internalization_room.canon.elements import element_keys
from app.services.internalization_room.canon.parse_map import ROOM_BOOK, load_book
from app.services.internalization_room.coverage import CoverageStatus
from app.services.internalization_room.prepare_opening import hand_over
from tests.baker import make_language, make_project

_codes = itertools.count()

PARTIALLY_ENGAGED = CoverageStatus.PARTIALLY_ENGAGED.value

CANON = [meaning_map.pericope_num for meaning_map in load_book(ROOM_BOOK)]
FIRST, SECOND = CANON[0], CANON[1]


async def a_team(db: AsyncSession, *, name: str):
    language = await make_language(db, name=name, code=f"s{next(_codes):02d}")
    return await make_project(db, language.id, name=name)


def closed(pericope: str) -> dict[str, str]:
    return dict.fromkeys(element_keys(pericope), PARTIALLY_ENGAGED)


async def having_closed(db: AsyncSession, team, *pericopes: str) -> None:
    """Walk the team through these passages the way the room does, so nothing is inserted."""
    for pericope in pericopes:
        session = await room.create_session(db, pericope=pericope, project_id=team.id)
        await room.apply_coverage(db, session.id, closed(pericope))


# ------------------------------------------------------------------- opening where the team is


@pytest.mark.asyncio
async def test_a_session_opened_without_a_passage_starts_the_team_at_the_beginning(
    db_session: AsyncSession,
) -> None:
    team = await a_team(db_session, name="Primeira vez")

    session = await room.create_session(db_session, project_id=team.id)

    assert session.pericope == FIRST
    assert session.coverage_state == dict.fromkeys(
        element_keys(FIRST), CoverageStatus.NOT_ENCOUNTERED.value
    )


@pytest.mark.asyncio
async def test_a_session_opened_without_a_passage_lands_on_the_teams_next_one(
    db_session: AsyncSession,
) -> None:
    """The acceptance criterion: a team whose first passage met the floor opens on the second."""
    team = await a_team(db_session, name="Andou")
    await having_closed(db_session, team, FIRST)

    session = await room.create_session(db_session, project_id=team.id)

    assert session.pericope == SECOND


@pytest.mark.asyncio
async def test_two_teams_open_on_their_own_passages_in_the_same_installation(
    db_session: AsyncSession,
) -> None:
    ahead = await a_team(db_session, name="Adiantada")
    behind = await a_team(db_session, name="Atrasada")
    await having_closed(db_session, ahead, FIRST)

    for_ahead = await room.create_session(db_session, project_id=ahead.id)
    for_behind = await room.create_session(db_session, project_id=behind.id)

    assert (for_ahead.pericope, for_behind.pericope) == (SECOND, FIRST)


@pytest.mark.asyncio
async def test_a_tablet_that_never_said_whose_it_is_still_opens_a_session(
    db_session: AsyncSession,
) -> None:
    """The field's common case today: the app does not send its credential until ENG-454.

    Refusing here would take every room offline to gain a column value.
    """
    session = await room.create_session(db_session, project_id=None)

    assert session.pericope == FIRST


@pytest.mark.asyncio
async def test_a_named_passage_is_obeyed_and_not_second_guessed(
    db_session: AsyncSession,
) -> None:
    """Resolution fills a silence; it does not overrule a request."""
    team = await a_team(db_session, name="Escolheu")

    session = await room.create_session(db_session, pericope=CANON[4], project_id=team.id)

    assert session.pericope == CANON[4]


# --------------------------------------------------------------------- the end of the book


@pytest.mark.asyncio
async def test_a_team_that_closed_the_last_passage_is_refused_rather_than_sent_round_again(
    db_session: AsyncSession,
) -> None:
    """The defined state the issue asks for: not a wrap-around, not a crash.

    409 and not 400: the request is well formed and the team exists — it is the team's own
    position that leaves nothing to open. Naming a passage still works, which is the door out.
    """
    team = await a_team(db_session, name="Terminou")
    await having_closed(db_session, team, *CANON)

    with pytest.raises(ConflictError):
        await room.create_session(db_session, project_id=team.id)


@pytest.mark.asyncio
async def test_a_team_that_finished_the_book_may_still_be_given_a_passage_by_name(
    db_session: AsyncSession,
) -> None:
    team = await a_team(db_session, name="Terminou mas volta")
    await having_closed(db_session, team, *CANON)

    session = await room.create_session(db_session, pericope=FIRST, project_id=team.id)

    assert session.pericope == FIRST


# ------------------------------------------------------------ the panorama and its prepared line


@pytest.mark.asyncio
async def test_the_panorama_alias_still_names_the_book_the_room_serves(
    db_session: AsyncSession,
) -> None:
    """`OV` expanded through `book_of(DEFAULT_PERICOPE)`, which is why it is in this slice.

    The client asks for the panorama without naming a book and the canon stays on this side.
    A book is not a passage, so replacing the pericope constant with `ROOM_BOOK` is not
    trading one constant for another: the room serves one book, and `elements_for`,
    `labelled_elements` and `run_turn` already take it as a parameter.
    """
    session = await room.create_session(db_session, pericope="OV")

    assert session.pericope == f"OV-{ROOM_BOOK}"
    assert room.is_panorama(session.pericope)
    assert session.coverage_state == {}


def test_a_ready_line_is_handed_to_the_session_it_was_written_for() -> None:
    panorama = IRSession(id="ov", pericope=f"OV-{ROOM_BOOK}", prepared_pericope=SECOND)
    panorama.prepared_speech = "a primeira fala"
    panorama.prepared_audio_key = "tts/v/p02.mp3"
    opening = IRSession(id="s1", pericope=SECOND)

    assert hand_over(panorama, opening) is True
    assert opening.prepared_speech == "a primeira fala"


def test_a_line_prepared_for_a_passage_the_team_has_since_left_is_not_handed_over() -> None:
    """The case a re-derived guard waves through, which is why the passage is recorded.

    The panorama wrote the second passage's opening. While the team was still hearing it,
    another of their devices closed that passage, so the resolution now says the third — and
    the session that opens is the third. Comparing the opening against a freshly resolved
    passage compares the third to the third and hands over a line written from the second
    passage's meaning map, spoken as the third's own framing.
    """
    panorama = IRSession(id="ov", pericope=f"OV-{ROOM_BOOK}", prepared_pericope=SECOND)
    panorama.prepared_speech = "a fala da segunda"
    panorama.prepared_audio_key = "tts/v/p02.mp3"
    opening_on_the_next_one = IRSession(id="s1", pericope=CANON[2])

    assert hand_over(panorama, opening_on_the_next_one) is False
    assert opening_on_the_next_one.prepared_speech is None
    assert panorama.prepared_speech == "a fala da segunda", (
        "a fala foi gasta por uma sessao que nao a recebeu"
    )


def test_a_line_with_no_passage_recorded_is_not_handed_to_anybody() -> None:
    """A row written before this slice carries no `prepared_pericope`, and cannot be trusted.

    Biased the same way the floor is: what is unknown is refused. The cost is one session
    writing its own opening; the cost of the other direction is P01's framing spoken over
    whatever passage the team is actually on.
    """
    panorama = IRSession(id="ov", pericope=f"OV-{ROOM_BOOK}", prepared_pericope=None)
    panorama.prepared_speech = "de antes desta fatia"
    panorama.prepared_audio_key = "tts/v/velha.mp3"

    assert hand_over(panorama, IRSession(id="s1", pericope=FIRST)) is False


# -------------------------------------------------------------------- the constant, and its paths


def test_no_constant_passage_is_left_in_the_source() -> None:
    """`DEFAULT_PERICOPE` gone, and gone from every path that read it.

    Written as a sweep of the tree rather than an import that fails, because the failure worth
    catching is the one path somebody left behind: a slice with the constant deleted from its
    own module and still consulted somewhere else looks finished and answers P01 to everybody.
    """
    app_dir = Path(__file__).resolve().parents[1] / "app"
    named = sorted(
        {
            str(source.relative_to(app_dir))
            for source in app_dir.rglob("*.py")
            if "DEFAULT_PERICOPE" in _identifiers(source)
        }
    )

    assert named == [], f"a constante de perícope sobreviveu em: {named}"


def _identifiers(source: Path) -> set[str]:
    """Every name a module defines, reads or imports — and nothing it merely talks about.

    The docstrings that explain what this constant was and why it is gone are the record of
    the decision, and a text search would read them as the thing they describe.
    """
    tree = ast.parse(source.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            found.add(node.id)
        elif isinstance(node, ast.Attribute):
            found.add(node.attr)
        elif isinstance(node, ast.alias):
            found.add(node.asname or node.name)
    return found


def test_no_module_carries_a_passage_of_the_book_written_into_it() -> None:
    """The same criterion one level below the name, since renaming would satisfy the above.

    Read with `ast` rather than with a regex, and the difference is the whole test: this
    module's own prose names P01 while explaining why it is not in the code, and a text sweep
    would call that a violation. Docstrings are prose *about* a module and are excluded; every
    other string literal is not, so a passage reaching a decision was handed there.
    """
    app_dir = Path(__file__).resolve().parents[1] / "app"
    looks_like_a_passage = re.compile(r"^P\d{2}$")
    named = sorted(
        {
            str(source.relative_to(app_dir))
            for source in app_dir.rglob("*.py")
            for written in _string_literals(source)
            if looks_like_a_passage.match(written)
        }
    )

    assert named == [], f"uma perícope está escrita dentro de: {named}"


_CARRIES_A_DOCSTRING = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)


def _string_literals(source: Path) -> list[str]:
    """Every string literal in a module except its docstrings."""
    tree = ast.parse(source.read_text(encoding="utf-8"))
    prose = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(node, _CARRIES_A_DOCSTRING)
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
        and isinstance(node.body[0].value.value, str)
    }
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in prose
    ]


@pytest.mark.asyncio
async def test_the_session_the_room_opens_still_refuses_canon_it_cannot_serve(
    db_session: AsyncSession,
) -> None:
    """The guard that ran before a session existed still runs when a passage is named."""
    from app.core.exceptions import ValidationError

    with pytest.raises(ValidationError):
        await room.create_session(db_session, pericope="P99")


@pytest.mark.asyncio
async def test_a_resolved_session_is_opened_in_progress_like_any_other(
    db_session: AsyncSession,
) -> None:
    team = await a_team(db_session, name="Estado")

    session = await room.create_session(db_session, project_id=team.id)

    assert session.status is IRSessionStatus.IN_PROGRESS
