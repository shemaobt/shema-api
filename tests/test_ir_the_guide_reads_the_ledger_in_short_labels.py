# ruff: noqa: RUF001 — the expectations quote the map's own verse ranges, en dash included.
"""The Guide's coverage block is her three parts, in labels a Guide can say.

Every turn the Guide was handed a REMAINING list and nothing else — one line per element,
each carrying the internal key in brackets and the audit kind in capitals. It was never told
which scene the team was in, nor what they had already worked, so it guessed, reopened
finished scenes, and could read `preserved:R6` aloud into a room with no screen. DOCTRINE
§2.1: the app owns "the coverage ledger … All of it information; none of it instruction."
"""

import re

import pytest

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
from app.services.internalization_room.prompt_blocks import coverage_status_block

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
CURRENT SCENE: S2

COVERED (engaged): S1 (v.1–2); אֱלִימֶלֶך / Elimelech; נָעֳמִי / Naomi; מַחְלוֹן / Mahlon; \
כִלְיוֹן / Chilion; שֹּפְטִים / Judges; אֶפְרָתִים / Ephrathites; \
בֵּית לֶחֶם יְהוּדָה / Bethlehem of Judah; שְדֵי מוֹאָב / fields of Moab; הָאָרֶץ / the land; \
רָעָב / famine; לָגוּר / sojourning; יְמֵי שְׁפֹט הַשֹּׁפְטִים / days of the judges; absence @ S1; \
S2 (v.3)

REMAINING (not yet worked by the team, in their own words):
  arc: Level-1 arc
  context: Level-1 context
  tone: Level-1 tone
  function: Level-1 function
  scene: S3 (v.4), S4 (v.5)
  being: אֱלִימֶלֶך / Elimelech, נָעֳמִי / Naomi, מַחְלוֹן / Mahlon, כִלְיוֹן / Chilion, \
נָשִׁים מוֹאֲבִיּוֹת / women of Moab, עָרְפָּה / Orpah, רוּת / Ruth, \
הָאִשָּה (נָעֳמִי) / "the woman" (Naomi)
  place: שְדֵי מוֹאָב / fields of Moab (implied), שָּם / there (fields of Moab, continued)
  object: כְּעֶשֶר שָׁנִים / about ten years
  absence: absence @ S2, absence @ S3, absence @ S4
  preserved: R3, R5, R10"""


def test_the_block_is_her_three_parts_in_labels_the_guide_can_say() -> None:
    """Scene 2 is where the team is, scene 1 is behind them, and nothing is a key."""
    state = _engaged(*_scene_keys(1), "scene:2")

    assert coverage_status_block(state, P, current_scene(state, P)) == (
        SCENE_ONE_DONE_SCENE_TWO_OPEN
    ), (
        "o Guia recebia só REMAINING, uma linha por elemento com a chave entre colchetes e o "
        "tipo de auditoria em caixa alta — sem cena atual e sem o que já foi feito, reabria "
        "cena pronta e podia ler 'preserved:R6' em voz alta"
    )


OPENING = (
    "CURRENT SCENE: (whole-passage opening — help the team feel the shape before any one scene)"
)
INTEGRATION = (
    "CURRENT SCENE: (whole-passage integration — every scene has been engaged; check the "
    "remaining whole-passage meaning and the team's readiness)"
)


def test_the_first_turn_is_the_whole_passage_opening_not_scene_one() -> None:
    nothing = initial_state(P)

    lines = coverage_status_block(nothing, P, current_scene(nothing, P)).splitlines()

    assert lines[0] == OPENING, "no turno um o bloco punha a equipe na cena 1"
    assert lines[2] == "COVERED (engaged): (nothing engaged yet — the session is just beginning)"


def test_every_scene_engaged_is_the_integration_with_the_axes_still_listed() -> None:
    every_scene = _engaged(*(key for n in (1, 2, 3, 4) for key in _scene_keys(n)))

    lines = coverage_status_block(every_scene, P, current_scene(every_scene, P)).splitlines()

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

    lines = coverage_status_block(everything, P, current_scene(everything, P)).splitlines()

    assert lines[0] == INTEGRATION
    assert lines[4:] == ["REMAINING: (none — every element has been worked by the team)"]


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
    block = coverage_status_block(state, P, current_scene(state, P))

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
