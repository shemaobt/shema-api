# ruff: noqa: RUF001 — the expectations quote the map's own verse ranges, en dash included.
"""The Guide's coverage block is her LEDGER, line for line.

The block we sent was our own: a scene line she never renders in her live room, COVERED,
and a REMAINING list that lumped what the Guide had raised with what nobody had touched,
so the Guide never saw which of its own openings the team had not taken up.
`renderCoverageStatus` (`Tripod-Internalization`, `src/turn/coverageStatus.ts:18-56`,
byte-identical at 533b6e3, 17ba6fc and a3f3c69) is the structure ported here; the labels
stay our canon's.
"""

from pathlib import Path

from app.db.models.internalization_room import IRPromptKey, IRSession
from app.services.internalization_room._default_prompts import default_prompt
from app.services.internalization_room.coverage import initial_state
from app.services.internalization_room.prompt_blocks import coverage_status_block
from app.services.internalization_room.sessions import session_is_done

P = "P01"

#: Her tracker after its second turn (`src/coverage/coverageTest.ts:40-68`) laid over
#: Ruth 1:1-5: Naomi, Elimelech, the fields of Moab, the famine and scene 1 taken up by the
#: team, Orpah named only by the Guide, and "the woman" of scene 4 not reached.
HER_SECOND_TURN = {
    **initial_state(P),
    "being:S1:B3": "engaged",
    "being:S1:B2": "engaged",
    "place:S1:PL2": "engaged",
    "object:S1:O1": "engaged",
    "scene:1": "engaged",
    "being:S3:B8": "surfaced",
}

#: Worked by hand from `coverageStatus.ts:41-56` with the map's labels
#: (`canon/vendor/meaning-map/P01-Ruth-1-1-5.md`) — never rendered and pasted back.
HER_SECOND_TURN_LEDGER = """\
LEDGER (the app's notes — information only; you decide what comes next)

WORKED WITH BY THE TEAM (engaged): S1 (v.1–2); אֱלִימֶלֶך / Elimelech; נָעֳמִי / Naomi; \
שְדֵי מוֹאָב / fields of Moab; רָעָב / famine

RAISED BY YOU, NOT YET TAKEN UP BY THE TEAM:
  being: עָרְפָּה / Orpah

NOT YET TOUCHED (still deserve a visit before the session ends):
  arc: Level-1 arc
  context: Level-1 context
  tone: Level-1 tone
  function: Level-1 function
  scene: S2 (v.3), S3 (v.4), S4 (v.5)
  being: מַחְלוֹן / Mahlon, כִלְיוֹן / Chilion, שֹּפְטִים / Judges, אֶפְרָתִים / Ephrathites, \
אֱלִימֶלֶך / Elimelech, נָעֳמִי / Naomi, נָשִׁים מוֹאֲבִיּוֹת / women of Moab, רוּת / Ruth, \
הָאִשָּה (נָעֳמִי) / "the woman" (Naomi)
  place: בֵּית לֶחֶם יְהוּדָה / Bethlehem of Judah, הָאָרֶץ / the land, \
שְדֵי מוֹאָב / fields of Moab (implied), שָּם / there (fields of Moab, continued)
  object: לָגוּר / sojourning, כְּעֶשֶר שָׁנִים / about ten years
  time: יְמֵי שְׁפֹט הַשֹּׁפְטִים / days of the judges
  significant_absence: absence @ S1, absence @ S2, absence @ S3, absence @ S4
  preserved_element: R3, R5, R10"""


def test_the_guide_reads_her_ledger_with_what_it_raised_apart_from_what_nobody_touched() -> None:
    """Naomi is worked in scene 1 and still owed in scenes 2 and 3, and says so once each."""
    assert coverage_status_block(HER_SECOND_TURN, P) == HER_SECOND_TURN_LEDGER, (
        "o Guia lia COVERED e um REMAINING que juntava o que ele mesmo levantou com o que "
        "ninguém tocou, sob uma linha de cena que o ledger dela não manda"
    )


#: Every bead of Ruth 1:1-5 taken up by the team except Orpah, whom only the Guide named.
ALL_BUT_ORPAH = {**dict.fromkeys(initial_state(P), "engaged"), "being:S3:B8": "surfaced"}

ALL_BUT_ORPAH_LEDGER = """\
LEDGER (the app's notes — information only; you decide what comes next)

WORKED WITH BY THE TEAM (engaged): Level-1 arc; Level-1 context; Level-1 tone; \
Level-1 function; S1 (v.1–2); אֱלִימֶלֶך / Elimelech; נָעֳמִי / Naomi; מַחְלוֹן / Mahlon; \
כִלְיוֹן / Chilion; שֹּפְטִים / Judges; אֶפְרָתִים / Ephrathites; \
בֵּית לֶחֶם יְהוּדָה / Bethlehem of Judah; שְדֵי מוֹאָב / fields of Moab; הָאָרֶץ / the land; \
רָעָב / famine; לָגוּר / sojourning; יְמֵי שְׁפֹט הַשֹּׁפְטִים / days of the judges; absence @ S1; \
S2 (v.3); שְדֵי מוֹאָב / fields of Moab (implied); absence @ S2; S3 (v.4); \
נָשִׁים מוֹאֲבִיּוֹת / women of Moab; רוּת / Ruth; שָּם / there (fields of Moab, continued); \
כְּעֶשֶר שָׁנִים / about ten years; absence @ S3; S4 (v.5); \
הָאִשָּה (נָעֳמִי) / "the woman" (Naomi); absence @ S4; R3; R5; R10

RAISED BY YOU, NOT YET TAKEN UP BY THE TEAM:
  being: עָרְפָּה / Orpah

NOT YET TOUCHED (still deserve a visit before the session ends):
  (nothing — everything in the map has been visited)"""


def test_a_bead_the_guide_raised_is_still_owed_when_nothing_is_left_untouched() -> None:
    """Her design, accepted: NOT YET TOUCHED reads empty while the floor is not met."""
    session = IRSession(pericope=P, coverage_state=ALL_BUT_ORPAH)

    assert coverage_status_block(ALL_BUT_ORPAH, P) == ALL_BUT_ORPAH_LEDGER, (
        "Orpah, só nomeada pelo Guia, sumia num REMAINING que não dizia quem a levantou"
    )
    assert session_is_done(session) is False, (
        "um bead só levantado pelo Guia não fecha o piso, mesmo com nada por tocar"
    )


def test_a_session_with_nothing_worked_says_it_is_just_beginning_and_raises_nothing() -> None:
    lines = coverage_status_block(initial_state(P), P).splitlines()

    assert lines[:6] == [
        "LEDGER (the app's notes — information only; you decide what comes next)",
        "",
        "WORKED WITH BY THE TEAM (engaged): (nothing yet — the session is just beginning)",
        "",
        "NOT YET TOUCHED (still deserve a visit before the session ends):",
        "  arc: Level-1 arc",
    ], "o turno zero dizia COVERED com o texto vazio nosso, abaixo de uma linha de cena"


def test_a_bead_still_at_the_retired_partially_engaged_is_one_the_guide_raised() -> None:
    """Her ledger has no such status; the floor already holds it like `surfaced`."""
    retired = {**HER_SECOND_TURN, "being:S3:B8": "partially_engaged"}

    assert coverage_status_block(retired, P) == HER_SECOND_TURN_LEDGER, (
        "o status aposentado não caía em seção nenhuma do ledger dela"
    )


def test_a_status_the_ledger_does_not_know_is_a_bead_not_yet_touched() -> None:
    unknown = {**HER_SECOND_TURN, "being:S3:B8": "half_heard"}

    lines = coverage_status_block(unknown, P).splitlines()

    assert "RAISED BY YOU, NOT YET TAKEN UP BY THE TEAM:" not in lines
    assert (
        "  being: מַחְלוֹן / Mahlon, כִלְיוֹן / Chilion, שֹּפְטִים / Judges, "
        "אֶפְרָתִים / Ephrathites, אֱלִימֶלֶך / Elimelech, נָעֳמִי / Naomi, "
        "נָשִׁים מוֹאֲבִיּוֹת / women of Moab, עָרְפָּה / Orpah, רוּת / Ruth, "
        'הָאִשָּה (נָעֳמִי) / "the woman" (Naomi)'
    ) in lines, "um status desconhecido sumia do bloco em vez de contar como não tocado"


def test_her_scene_line_is_rendered_only_for_a_scene_someone_hands_it() -> None:
    """Her live room never sets `currentScene`, and no caller here passes one."""
    lines = coverage_status_block(initial_state(P), P, current_scene="S1").splitlines()

    assert lines[:3] == [
        "LEDGER (the app's notes — information only; you decide what comes next)",
        "SCENE THE LEDGER LAST SAW THE TEAM IN: S1",
        "",
    ]


HER_GUIDE = (
    Path(__file__).resolve().parents[1]
    / "app/services/internalization_room/prompts/vendor/guide_system_prompt.md"
)


def _coverage_section(prompt: str) -> str:
    start = prompt.index("## Coverage Status")
    return prompt[start : prompt.index("{{COVERAGE_STATUS}}", start)]


def test_the_ledger_is_introduced_to_the_guide_in_her_words() -> None:
    """Her heading and paragraph (`prompts/guide_system_prompt.md`, a3f3c69:242-244)."""
    ours = default_prompt(IRPromptKey.GUIDE)["prompt"]

    assert _coverage_section(ours) == _coverage_section(HER_GUIDE.read_text(encoding="utf-8")), (
        "o cabeçalho dizia 'act on it' e mandava trazer tudo o que restava — instrução, "
        "onde o dela diz que o ledger é informação e a decisão é do Guia"
    )
