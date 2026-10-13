"""ENG-1510 — the Desk's team views read the canon of the session the team works in.

ENG-1219 made a session keep the canon it opened with, and the Desk's card of a session already
reads it that way. The views drawn per team still read the canon the room serves now, so after a
re-pin a team whose session kept the older map was shown the new one. Each case here has two
teams on one passage: one opened before the re-pin, one after, read in the same request order.
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ProjectRole
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
