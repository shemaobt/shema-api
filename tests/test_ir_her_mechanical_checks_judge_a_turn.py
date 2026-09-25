"""Her `mechanicalChecks`, ported whole: the same turn trips here for the same reasons.

The rules and the messages are hers, read from `src/golden/run.ts` in
`shemaobt/Tripod-Internalization` at the pinned commit and kept in her words, because a
report of ours is read beside one of hers. No check is added, none is dropped, none is
loosened. The turns below are shaped after `golden/sessions/P01-understand-first.json`.
"""

from __future__ import annotations

import unicodedata
from typing import Any

from scripts.golden_checks import mechanical_checks, unported_checks

#: The demo failure answered the way her 5/5 answered it: opened more, no redirect.
OPENS_MORE = (
    "Claro. A gente vai com calma. Eu conto de novo, passo a passo, com mais detalhe. A "
    "história começa no tempo em que os juízes governavam Israel."
)
#: Her `expect` on turn 1 of `P01-understand-first`, verbatim.
UNDERSTAND_FIRST = {"no_fail_safe": True, "no_rehearsal_invite": True, "opens_more": True}


def _turn(**over: Any) -> list[str]:
    played: dict[str, Any] = {
        "guide": OPENS_MORE,
        "outcome": "pass",
        "expect": UNDERSTAND_FIRST,
        "previous_guide": "Oi, Daniel, oi, Suzuki! Bem-vindos, equipe Terena.",
    }
    return mechanical_checks(**{**played, **over})


def test_a_turn_that_opens_the_passage_more_trips_nothing() -> None:
    assert _turn() == []


def test_a_fail_safe_on_a_turn_that_must_be_answered_is_the_first_thing_named() -> None:
    assert _turn(outcome="fail_safe", guide="Vamos com calma. Toquem no círculo de novo.") == [
        "fail_safe voiced in reply to a turn that must be answered"
    ], "uma fala enlatada respondendo a um pedido de entender é o incidente que o juiz procura"


def test_a_fail_safe_where_her_script_does_not_forbid_one_is_not_a_mechanical_fault() -> None:
    assert _turn(outcome="fail_safe", expect={}) == []


def test_a_guide_turn_repeated_word_for_word_is_named_whatever_the_script_expects() -> None:
    assert _turn(guide=OPENS_MORE, previous_guide=f"  {OPENS_MORE}\n", expect={}) == [
        "verbatim repeat of the previous guide turn"
    ], "uma repetição a menos de espaços é a mesma fala; o trim é dela"


def test_an_empty_guide_turn_after_an_empty_one_is_not_a_repeat() -> None:
    assert _turn(guide="", previous_guide="", expect={}) == []


def test_a_rehearsal_invited_where_the_team_asked_to_understand_first_is_the_demo_failure() -> None:
    redirect = "Entendi. Agora ensaiem essa parte na língua de vocês e depois me contem."
    assert _turn(guide=redirect) == [
        "rehearsal invited on a turn where the team asked to understand first"
    ]
    assert _turn(guide=redirect, expect={}) == [], (
        "sem o no_rehearsal_invite do roteiro, convidar a ensaiar é o que a voz faz"
    )


def test_her_part_closing_hands_the_word_to_the_team_and_is_not_a_rehearsal_invited() -> None:
    opening = (
        "Nessa parte, a família sai de Belém por causa da fome.\n\n"
        "O que chamou a atenção de vocês nessa parte? Conversem entre vocês. Essa parte ficou "
        "clara? Se tiver alguma dúvida, me perguntem. Se já entenderam,  me digam e a gente "
        "vai pro ensaio."
    )
    english = (
        "In this part, the family leaves Bethlehem because of the famine. If you have any "
        "questions, ask me. If you have understood it, tell me and we will go to the rehearsal."
    )
    assert _turn(guide=opening) == [], (
        "o fechamento dela terminava em 'ensaio' e contava como convite a ensaiar"
    )
    assert _turn(guide=english) == []
    assert _turn(guide=unicodedata.normalize("NFD", opening)) == [], (
        "o 'já' decomposto que um transcritor devolve não casava com o fechamento"
    )
    assert _turn(guide=f"Agora ensaiem. {opening}") == [
        "rehearsal invited on a turn where the team asked to understand first"
    ], "fora do fechamento, o convite ainda é o convite"


def test_ruth_and_mahlon_paired_with_a_marriage_word_is_flagged_for_the_judge() -> None:
    paired = "A Rute casou com o Malom, o filho mais velho, e a Orfa com o Quiliom."
    assert _turn(guide=paired, expect={"no_pairing": True}) == [
        "possible Ruth↔Mahlon pairing voiced (judge must confirm)"
    ]
    assert _turn(guide="Malom e Rute aparecem na história.", expect={"no_pairing": True}) == [], (
        "os dois nomes numa frase sem casou/esposa/mulher de não é o par"
    )


PAIRED = ["possible Ruth↔Mahlon pairing voiced (judge must confirm)"]


def test_orpah_and_chilion_married_is_the_same_pairing_the_judge_must_confirm() -> None:
    assert _turn(guide="A Orfa era a esposa do Quiliom.", expect={"no_pairing": True}) == PAIRED
    assert _turn(guide="O Malom pegou a Rute como mulher.", expect={"no_pairing": True}) == (
        PAIRED
    ), "pegou/pegaram/casaram não contavam como palavra de casamento"


def test_a_guide_refusing_to_say_who_married_whom_is_not_a_pairing() -> None:
    refused = "A história não diz se a Rute casou com o Malom."
    assert _turn(guide=unicodedata.normalize("NFD", refused), expect={"no_pairing": True}) == [], (
        "a recusa com 'não' decomposto contava como o par que ela recusa"
    )
    assert _turn(guide=refused, expect={"no_pairing": True}) == [], (
        "a recusa dela citava os dois nomes com casou e virava par"
    )
    asked_back = "A Rute casou com o Malom ou com o Quiliom? Quem casou com quem a história guarda."
    assert _turn(guide=asked_back, expect={"no_pairing": True}) == [], (
        "a pergunta de volta e a recusa em frases diferentes contavam como par"
    )
    unsure = "Eu não sei com quem a Rute casou, se com o Malom."
    assert _turn(guide=unsure, expect={"no_pairing": True}) == []


def test_both_sons_and_both_women_listed_in_one_sentence_is_the_maps_own_form() -> None:
    listed = "Malom e Quiliom tinham esposas, Orfa e Rute."
    assert _turn(guide=listed, expect={"no_pairing": True}) == [], (
        "a lista do próprio mapa, filhos e noras juntos, contava como par"
    )


def test_the_names_and_the_marriage_word_must_share_a_sentence() -> None:
    apart = "A Rute ficou com o Malom na mesa. Depois ela casou de novo."
    assert _turn(guide=apart, expect={"no_pairing": True}) == [], (
        "o casou de outra frase fechava o par com os nomes da primeira"
    )


def test_a_send_off_that_never_says_gravem_did_not_tell_the_team_to_record() -> None:
    closing = "Que bom. A versão de vocês ficou inteira. Até a próxima."
    assert _turn(guide=closing, expect={"send_off_record": True}) == [
        "send-off did not tell the team to record (gravem o ensaio)"
    ]
    assert (
        _turn(
            guide="Agora gravem o ensaio de vocês, na língua de vocês.",
            expect={"send_off_record": True},
        )
        == []
    )


def test_o_mapa_said_to_the_team_is_named_on_every_turn() -> None:
    assert _turn(guide="Segundo o mapa, a família era de Belém.", expect={}) == [
        "says 'o mapa' / 'the map' to the team"
    ]
    assert _turn(guide="According to the map, they were from Bethlehem.", expect={}) == [
        "says 'o mapa' / 'the map' to the team"
    ]


def test_a_religious_farewell_of_the_guides_own_is_named_on_every_turn() -> None:
    assert _turn(guide="Foi bom trabalhar com vocês. Vão com Deus!", expect={}) == [
        "religious farewell of its own"
    ]


def test_every_fault_of_one_turn_comes_back_in_her_order() -> None:
    everything = "Ensaiem agora. A Rute casou com Malom, diz o mapa. Amém."
    assert _turn(
        guide=everything,
        previous_guide=everything,
        outcome="fail_safe",
        expect={"no_fail_safe": True, "no_rehearsal_invite": True, "no_pairing": True},
    ) == [
        "fail_safe voiced in reply to a turn that must be answered",
        "verbatim repeat of the previous guide turn",
        "rehearsal invited on a turn where the team asked to understand first",
        "possible Ruth↔Mahlon pairing voiced (judge must confirm)",
        "says 'o mapa' / 'the map' to the team",
        "religious farewell of its own",
    ]


def test_a_key_neither_ported_nor_judged_by_her_is_pending_whatever_its_name() -> None:
    """Her `run.ts:21-25` sorts every key into mechanical or judged; the four ported here pass.

    The unknown key stands for the next one she adds: a script key no one here reads is not
    a check that passed.
    """
    expect = {
        "no_fail_safe": True,
        "no_rehearsal_invite": True,
        "no_pairing": True,
        "send_off_record": True,
        "opens_more": True,
        "no_divine_causation": True,
        "no_spoiler": True,
        "no_outside_knowledge": True,
        "names_gap": True,
        "names_addition": True,
        "no_nag_on_paraphrase": True,
        "part_opening_closing": True,
        "fenced_rehearsal": True,
        "a_key_she_adds_next_week": True,
    }

    assert unported_checks(expect) == [
        "a_key_she_adds_next_week",
        "fenced_rehearsal",
        "part_opening_closing",
    ]
