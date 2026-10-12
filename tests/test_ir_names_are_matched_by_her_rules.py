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


def test_the_hebrew_echo_of_naomi_engages_her_and_the_woman_in_scene_four() -> None:
    heard = _team_says("P01", "ela era נעמי")

    assert heard["being:S4:B3"] == "engaged", (
        "o eco hebraico do nome, a única chave da forma «the woman», não engajava a cena 4"
    )
    assert heard["being:S1:B3"] == "engaged", "o eco hebraico de Noemi não engajava Noemi"


def test_noemia_is_not_noemi_a_name_is_matched_as_a_whole_word() -> None:
    heard = _team_says("P01", "Noemia chegou")

    assert heard["being:S1:B3"] == "not_encountered", (
        "«Noemia» engajava Noemi porque o nome era procurado dentro da palavra"
    )


def test_the_hebrew_echo_is_found_inside_a_word_that_carries_a_prefix() -> None:
    heard = _team_says("P01", "אלימלך ונעמי")

    assert heard["being:S1:B3"] == "engaged", (
        "o eco hebraico com um prefixo não engajava Noemi, e o dela é lido dentro da palavra"
    )
