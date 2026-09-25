# ruff: noqa: RUF001 — the expectations quote the map's own verse ranges, en dash included.
"""The Guide's coverage block is her three parts, in labels a Guide can say.

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
from app.services.internalization_room.coverage import (
    CoverageStatus,
    current_scene,
    initial_state,
    merge,
)
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


def test_the_scene_pointer_is_read_off_the_ledger_not_off_the_planner() -> None:
    """Scene 1 finished and scene 2 begun puts the team in scene 2, whatever was said."""
    nothing = initial_state(P)
    scene_one_done = _engaged(*_scene_keys(1))
    scene_two_begun = _engaged(*_scene_keys(1), "scene:2")
    every_scene = _engaged(*(key for n in (1, 2, 3, 4) for key in _scene_keys(n)))

    assert current_scene(nothing, P) is None, (
        "no turno zero o Guia lia CURRENT SCENE = Scene 1 antes de a equipe abrir a boca"
    )
    assert current_scene(scene_one_done, P) == "S2"
    assert current_scene(scene_two_begun, P) == "S2"
    assert current_scene(every_scene, P) is None, (
        "com toda cena engajada não há cena para apontar — é a integração da passagem"
    )


def test_a_bead_short_of_engaged_holds_the_pointer_on_its_scene() -> None:
    scene_one_echoed = {
        **_engaged(*_scene_keys(1)),
        next(key for key in _scene_keys(1) if key.startswith(ElementKind.ABSENCE)): (
            CoverageStatus.SURFACED.value
        ),
    }

    assert current_scene(scene_one_echoed, P) == "S1", (
        "a ausência só levantada pelo Guia deixava a cena 1 para trás como feita"
    )


#: Scene 1 of Ruth 1:1-5 worked to its last bead and scene 2 opened, as the map spells
#: each line (`canon/vendor/meaning-map/P01-Ruth-1-1-5.md`, §3) and the compilation log
#: numbers each rule — never read back through `elements_for`.
SCENE_ONE_DONE_SCENE_TWO_OPEN = """\
FIRST SCENE WHOSE BEADS ARE NOT ALL CLOSED: S2

COVERED (engaged): S1 (v.1–2); אֱלִימֶלֶך / Elimelech @ S1; נָעֳמִי / Naomi @ S1; \
מַחְלוֹן / Mahlon @ S1; כִלְיוֹן / Chilion @ S1; שֹּפְטִים / Judges @ S1; \
אֶפְרָתִים / Ephrathites @ S1; בֵּית לֶחֶם יְהוּדָה / Bethlehem of Judah @ S1; \
שְדֵי מוֹאָב / fields of Moab @ S1; הָאָרֶץ / the land @ S1; רָעָב / famine @ S1; \
לָגוּר / sojourning @ S1; יְמֵי שְׁפֹט הַשֹּׁפְטִים / days of the judges @ S1; absence @ S1; \
S2 (v.3)

REMAINING (not yet worked by the team, in their own words):
  arc: Level-1 arc
  context: Level-1 context
  tone: Level-1 tone
  function: Level-1 function
  scene: S3 (v.4), S4 (v.5)
  being: אֱלִימֶלֶך / Elimelech @ S2, נָעֳמִי / Naomi @ S2, מַחְלוֹן / Mahlon @ S2, \
כִלְיוֹן / Chilion @ S2, מַחְלוֹן / Mahlon @ S3, כִלְיוֹן / Chilion @ S3, \
נָשִׁים מוֹאֲבִיּוֹת / women of Moab @ S3, עָרְפָּה / Orpah @ S3, רוּת / Ruth @ S3, \
נָעֳמִי / Naomi @ S3, מַחְלוֹן / Mahlon @ S4, כִלְיוֹן / Chilion @ S4, \
הָאִשָּה (נָעֳמִי) / "the woman" (Naomi) @ S4
  place: שְדֵי מוֹאָב / fields of Moab (implied) @ S2, \
שָּם / there (fields of Moab, continued) @ S3, שְדֵי מוֹאָב / fields of Moab (implied) @ S4
  object: כְּעֶשֶר שָׁנִים / about ten years @ S3
  absence: absence @ S2, absence @ S3, absence @ S4
  preserved: R3, R5, R10"""


def test_the_block_is_her_three_parts_in_labels_the_guide_can_say() -> None:
    """Scene 2 is where the team is, scene 1 is behind them, and nothing is a key.

    A person the map names in four scenes is four beads, and the label says which: the
    team saying "Naomi" in scene 1 does not answer for her in scene 3, so COVERED and
    REMAINING never name the same thing.
    """
    state = _engaged(*_scene_keys(1), "scene:2")

    assert coverage_status_block(state, P) == SCENE_ONE_DONE_SCENE_TWO_OPEN, (
        "o Guia recebia só REMAINING, uma linha por elemento com a chave entre colchetes e o "
        "tipo de auditoria em caixa alta — sem cena atual e sem o que já foi feito, reabria "
        "cena pronta e podia ler 'preserved:R6' em voz alta"
    )


OPENING = (
    "FIRST SCENE WHOSE BEADS ARE NOT ALL CLOSED: none yet — no bead is closed; "
    "the whole passage is still open"
)
INTEGRATION = (
    "FIRST SCENE WHOSE BEADS ARE NOT ALL CLOSED: none — every scene's beads are closed; "
    "the whole-passage meaning remains"
)


def test_a_preserved_bead_carries_its_rule_id_and_is_labelled_by_it() -> None:
    """The id is read off the bead, never off the spelling of its key."""
    preserved = [e for e in elements_for(P) if e.kind is ElementKind.PRESERVED]

    assert [e.rule_id for e in preserved] == ["R3", "R5", "R10"]
    assert all(e.rule_id not in e.key.split(":")[0] for e in preserved)


def test_the_first_turn_is_the_whole_passage_opening_not_scene_one() -> None:
    nothing = initial_state(P)

    lines = coverage_status_block(nothing, P).splitlines()

    assert lines[0] == OPENING, "no turno um o bloco punha a equipe na cena 1"
    assert lines[2] == "COVERED (engaged): (nothing engaged yet — the session is just beginning)"


def test_every_scene_engaged_is_the_integration_with_the_axes_still_listed() -> None:
    every_scene = _engaged(*(key for n in (1, 2, 3, 4) for key in _scene_keys(n)))

    lines = coverage_status_block(every_scene, P).splitlines()

    assert lines[0] == INTEGRATION
    assert lines[4:] == [
        "REMAINING (not yet worked by the team, in their own words):",
        "  arc: Level-1 arc",
        "  context: Level-1 context",
        "  tone: Level-1 tone",
        "  function: Level-1 function",
        "  preserved: R3, R5, R10",
    ]


def test_a_finished_passage_is_the_integration_with_nothing_remaining() -> None:
    everything = _engaged(*(element.key for element in elements_for(P)))

    lines = coverage_status_block(everything, P).splitlines()

    assert lines[0] == INTEGRATION
    assert lines[4:] == ["REMAINING: (none — every element has been worked by the team)"]


@pytest.mark.parametrize(
    ("state", "scene_line"),
    [
        (initial_state(P), OPENING),
        (_engaged(*_scene_keys(1), "scene:2"), "FIRST SCENE WHOSE BEADS ARE NOT ALL CLOSED: S2"),
        (_engaged(*(key for n in (1, 2, 3, 4) for key in _scene_keys(n))), INTEGRATION),
    ],
    ids=["nothing closed", "a scene open", "every scene closed"],
)
def test_the_scene_line_says_what_it_computes_and_instructs_nothing(
    state: dict[str, str], scene_line: str
) -> None:
    """DOCTRINE §2.1: the ledger is information, never instruction (ADR 0035)."""
    first_line = coverage_status_block(state, P).splitlines()[0]

    assert first_line == scene_line


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
    assert composed[0] == OPENING
    assert composed[-1] == "  preserved: R3, R5, R10", (
        "o bloco COMPREHENSION EVIDENCE vinha colado embaixo do ledger, com READINESS e "
        "unidades semânticas que o Guia era mandado seguir"
    )
    assert not any(
        heading in guide.systems[0].partition(CACHE_BREAK)[2]
        for heading in ("COMPREHENSION EVIDENCE", "READINESS:", "PROBE", "BRIDGE MODE")
    )
