"""Her `mechanicalChecks`, ported whole: the same turn trips here for the same reasons.

The rules and the messages are hers, read from `src/golden/run.ts` in
`shemaobt/Tripod-Internalization` at the pinned commit and kept in her words, because a
report of ours is read beside one of hers. No check is added, none is dropped, none is
loosened. The turns below are shaped after `golden/sessions/P01-understand-first.json`.
"""

from __future__ import annotations

from typing import Any

from scripts.golden_checks import mechanical_checks

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


def test_ruth_and_mahlon_paired_with_a_marriage_word_is_flagged_for_the_judge() -> None:
    paired = "A Rute casou com o Malom, o filho mais velho, e a Orfa com o Quiliom."
    assert _turn(guide=paired, expect={"no_pairing": True}) == [
        "possible Ruth↔Mahlon pairing voiced (judge must confirm)"
    ]
    assert _turn(guide="Malom e Rute aparecem na história.", expect={"no_pairing": True}) == [], (
        "os dois nomes numa frase sem casou/esposa/mulher de não é o par"
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
