"""ENG-1378 — the name check matches names by her rules, on the labels of her canon.

Her matcher (`concreteMatch.ts`, `sessionForms.ts` at 18fa7c4) decides which words name an
element. Every expectation below is one of her own cases from `src/coverage/coverageTest.ts`,
read on our canon: a check that matched less would leave a bead the team named untouched,
and one that matched more would credit the team with what they never said.
"""

from __future__ import annotations

from app.services.internalization_room.coverage import initial_state
from app.services.internalization_room.name_check import names_heard


def _team_says(pericope: str, said: str) -> dict[str, str]:
    return names_heard(initial_state(pericope), team=said, voice="", pericope=pericope)


def test_noemi_does_not_engage_the_woman_naomi_is_stripped_to_in_scene_four() -> None:
    heard = _team_says("P01", "Noemi ficou com os dois filhos")

    assert heard["being:S4:B3"] == "not_encountered", (
        "«Noemi» engajava «the woman», a forma que tira o nome dela na cena 4"
    )
