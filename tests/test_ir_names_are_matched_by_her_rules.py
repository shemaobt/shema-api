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


def test_belem_said_without_its_accent_still_engages_bethlehem() -> None:
    heard = _team_says("P01", "eles saíram de Belem")

    assert heard["place:S1:PL1"] == "engaged", (
        "a transcrição sem o acento de «Belém» não engajava Belém"
    )


def test_one_word_of_fields_of_moab_names_it_in_portuguese_and_in_english() -> None:
    assert _team_says("P01", "foram pros campos de Moabe")["place:S1:PL2"] == "engaged", (
        "«Moabe», a palavra que distingue «Fields of Moab», não engajava o lugar"
    )
    assert _team_says("P01", "they went to Moab")["place:S1:PL2"] == "engaged", (
        "«Moab», o nome próprio dentro de «Fields of Moab», não engajava o lugar"
    )


def test_os_juizes_alone_names_the_judges_and_not_the_days_when_the_judges_judged() -> None:
    days = "time:S1:TM_PERIOD_OF_JUDGES"

    assert _team_says("P01", "os juízes mandavam")[days] == "not_encountered", (
        "«juízes», o nome dos Juízes, engajava sozinho o tempo em que os juízes julgavam"
    )
    assert _team_says("P01", "no tempo dos juízes")[days] == "engaged", (
        "a frase inteira do tempo dos juízes não engajava o tempo"
    )


def test_ruth_alone_is_ruths_name_and_never_the_young_men_ruth_did_not_go_after() -> None:
    young_men = "being:S3:B32"

    assert _team_says("P09", "Ruth lay down")[young_men] == "not_encountered", (
        "«Ruth», o nome dela, engajava sozinho os rapazes atrás de quem ela não foi"
    )
    assert _team_says("P09", "Rute foi pra eira e deitou")[young_men] == "not_encountered"
    assert _team_says("P09", "ela não foi atrás dos rapazes")[young_men] == "engaged", (
        "«rapazes», o nome inteiro deles, não engajava os rapazes"
    )


def test_resgatador_names_the_nearer_redeemer_only_where_boaz_is_not_the_redeemer() -> None:
    assert _team_says("P11", "o resgatador tirou a sandália")["being:S4:B19"] == (
        "not_encountered"
    ), "«resgatador» engajava o resgatador mais próximo na cena em que Boaz é o resgatador"
    assert _team_says("P11", "o resgatador passou por ali")["being:S1:B19"] == "engaged", (
        "«resgatador» não engajava o resgatador mais próximo onde Boaz só convoca"
    )


def test_a_long_word_of_a_label_the_names_list_does_not_hold_names_the_element() -> None:
    heard = _team_says("P01", "they stayed there for many years")

    assert heard["object:S3:TH_TEN_YEARS_APPROXIMATELY"] == "engaged", (
        "«years», palavra do rótulo «about ten years» que a lista de nomes não tem, não o engajava"
    )
