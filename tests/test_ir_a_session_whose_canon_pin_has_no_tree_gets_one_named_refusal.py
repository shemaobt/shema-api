"""ENG-1588 — a session whose canon pin has no tree is refused by name, the same way everywhere.

The canon sync drops the kept trees, so a session opened before a re-pin can find no tree for
its pin once the next deploy lands. Each reader used to fail its own way: a 400 that blamed
the caller for a passage the canon has, a 500, or a silent read of nothing.
"""

from __future__ import annotations

import shutil
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room.questions import router as questions_router
from app.core.database import get_db
from app.core.enums import ProjectRole
from app.core.exceptions import CanonNotKept, register_exception_handlers
from app.db.models.internalization_room import IRQuestion, IRQuestionStatus
from app.db.models.project import Project
from app.services.auth.issue_tokens import issue_tokens
from app.services.internalization_room.canon import kept
from app.services.internalization_room.canon.book_material import (
    preservation_rules,
    significant_absences,
    vendor_pin,
)
from app.services.internalization_room.canon.labels import labelled_elements
from app.services.internalization_room.canon.names import registry_entry, verse_ranges
from app.services.internalization_room.canon.parse_map import load_book, load_map
from app.services.internalization_room.canon.titles import scene_title
from app.services.internalization_room.coverage import CoverageStatus
from app.services.internalization_room.sessions import apply_coverage, create_session
from tests.baker import (
    grant_facilitator_app_role,
    make_language,
    make_project,
    make_project_user_access,
    make_user,
    open_ir_session,
)
from tests.canon_harness import forget_the_canon, the_canon_moves_on
from tests.device_harness import TABLET_TEAM
from tests.opening_harness import desk_routes, desk_sessions_routes
from tests.release_harness import PREFIX
from tests.room_harness import room_client

NEW_PIN = "a" * 40
GONE_PIN = "b" * 40
P = "P01"
NAOMI_IN_THE_FIRST_SCENE = "being:S1:B3"


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    async with room_client(db_session, monkeypatch) as door:
        yield door


@pytest.fixture()
def a_pin_with_no_tree(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> str:
    monkeypatch.setattr(kept, "KEPT_DIR", tmp_path / "kept")
    forget_the_canon()
    return GONE_PIN


async def test_a_session_whose_pin_lost_its_tree_is_refused_by_its_pin_not_as_a_bad_request(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    session = await open_ir_session(db_session, pericope=P, project_id=TABLET_TEAM)
    tree = the_canon_moves_on(monkeypatch, tmp_path, NEW_PIN)
    shutil.rmtree(tree)

    read = await client.get(f"{PREFIX}/sessions/{session.id}")

    assert read.status_code == 409, read.text[:300]
    assert read.json()["code"] == "CANON_NOT_KEPT", (
        "a sessão sem árvore respondia 400 «no vendored Meaning Map», culpando o pedido"
    )
    assert session.canon_pin in read.json()["detail"]


@pytest.mark.parametrize(
    "read",
    [
        lambda: load_map(P),
        lambda: load_book("Ruth"),
        lambda: registry_entry("Ruth", "B1"),
        lambda: verse_ranges(P),
        lambda: significant_absences(P),
        lambda: labelled_elements(P),
    ],
    ids=["map", "book", "names", "coordinates", "absences", "labels"],
)
def test_every_reader_of_a_pin_with_no_tree_refuses_by_naming_that_pin(
    read: Callable[[], Any], a_pin_with_no_tree: str
) -> None:
    with kept.reading_the_canon_of(a_pin_with_no_tree), pytest.raises(CanonNotKept) as refused:
        read()

    assert a_pin_with_no_tree in str(refused.value), (
        "cada leitor falhava do seu jeito: 400, FileNotFoundError ou StopIteration, sem o pin"
    )


@pytest.mark.parametrize(
    "read",
    [
        lambda: preservation_rules("Ruth"),
        lambda: vendor_pin(),
        lambda: scene_title(P, 1, "The family leaves Bethlehem", "pt"),
    ],
    ids=["rules", "pin", "portuguese-title"],
)
def test_a_pin_with_no_tree_is_refused_never_read_as_no_rules_or_an_english_title(
    read: Callable[[], Any], a_pin_with_no_tree: str
) -> None:
    with kept.reading_the_canon_of(a_pin_with_no_tree), pytest.raises(CanonNotKept) as refused:
        read()

    assert a_pin_with_no_tree in str(refused.value), (
        "sem árvore, as regras liam vazio, o pin virava «unpinned» e a cena voltava ao inglês"
    )


async def _a_desk_over_two_teams(db: AsyncSession) -> tuple[dict[str, str], list[Project]]:
    user = await make_user(db, email="mesa@example.com")
    await grant_facilitator_app_role(db, user.id)
    teams = []
    for name, code in (("antes", "q01"), ("depois", "q02")):
        language = await make_language(db, name=f"Lingua {name}", code=code)
        team = await make_project(db, language.id, name=f"Equipe {name}")
        await make_project_user_access(db, team.id, user.id, role=ProjectRole.FACILITATOR)
        teams.append(team)
    access, _refresh = await issue_tokens(db, user)
    return {"Authorization": f"Bearer {access}"}, teams


async def test_the_desk_necklace_of_a_team_whose_pin_lost_its_tree_is_refused_by_it_not_unknown(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    desk, (gone_team, _) = await _a_desk_over_two_teams(db_session)
    session = await open_ir_session(db_session, pericope=P, project_id=gone_team.id)
    shutil.rmtree(the_canon_moves_on(monkeypatch, tmp_path, NEW_PIN))

    async with desk_routes(db_session) as at_desk:
        necklace = await at_desk.get(
            f"/api/facilitator/teams/{gone_team.id}/coverage", params={"pericope": P}, headers=desk
        )

    assert necklace.status_code == 409, necklace.text[:300]
    assert necklace.json()["code"] == "CANON_NOT_KEPT", (
        "a Mesa ouvia 404, como se a passagem nunca tivesse existido no canon"
    )
    assert session.canon_pin in necklace.json()["detail"]


async def test_the_page_of_a_team_whose_pin_lost_its_tree_is_drawn_without_what_its_canon_named(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    desk, (gone_team, _) = await _a_desk_over_two_teams(db_session)
    session = await open_ir_session(db_session, pericope=P, project_id=gone_team.id)
    await apply_coverage(db_session, session.id, {"scene:S1": CoverageStatus.ENGAGED.value})
    shutil.rmtree(the_canon_moves_on(monkeypatch, tmp_path, NEW_PIN))

    async with desk_routes(db_session) as at_desk:
        page = await at_desk.get(f"/api/facilitator/teams/{gone_team.id}", headers=desk)

    assert page.status_code == 200, page.text[:300]
    team = page.json()
    assert team["active_passage"] == {"pericope": P, "reference": None}, (
        "a página da equipe sem árvore respondia 409 inteira, até o nome e as mãos levantadas"
    )
    assert team["scene_the_team_is_in"] is None
    assert team["name"] == "Equipe antes"


async def test_the_team_list_names_every_other_teams_passage_when_one_teams_pin_lost_its_tree(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    desk, (gone_team, fresh_team) = await _a_desk_over_two_teams(db_session)
    await open_ir_session(db_session, pericope=P, project_id=gone_team.id)
    shutil.rmtree(the_canon_moves_on(monkeypatch, tmp_path, NEW_PIN))
    await open_ir_session(db_session, pericope=P, project_id=fresh_team.id)

    async with desk_routes(db_session) as at_desk:
        listed = await at_desk.get("/api/facilitator/teams", headers=desk)

    assert listed.status_code == 200, listed.text[:300]
    passages = {team["team_id"]: team["active_passage"] for team in listed.json()["teams"]}
    assert passages == {
        gone_team.id: {"pericope": P, "reference": None},
        fresh_team.id: {"pericope": P, "reference": "Ruth 1:1\u20135"},
    }, "uma equipe sem árvore derrubava a lista de equipes inteira, as outras junto"


async def test_a_team_whose_pin_lost_its_tree_is_still_found_by_its_passage_in_a_search(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    desk, (gone_team, fresh_team) = await _a_desk_over_two_teams(db_session)
    await open_ir_session(db_session, pericope=P, project_id=gone_team.id)
    shutil.rmtree(the_canon_moves_on(monkeypatch, tmp_path, NEW_PIN))
    await open_ir_session(db_session, pericope=P, project_id=fresh_team.id)

    async with desk_routes(db_session) as at_desk:
        found = await at_desk.get("/api/facilitator/teams", params={"search": P}, headers=desk)

    assert found.status_code == 200, found.text[:300]
    assert {team["team_id"] for team in found.json()["teams"]} == {gone_team.id, fresh_team.id}, (
        "a busca lia a referência da passagem e quebrava na equipe que não tinha uma"
    )


async def _an_entered_session_before_and_after_the_tree_is_dropped(
    db: AsyncSession, team_id: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> tuple[str, str]:
    gone = await open_ir_session(db, pericope=P, project_id=team_id)
    gone.messages = [{"role": "team", "text": "a família saiu de Belém"}]
    gone.created_at = datetime.now(UTC) - timedelta(days=1)
    await db.commit()
    shutil.rmtree(the_canon_moves_on(monkeypatch, tmp_path, NEW_PIN))
    fresh = await create_session(db, pericope=P, project_id=team_id, language="pt")
    fresh.messages = [{"role": "team", "text": "Noemi voltou com Rute"}]
    await db.commit()
    return gone.id, fresh.id


async def test_a_teams_history_draws_every_other_conversation_when_one_lost_its_tree(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    desk, (team, _) = await _a_desk_over_two_teams(db_session)
    gone, fresh = await _an_entered_session_before_and_after_the_tree_is_dropped(
        db_session, team.id, monkeypatch, tmp_path
    )

    async with desk_routes(db_session) as at_desk:
        history = await at_desk.get(f"/api/facilitator/teams/{team.id}/sessions", headers=desk)

    assert history.status_code == 200, history.text[:300]
    cards = {card["session_id"]: card["coverage"] for card in history.json()}
    assert set(cards) == {gone, fresh}
    assert cards[gone] is None, (
        "a conversa sem árvore desenhava um colar vazio, como se nada tivesse sido alcançado"
    )
    labels = {bead["key"]: bead["label_en"] for bead in cards[fresh]}
    assert labels[NAOMI_IN_THE_FIRST_SCENE] == "Naomi", (
        "uma conversa sem árvore derrubava o histórico inteiro da equipe"
    )


async def test_the_desk_sessions_page_lists_every_other_session_when_one_lost_its_tree(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    desk, (team, _) = await _a_desk_over_two_teams(db_session)
    gone, fresh = await _an_entered_session_before_and_after_the_tree_is_dropped(
        db_session, team.id, monkeypatch, tmp_path
    )

    async with desk_sessions_routes(db_session) as at_desk:
        page = await at_desk.get("/api/facilitator/sessions", headers=desk)

    assert page.status_code == 200, page.text[:300]
    counts = {
        row["session_id"]: (row["engaged_elements"], row["total_elements"])
        for row in page.json()["sessions"]
    }
    assert counts == {gone: (None, None), fresh: (0, 47)}, (
        "uma sessão sem árvore derrubava a página de sessões da Mesa inteira"
    )


async def _a_hand_raised_on_naomi(db: AsyncSession, team_id: str, session_id: str) -> str:
    question = IRQuestion(
        device_id="aparelho",
        session_id=session_id,
        pericope=P,
        element_key=NAOMI_IN_THE_FIRST_SCENE,
        audio_key="pergunta.m4a",
        status=IRQuestionStatus.OPEN,
        project_id=team_id,
        created_at=datetime.now(UTC),
    )
    db.add(question)
    await db.commit()
    return question.id


async def test_the_inbox_still_names_every_other_sessions_hands_when_one_pin_lost_its_tree(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    desk, (gone_team, fresh_team) = await _a_desk_over_two_teams(db_session)
    gone_session = await open_ir_session(db_session, pericope=P, project_id=gone_team.id)
    shutil.rmtree(the_canon_moves_on(monkeypatch, tmp_path, NEW_PIN))
    fresh_session = await open_ir_session(db_session, pericope=P, project_id=fresh_team.id)
    gone_hand = await _a_hand_raised_on_naomi(db_session, gone_team.id, gone_session.id)
    fresh_hand = await _a_hand_raised_on_naomi(db_session, fresh_team.id, fresh_session.id)

    inbox = FastAPI()
    inbox.include_router(questions_router, prefix=PREFIX)
    register_exception_handlers(inbox)

    async def _get_db():
        yield db_session

    inbox.dependency_overrides[get_db] = _get_db
    async with httpx.AsyncClient(
        transport=ASGITransport(app=inbox), base_url="http://test"
    ) as at_desk:
        page = await at_desk.get(f"{PREFIX}/facilitator/questions", headers=desk)

    assert page.status_code == 200, page.text[:300]
    labels = {
        card["question_id"]: (card["element_label_en"], card["element_label_pt"])
        for card in page.json()["questions"]
    }
    assert labels == {gone_hand: (None, None), fresh_hand: ("Naomi", "Noemi")}, (
        "uma sessão sem árvore derrubava a caixa de perguntas inteira, as outras equipes junto"
    )
