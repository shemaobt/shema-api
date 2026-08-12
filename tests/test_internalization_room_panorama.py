import json
import sys
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models.internalization_room import IRPromptKey, IRSessionStatus
from app.services.internalization_room._default_prompts import default_prompt
from app.services.internalization_room.canon.book_material import build_book_material
from app.services.internalization_room.coverage import counts
from app.services.internalization_room.run_turn import run_panorama_turn
from app.services.internalization_room.sessions import (
    book_of,
    create_session,
    is_panorama,
    resolve_pericope,
)

PANORAMA = default_prompt(IRPromptKey.BOOK_PANORAMA)["prompt"]
VALIDATOR = default_prompt(IRPromptKey.VALIDATOR)["prompt"]
OV = "OV-Ruth"


def _settings() -> Settings:
    return Settings(database_url="sqlite+aiosqlite:///./test.db", google_api_key="fake")


class FakeAgent:
    def __init__(self, verdict: dict[str, Any], draft: str = "Vamos conhecer o livro."):
        self.verdict = verdict
        self.draft = draft
        self.systems: list[str] = []

    async def __call__(self, *, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        self.systems.append(system_prompt)
        if "corrected_response" in system_prompt:
            return json.dumps(self.verdict)
        return self.draft


@pytest.fixture
def patch_agent(monkeypatch: pytest.MonkeyPatch):
    module = sys.modules["app.services.internalization_room.run_turn"]

    def _install(agent: FakeAgent) -> FakeAgent:
        monkeypatch.setattr(module, "call_agent", agent)
        return agent

    return _install


def test_a_book_id_is_recognised_as_a_panorama() -> None:
    assert is_panorama(OV)
    assert book_of(OV) == "Ruth"
    assert not is_panorama("P03")
    assert book_of("P03") == "Ruth"


def test_the_bare_alias_resolves_to_the_book_the_room_serves() -> None:
    """A client asks for `OV` and never learns which book it is — the canon stays here."""
    assert resolve_pericope("OV") == OV
    assert resolve_pericope("P03") == "P03"


@pytest.mark.asyncio
async def test_the_alias_opens_a_real_panorama_session(db_session: AsyncSession) -> None:
    session = await create_session(db_session, pericope="OV")

    assert session.pericope == OV
    assert is_panorama(session.pericope)


@pytest.mark.asyncio
async def test_a_panorama_session_has_no_coverage_spine(db_session: AsyncSession) -> None:
    """It prepares the team to enter the book; it asks no retelling and never completes."""
    session = await create_session(db_session, pericope=OV)

    assert session.coverage_state == {}
    assert counts(session.coverage_state) == {"engaged": 0, "surfaced": 0, "total": 0}
    assert session.status is IRSessionStatus.IN_PROGRESS


@pytest.mark.asyncio
async def test_the_panorama_is_grounded_on_the_book_material(patch_agent) -> None:
    agent = patch_agent(FakeAgent({"verdict": "pass", "issues": []}))
    material = build_book_material("Ruth")

    outcome = await run_panorama_turn(
        transcript="",
        messages=[],
        panorama_prompt=PANORAMA,
        validator_prompt=VALIDATOR,
        book="Ruth",
        book_material=material,
        opening=True,
        settings=_settings(),
    )

    assert outcome.speech == "Vamos conhecer o livro."
    speaker_system = agent.systems[0]
    assert "THE BOOK OF RUTH" in speaker_system
    assert "PRESERVATION NOTES" in speaker_system


@pytest.mark.asyncio
async def test_the_validator_judges_against_the_same_material(patch_agent) -> None:
    """Containment is enforced twice in a panorama too, with the book as the standard."""
    agent = patch_agent(FakeAgent({"verdict": "pass", "issues": []}))

    await run_panorama_turn(
        transcript="o que é esse livro?",
        messages=[],
        panorama_prompt=PANORAMA,
        validator_prompt=VALIDATOR,
        book="Ruth",
        book_material=build_book_material("Ruth"),
        settings=_settings(),
    )

    validator_system = agent.systems[1]
    assert "THE BOOK OF RUTH" in validator_system
    assert "{{" not in validator_system


@pytest.mark.asyncio
async def test_a_rejected_panorama_turn_is_never_voiced(patch_agent) -> None:
    patch_agent(
        FakeAgent(
            {"verdict": "regenerate", "issues": [{"problem": "imported_knowledge"}]},
            draft="Rute se casa com Boaz no fim.",
        )
    )

    outcome = await run_panorama_turn(
        transcript="como termina?",
        messages=[],
        panorama_prompt=PANORAMA,
        validator_prompt=VALIDATOR,
        book="Ruth",
        book_material=build_book_material("Ruth"),
        settings=_settings(),
    )

    assert outcome.used_fail_safe is True
    assert "Boaz" not in outcome.speech
