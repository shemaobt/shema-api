"""The fail-safe lines the room speaks: written in every language it claims, never naming the
draft machinery, and rotated so a repeated failure does not repeat a sentence."""

import re

import pytest

from app.services.internalization_room._default_prompts import (
    _PROMPTS_DIR,
    fail_safe_utterances,
)
from app.services.internalization_room.fail_safe import FailSafe, choose, localized
from app.services.internalization_room.languages import ROOM_LANGUAGES


@pytest.mark.parametrize("spoken", ROOM_LANGUAGES)
def test_every_kind_the_room_claims_to_speak_is_written_in_it(spoken: str) -> None:
    """Um idioma reivindicado e não escrito é uma sala que troca de língua no meio.

    Medido com `localized` e não com `utterances`: `utterances` cai para o bloco inglês e
    por isso nunca volta vazio, o que a torna segura para falar e inútil como medida.
    """
    for kind in FailSafe:
        if kind in (FailSafe.UNTOLD_STRETCH, FailSafe.STRETCH_TO_CORRECT):
            continue
        written = localized(kind, spoken)
        assert written, (
            f"a sala diz que fala {spoken!r} e a família {kind} não tem falas escritas nesse "
            "idioma — a equipe ouviria a falha em outra língua"
        )


def test_the_room_keeps_no_fail_safe_draft_for_a_language_it_does_not_speak() -> None:
    on_disk = {path.name for path in _PROMPTS_DIR.glob("_fail_safe_*_supplement.md")}

    assert on_disk == {"_fail_safe_pt_supplement.md"}
    assert {kind: localized(kind, "es") for kind in FailSafe if localized(kind, "es")} == {}
    assert "-es." not in fail_safe_utterances()


@pytest.mark.parametrize("spoken", ROOM_LANGUAGES)
def test_no_fail_safe_line_names_a_draft_a_rejection_the_validator_a_numbered_count_or_an_ordinal(
    spoken: str,
) -> None:
    mechanics = re.compile(
        r"rascunho|draft|tentativa|attempt|rejeit|reject|validador|validator"
        r"|\b\d+\s*(vez(es)?|times)\b"
        r"|\b(primeira|segunda|terceira|quarta|quinta)s?\b"
        r"|\b(first|second|third|fourth|fifth)\s+(time|try|attempt)\b|\b(third|fourth|fifth)\b",
        re.I,
    )
    for kind in FailSafe:
        for line in localized(kind, spoken):
            assert not mechanics.search(line), (
                f"a falha dita à equipe não pode expor o mecanismo: {kind} {spoken!r} {line!r}"
            )


def test_a_turn_answer_has_no_field_that_could_carry_a_draft() -> None:
    from app.models.internalization_room import TurnResponse

    leaks = {"attempt", "attempts", "draft", "drafts", "issues", "verdict", "trace"}
    assert leaks.isdisjoint(TurnResponse.model_fields)


def test_a_repeated_failure_does_not_repeat_the_same_sentence() -> None:
    """The authored file asks for variation; a room stuck on one line sounds like a machine."""
    spoken = [choose(FailSafe.UNREPAIRABLE, "pt", turn=turn) for turn in range(4)]

    assert len({line for line, _ in spoken}) == 4
    assert [name for _, name in spoken] == ["A0", "A1", "A2", "A3"]


def test_the_rotation_wraps_instead_of_running_out() -> None:
    line, name = choose(FailSafe.UNREPAIRABLE, "pt", turn=4)

    assert name == "A0"
    assert line == choose(FailSafe.UNREPAIRABLE, "pt", turn=0)[0]


def test_the_portuguese_acknowledgements_are_her_three_and_ta_is_not_among_them() -> None:
    assert localized(FailSafe.INSTANT_ACK, "pt") == [
        "Hmm.",
        "Certo.",
        "Deixa eu pensar um instante.",
    ]


def test_the_english_acknowledgements_are_her_three_and_right_is_not_among_them() -> None:
    assert localized(FailSafe.INSTANT_ACK, "en") == [
        "Mm-hm.",
        "Okay.",
        "Mmm \u2014 let me think about that for a moment.",
    ]


def test_a_kind_with_one_line_always_answers_with_it() -> None:
    assert choose(FailSafe.HARD_STOP, "pt", turn=7)[1] == "E0"


def test_an_unwritten_language_falls_back_to_the_authored_line() -> None:
    """Silence would be the one outcome worse than the wrong language."""
    line, name = choose(FailSafe.UNREPAIRABLE, "xx", turn=0)

    assert line
    assert name == "A0"
