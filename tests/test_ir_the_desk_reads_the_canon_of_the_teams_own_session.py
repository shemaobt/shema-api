"""ENG-1510 — the Desk's team views read the canon of the session the team works in.

ENG-1219 made a session keep the canon it opened with, and the Desk's card of a session already
reads it that way. The views drawn per team still read the canon the room serves now, so after a
re-pin a team whose session kept the older map was shown the new one. Each case here has two
teams on one passage: one opened before the re-pin, one after, read in the same request order.
"""

from __future__ import annotations

import itertools
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ProjectRole
from app.db.models.internalization_room import IRQuestion, IRQuestionStatus
from app.services.internalization_room.coverage import CoverageStatus
from app.services.internalization_room.sessions import apply_coverage
from tests.baker import (
    grant_facilitator_app_role,
    make_language,
    make_project,
    make_project_user_access,
    make_user,
    open_ir_session,
)
from tests.canon_harness import the_canon_moves_on
from tests.opening_harness import desk_routes

NEW_PIN = "a" * 40
P = "P03"
FIRST_SCENE_HEADING = "### Scene 1 —"
SECOND_SCENE_HEADING = "### Scene 2 —"
RUTH_IN_THE_SECOND_SCENE = "being:S2:B9"
KEPT_RUTH_LABEL = "Ruth, as the kept catalogue names her"

FIRST = "P01"
SERVED_FIRST_REFERENCE = "Ruth 1:1\u20135"
KEPT_FIRST_REFERENCE = f"{SERVED_FIRST_REFERENCE}, as the kept map titles it"

_codes = itertools.count()


def _the_kept_map_has_no_first_scene(tree: Path, pericope: str) -> None:
    (page,) = (tree / "vendor" / "meaning-map").glob(f"{pericope}-*.md")
    told = page.read_text(encoding="utf-8")
    first = told.index(FIRST_SCENE_HEADING)
    page.write_text(told[:first] + told[told.index(SECOND_SCENE_HEADING) :], encoding="utf-8")


def _the_kept_p03_has_its_own_beads_and_labels(tree: Path) -> None:
    _the_kept_map_has_no_first_scene(tree, P)
    catalogue = tree / "element-labels" / "ruth.json"
    labels = json.loads(catalogue.read_text(encoding="utf-8"))
    labels[P] = {
        key: named for key, named in labels[P].items() if not (key.endswith(":S1") or ":S1:" in key)
    }
    labels[P][RUTH_IN_THE_SECOND_SCENE] = {"en": KEPT_RUTH_LABEL, "pt": None}
    catalogue.write_text(json.dumps(labels, ensure_ascii=False), encoding="utf-8")


def _the_kept_p01_is_titled_its_own_way(tree: Path) -> None:
    (page,) = (tree / "vendor" / "meaning-map").glob(f"{FIRST}-*.md")
    told = page.read_text(encoding="utf-8")
    page.write_text(
        told.replace(
            f"# {FIRST} — {SERVED_FIRST_REFERENCE}\n", f"# {FIRST} — {KEPT_FIRST_REFERENCE}\n"
        ),
        encoding="utf-8",
    )


def _the_kept_p01_has_no_first_scene(tree: Path) -> None:
    _the_kept_map_has_no_first_scene(tree, FIRST)


async def _worked_the_second_scene_then_the_first(db: AsyncSession, session_id: str) -> None:
    for scene in ("scene:S2", "scene:S1"):
        await apply_coverage(db, session_id, {scene: CoverageStatus.ENGAGED.value})


async def _a_desk_over_two_teams(db: AsyncSession):
    user = await make_user(db, email="mesa@example.com")
    await grant_facilitator_app_role(db, user.id)
    teams = []
    for name in ("antes", "depois"):
        language = await make_language(db, name=f"Lingua {name}", code=f"k{next(_codes):02d}")
        team = await make_project(db, language.id, name=f"Equipe {name}")
        await make_project_user_access(db, team.id, user.id, role=ProjectRole.FACILITATOR)
        teams.append(team)
    from app.services.auth.issue_tokens import issue_tokens

    access, _refresh = await issue_tokens(db, user)
    return {"Authorization": f"Bearer {access}"}, teams


async def test_a_team_whose_session_kept_the_old_canon_is_shown_that_canons_necklace(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    desk, (kept_team, fresh_team) = await _a_desk_over_two_teams(db_session)
    await open_ir_session(db_session, pericope=P, project_id=kept_team.id)
    the_canon_moves_on(
        monkeypatch, tmp_path, NEW_PIN, keeping=_the_kept_p03_has_its_own_beads_and_labels
    )
    await open_ir_session(db_session, pericope=P, project_id=fresh_team.id)

    async with desk_routes(db_session) as at_desk:
        fresh = await at_desk.get(
            f"/api/facilitator/teams/{fresh_team.id}/coverage", params={"pericope": P}, headers=desk
        )
        kept = await at_desk.get(
            f"/api/facilitator/teams/{kept_team.id}/coverage", params={"pericope": P}, headers=desk
        )

    assert kept.status_code == 200 and fresh.status_code == 200, kept.text[:300]
    kept_beads = {bead["key"]: bead["label_en"] for bead in kept.json()}
    fresh_beads = {bead["key"]: bead["label_en"] for bead in fresh.json()}
    assert "scene:S1" not in kept_beads, "a Mesa desenhou o colar da equipe pelo canon novo"
    assert kept_beads[RUTH_IN_THE_SECOND_SCENE] == KEPT_RUTH_LABEL
    assert "scene:S1" in fresh_beads, "a equipe aberta depois da troca deixou de ler o canon novo"
    assert fresh_beads[RUTH_IN_THE_SECOND_SCENE] == "Ruth"


async def test_a_team_whose_session_kept_the_old_canon_is_shown_that_canons_reference(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    desk, (kept_team, fresh_team) = await _a_desk_over_two_teams(db_session)
    await open_ir_session(db_session, pericope=FIRST, project_id=kept_team.id)
    the_canon_moves_on(monkeypatch, tmp_path, NEW_PIN, keeping=_the_kept_p01_is_titled_its_own_way)
    await open_ir_session(db_session, pericope=FIRST, project_id=fresh_team.id)

    async with desk_routes(db_session) as at_desk:
        fresh = await at_desk.get(f"/api/facilitator/teams/{fresh_team.id}", headers=desk)
        kept = await at_desk.get(f"/api/facilitator/teams/{kept_team.id}", headers=desk)

    assert kept.status_code == 200 and fresh.status_code == 200, kept.text[:300]
    assert kept.json()["active_passage"] == {
        "pericope": FIRST,
        "reference": KEPT_FIRST_REFERENCE,
    }, "a página da equipe nomeou a passagem pelo canon novo"
    assert fresh.json()["active_passage"]["reference"] == SERVED_FIRST_REFERENCE


async def test_a_team_whose_session_kept_the_old_canon_is_placed_in_that_canons_scene(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    desk, (kept_team, fresh_team) = await _a_desk_over_two_teams(db_session)
    kept_session = await open_ir_session(db_session, pericope=FIRST, project_id=kept_team.id)
    await _worked_the_second_scene_then_the_first(db_session, kept_session.id)
    the_canon_moves_on(monkeypatch, tmp_path, NEW_PIN, keeping=_the_kept_p01_has_no_first_scene)
    fresh_session = await open_ir_session(db_session, pericope=FIRST, project_id=fresh_team.id)
    await _worked_the_second_scene_then_the_first(db_session, fresh_session.id)

    async with desk_routes(db_session) as at_desk:
        fresh = await at_desk.get(f"/api/facilitator/teams/{fresh_team.id}", headers=desk)
        kept = await at_desk.get(f"/api/facilitator/teams/{kept_team.id}", headers=desk)

    assert kept.status_code == 200 and fresh.status_code == 200, kept.text[:300]
    assert kept.json()["scene_the_team_is_in"] == "scene:S2", (
        "a página da equipe pôs a equipe numa cena que o canon dela não tem"
    )
    assert fresh.json()["scene_the_team_is_in"] == "scene:S1"


async def test_the_team_list_names_each_teams_passage_by_the_canon_its_own_session_kept(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    desk, (kept_team, fresh_team) = await _a_desk_over_two_teams(db_session)
    await open_ir_session(db_session, pericope=FIRST, project_id=kept_team.id)
    the_canon_moves_on(monkeypatch, tmp_path, NEW_PIN, keeping=_the_kept_p01_is_titled_its_own_way)
    await open_ir_session(db_session, pericope=FIRST, project_id=fresh_team.id)

    async with desk_routes(db_session) as at_desk:
        listed = await at_desk.get("/api/facilitator/teams", headers=desk)

    assert listed.status_code == 200, listed.text[:300]
    references = {
        team["team_id"]: team["active_passage"]["reference"] for team in listed.json()["teams"]
    }
    assert references == {
        kept_team.id: KEPT_FIRST_REFERENCE,
        fresh_team.id: SERVED_FIRST_REFERENCE,
    }, "a lista de equipes nomeou a passagem de uma equipe pelo canon de outra"


async def _a_hand_raised_on_ruth(db: AsyncSession, team_id: str, session_id: str) -> str:
    question = IRQuestion(
        device_id="aparelho",
        session_id=session_id,
        pericope=P,
        element_key=RUTH_IN_THE_SECOND_SCENE,
        audio_key="pergunta.m4a",
        status=IRQuestionStatus.OPEN,
        project_id=team_id,
        created_at=datetime.now(UTC),
    )
    db.add(question)
    await db.commit()
    return question.id


async def test_a_hand_raised_in_a_session_that_kept_the_old_canon_names_its_bead_by_that_canon(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from fastapi import FastAPI

    from app.api.internalization_room.questions import router as questions_router
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    desk, (kept_team, fresh_team) = await _a_desk_over_two_teams(db_session)
    kept_session = await open_ir_session(db_session, pericope=P, project_id=kept_team.id)
    the_canon_moves_on(
        monkeypatch, tmp_path, NEW_PIN, keeping=_the_kept_p03_has_its_own_beads_and_labels
    )
    fresh_session = await open_ir_session(db_session, pericope=P, project_id=fresh_team.id)
    kept_hand = await _a_hand_raised_on_ruth(db_session, kept_team.id, kept_session.id)
    fresh_hand = await _a_hand_raised_on_ruth(db_session, fresh_team.id, fresh_session.id)

    inbox = FastAPI()
    inbox.include_router(questions_router, prefix="/api/internalization-room")
    register_exception_handlers(inbox)

    async def _get_db():
        yield db_session

    inbox.dependency_overrides[get_db] = _get_db
    async with httpx.AsyncClient(
        transport=ASGITransport(app=inbox), base_url="http://test"
    ) as at_desk:
        page = await at_desk.get("/api/internalization-room/facilitator/questions", headers=desk)

    assert page.status_code == 200, page.text[:300]
    labels = {card["question_id"]: card["element_label_en"] for card in page.json()["questions"]}
    assert labels == {kept_hand: KEPT_RUTH_LABEL, fresh_hand: "Ruth"}, (
        "a caixa de perguntas nomeou a conta pelo canon de outra sessão"
    )
