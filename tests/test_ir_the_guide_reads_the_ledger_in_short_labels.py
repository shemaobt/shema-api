"""The Guide's coverage block is her ledger, in labels a Guide can say.

Every turn the Guide was handed a REMAINING list and nothing else — one line per element,
each carrying the internal key in brackets and the audit kind in capitals. It was never told
which scene the team was in, nor what they had already worked, so it guessed, reopened
finished scenes, and could read `preserved:R6` aloud into a room with no screen. DOCTRINE
§2.1: the app owns "the coverage ledger … All of it information; none of it instruction."
"""

import json
import re
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models.internalization_room import IRPromptKey
from app.services.internalization_room._default_prompts import default_prompt
from app.services.internalization_room.canon.elements import (
    ElementKind,
    element_keys,
    elements_for,
)
from app.services.internalization_room.coverage import initial_state, merge
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.live_turn import run_comprehension_turn
from app.services.internalization_room.llm import CACHE_BREAK
from app.services.internalization_room.prompt_blocks import coverage_status_block
from app.services.internalization_room.sessions import append_exchange, create_session
from tests.turn_harness import the_room_agent_is

P = "P01"


def _scene_keys(scene: int) -> list[str]:
    return [element.key for element in elements_for(P) if element.scene == scene]


def _engaged(*keys: str) -> dict[str, str]:
    return merge(initial_state(P), pericope_num=P, engaged=list(keys))


def test_a_preserved_bead_carries_its_rule_id_and_is_labelled_by_it() -> None:
    """The id is read off the bead, never off the spelling of its key."""
    preserved = [e for e in elements_for(P) if e.kind is ElementKind.PRESERVED]

    assert [e.rule_id for e in preserved] == ["R3", "R5", "R10"]
    assert all(e.rule_id not in e.key.split(":")[0] for e in preserved)


AUDIT_KIND = re.compile(r"\b[A-Z][A-Z]+_[A-Z_]+\b")


@pytest.mark.parametrize(
    "state",
    [
        initial_state(P),
        _engaged(*_scene_keys(1), "scene:2"),
        _engaged(
            *(element.key for element in elements_for(P) if element.kind is ElementKind.ABSENCE)
        ),
    ],
    ids=["nothing", "scene one done", "every silence taken up"],
)
def test_no_key_and_no_audit_kind_reaches_the_block(state: dict[str, str]) -> None:
    """`STRUCTURAL_ABSENCE_OF_DIVINE_AGENCY` and `preserved:R6` are things the team heard."""
    block = coverage_status_block(state, P)

    assert [key for key in element_keys(P) if f"[{key}]" in block] == [], (
        "a chave interna ia entre colchetes numa sala sem tela para conferi-la"
    )
    assert [key for key in element_keys(P) if ":" in key and key in block] == [], (
        "'preserved:R6' e 'being:S1:B3' são o que a equipe ouvia; só os quatro eixos têm uma "
        "chave que é a própria palavra do grupo"
    )
    assert AUDIT_KIND.findall(block) == [], (
        "o tipo de auditoria em caixa alta viajava dobrado no rótulo da ausência"
    )


class LedgerReadingGuide:
    """A Guide keeping every system it was handed, with a Validator passing behind it."""

    def __init__(self) -> None:
        self.systems: list[str] = []

    async def __call__(self, *, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        self.systems.append(system_prompt)
        return "A famine comes, and a family leaves Bethlehem. How would you tell that part?"


async def test_nothing_but_the_ledger_reaches_the_guide_from_the_app(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DOCTRINE §2.1: the app hands the Guide the ledger, "information; none of it instruction".

    Underneath the ledger the room used to paste its comprehension evidence — readiness,
    supported units, practice still needed — the app-owned state the bridge mode and the
    probe contract once rode in with. Everything past the cache break is what the app
    composes each turn; it is the ledger and nothing after it.
    """
    guide = LedgerReadingGuide()
    the_room_agent_is(monkeypatch, turn=guide)
    session = await create_session(db_session, language="en", pericope=P)
    session = await append_exchange(
        db_session, session, team_utterance="", guide_response="opening"
    )

    await run_comprehension_turn(
        db_session,
        session,
        speech=HeardSpeech(text="we can start"),
        opening=False,
        guide_prompt=default_prompt(IRPromptKey.GUIDE)["prompt"],
        validator_prompt=default_prompt(IRPromptKey.VALIDATOR)["prompt"],
        settings=Settings(database_url="sqlite+aiosqlite:///./test.db", google_api_key="fake"),
    )

    composed = guide.systems[0].partition(CACHE_BREAK)[2].strip().splitlines()
    assert composed[:2] == [
        "LEDGER (the app's notes — information only; you decide what comes next)",
        "",
    ], "a linha de cena, que o ledger dela não manda, entrava logo abaixo do cabeçalho"
    assert composed[-1] == "  preserved_element: R3, R5, R10", (
        "o bloco COMPREHENSION EVIDENCE vinha colado embaixo do ledger, com READINESS e "
        "unidades semânticas que o Guia era mandado seguir"
    )
    assert not any(
        heading in guide.systems[0].partition(CACHE_BREAK)[2]
        for heading in ("COMPREHENSION EVIDENCE", "READINESS:", "PROBE", "BRIDGE MODE")
    )
