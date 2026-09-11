"""Her `checkRound`, ported whole: the same round fails here for the same reasons.

The rules and the failure messages are hers, read from `src/golden/bt.ts` in
`shemaobt/Tripod-Internalization` on 2026-09-11 and kept in her words, because a report of
ours goes back to her and has to be legible beside one of hers. No check is added, none is
dropped, none is loosened.

The inputs are typed from her `golden/bt/*.json`; the map behind the P02 ones is
`_spec/canon/meaning-map/P02-Ruth-1-6-14.md`, scene 1 (Ruth 1:6-7).
"""

from __future__ import annotations

from typing import Any

from scripts.bt_golden_checks import check_round

#: A turn that passes every unconditional check of hers: it says `vocês`, says `tradu`,
#: addresses nobody in the singular, names one frase, carries no banned verb, no `o mapa`
#: and no blessing.
A_GOOD_TURN = (
    "Vocês traduziram bem quase tudo. Na frase 1 vocês disseram que as noras pediram. Isso "
    "está no áudio de vocês, ou entrou agora na tradução?"
)

THE_EXTRA_CAUSE = (
    "A tradução diz que Noemi decidiu voltar porque as noras pediram; a história conta apenas "
    "que ela ouviu a notícia do pão."
)

#: Her `expect` of `P02-causa-a-mais`, round one, verbatim.
CAUSA_A_MAIS = {
    "conferida": False,
    "findings": [
        {
            "kind": "addition",
            "note": "(?=[\\s\\S]*noras?)(?=[\\s\\S]*pedi)(?=[\\s\\S]*(decid|volt))",
            "frase": 1,
        }
    ],
    "no_kinds": ["missing"],
    "spoken_names_frase": 1,
    "spoken_asks_audio_or_explanation": True,
    "spoken_must_not_match": (
        "quem (lhe |a )?contou|alguém (lhe |a )?contou|contaram (a|para) (ela|Noemi)|"
        "(Deus|o Senhor|YHWH) (a )?trouxe|trouxe (ela|Noemi)"
    ),
}


def _round(**over: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "findings": [{"kind": "addition", "note": THE_EXTRA_CAUSE, "frase": 1}],
        "spoken": A_GOOD_TURN,
        "outcome": "pass",
        "conferida": False,
    }
    return {**result, **over}


def test_her_causa_a_mais_expectation_passes_a_round_that_meets_it() -> None:
    assert check_round(_round(), CAUSA_A_MAIS) == []


def test_a_missing_where_nothing_is_missing_fails_by_no_kinds() -> None:
    told = _round(
        findings=[
            {"kind": "addition", "note": THE_EXTRA_CAUSE, "frase": 1},
            {"kind": "missing", "note": "A notícia do pão não é contada.", "frase": 1},
        ]
    )

    assert check_round(told, CAUSA_A_MAIS) == [
        'a missing finding must not appear here (no_kinds): "A notícia do pão não é contada."'
    ], (
        "o caso real do João: a notícia do pão está presente e uma causa a mais foi somada a "
        "ela, então nada falta — é isto que prova que o nosso leitor não depende do par"
    )


def test_no_finding_sweeps_every_note() -> None:
    expect = {
        "conferida": False,
        "findings": [],
        "no_finding": "Orfa|Rute|dez anos|casar|casamento",
    }
    told = _round(findings=[{"kind": "missing", "note": "Orfa não aparece.", "frase": 2}])

    assert (
        "a finding about a detail that IS in the telling (split across frases): "
        '"Orfa não aparece."' in check_round(told, expect)
    )


def test_the_voice_must_not_fill_the_marked_silence() -> None:
    told = _round(spoken="Vocês traduziram bem. Na frase 1, o Senhor a trouxe de volta para casa.")

    assert check_round(told, CAUSA_A_MAIS) == [
        "the voice must not match /quem (lhe |a )?contou|alguém (lhe |a )?contou|contaram "
        "(a|para) (ela|Noemi)|(Deus|o Senhor|YHWH) (a )?trouxe|trouxe (ela|Noemi)/ — it said: "
        '"o Senhor a trouxe"'
    ], "a checagem negativa cita o que a voz disse, que é o que a Marcia lê no relatório"


def test_the_singular_address_fails_and_voces_alone_passes() -> None:
    singular = _round(
        spoken="Você traduziu bem. Na frase 1 vocês disseram algo a mais, entrou na tradução?"
    )
    plural = _round(spoken=A_GOOD_TURN)

    assert check_round(singular, CAUSA_A_MAIS) == [
        'the voice addresses one person: "Você traduziu bem"'
    ]
    assert check_round(plural, CAUSA_A_MAIS) == [], (
        "o `\\b` do Python é ciente de Unicode, então `\\bvocê\\b` não casa dentro de `vocês`; "
        "o `\\p{L}` dela não existe aqui e esta é a prova de que a tradução do regex vale"
    )


def test_the_banned_verb_fails_and_the_ruled_frame_passes() -> None:
    banned = _round(
        spoken="Vocês contaram a história. Na frase 1 entrou algo a mais na tradução, vocês viram?"
    )
    ruled = _round(
        spoken=(
            "Vocês traduziram bem. Na frase 1 vocês disseram que as noras pediram, e isso a "
            "história não conta. Entrou agora na tradução?"
        )
    )

    assert check_round(banned, CAUSA_A_MAIS) == [
        'banned vocabulary (spec §5 — the word is traduzir): "contaram"'
    ]
    assert check_round(ruled, CAUSA_A_MAIS) == [], (
        "`conta` sozinho fica: 'isso a história não conta' é o enquadramento que a §5 decidiu"
    )


def test_more_than_one_frase_named_in_one_turn_fails() -> None:
    two = _round(
        spoken=(
            "Vocês traduziram bem. Na frase 1 e na frase 9 vocês disseram algo a mais. Entrou "
            "na tradução?"
        )
    )
    twice = _round(
        spoken=(
            "Vocês traduziram bem. Na frase 1 vocês disseram algo a mais; a frase 1 é a que "
            "vamos ouvir. Entrou na tradução?"
        )
    )

    assert "more than one frase named in one turn: frase 1, frase 9" in check_round(
        two, CAUSA_A_MAIS
    )
    assert check_round(twice, CAUSA_A_MAIS) == [], "a mesma frase duas vezes é um assunto só"


def test_a_fail_safe_outcome_fails_the_round() -> None:
    assert "the verdict fell to a fail-safe line" in check_round(
        _round(outcome="fail_safe"), CAUSA_A_MAIS
    )


def test_conferida_must_equal_the_expectation() -> None:
    assert check_round(_round(conferida=True), CAUSA_A_MAIS) == [
        "conferida=true, expected false (outcome pass)"
    ]


def test_spoken_names_frase_reads_the_number_whole() -> None:
    named = _round(spoken=A_GOOD_TURN)
    longer = _round(
        spoken="Vocês traduziram bem. Na frase 12 vocês disseram algo a mais, entrou na tradução?"
    )

    assert check_round(named, CAUSA_A_MAIS) == []
    assert "the voice does not name frase 1" in check_round(longer, CAUSA_A_MAIS), (
        "`frase\\s+1\\b` não pode casar dentro de `frase 12`, ou a checagem aprova a voz "
        "falando da frase errada"
    )


def test_the_voice_must_ask_whether_it_entered_in_the_translation() -> None:
    silent = _round(spoken="Vocês disseram algo a mais na frase 1. Isso está na gravação de vocês?")

    fails = check_round(silent, CAUSA_A_MAIS)

    assert "the voice never says traduzir/tradução" in fails
    assert "the voice does not ask whether it entered in the translation ('na tradução')" in fails


def test_an_empty_findings_expectation_with_any_finding_fails() -> None:
    expect = {"conferida": True, "findings": [], "spoken_matches": "aprov|ouvir"}
    told = _round(
        conferida=True,
        spoken="Vocês traduziram tudo. Podem ouvir e aprovar quando quiserem.",
    )

    assert check_round(told, expect) == [
        f"expected no findings, got [addition@1: {THE_EXTRA_CAUSE}]"
    ]


def test_extra_findings_beside_the_expected_one_are_allowed() -> None:
    told = _round(
        findings=[
            {"kind": "addition", "note": THE_EXTRA_CAUSE, "frase": 1},
            {"kind": "unclear", "note": "A frase 7 ficou difícil de seguir.", "frase": 7},
        ]
    )

    assert check_round(told, CAUSA_A_MAIS) == [], (
        "a expectativa dela nomeia o que tem de aparecer, não a lista inteira; só `findings` "
        "vazio, `no_kinds` e `no_finding` proíbem"
    )


def test_the_expected_finding_must_name_the_frase_it_was_promised_on() -> None:
    told = _round(findings=[{"kind": "addition", "note": THE_EXTRA_CAUSE, "frase": 2}])

    assert check_round(told, CAUSA_A_MAIS) == ["the addition finding should name frase 1, names 2"]


def test_a_finding_the_expectation_promised_that_never_came_is_named_with_what_did() -> None:
    told = _round(findings=[{"kind": "unclear", "note": "Não deu para seguir.", "frase": 4}])

    assert check_round(told, CAUSA_A_MAIS) == [
        "expected a addition finding matching "
        "/(?=[\\s\\S]*noras?)(?=[\\s\\S]*pedi)(?=[\\s\\S]*(decid|volt))/ — got "
        "[unclear@4: Não deu para seguir.]"
    ]


def test_the_voice_never_says_the_map_and_never_blesses() -> None:
    mapped = _round(spoken="Vocês traduziram bem. O mapa diz outra coisa na frase 1. Tradução?")
    blessed = _round(spoken="Vocês traduziram bem a frase 1. Entrou na tradução? Vão com Deus.")

    assert "says 'o mapa'" in check_round(mapped, CAUSA_A_MAIS)
    assert "a blessing" in check_round(blessed, CAUSA_A_MAIS)


def test_spoken_matches_is_required_when_her_script_carries_it() -> None:
    expect = {"conferida": True, "findings": [], "spoken_matches": "aprov|ouvir"}
    told = _round(
        findings=[],
        conferida=True,
        spoken="Vocês traduziram tudo e a passagem está conferida. Na frase 1 ficou bom.",
    )

    assert check_round(told, expect) == ["the voice does not match /aprov|ouvir/"]


def test_her_dropped_no_finding_would_have_failed_the_correct_run() -> None:
    """Why `P02-causa-a-mais` carries no `no_finding`, as a fact and not as a claim.

    She removed it rather than loosening it: the check sweeps the note of every finding, and
    the addition's note, obeying the whole-relation rule, cites the news of the bread as the
    contrast. A port that applied it anyway would fail a run that is right.
    """
    correct = _round()
    with_it = {**CAUSA_A_MAIS, "no_finding": "pão|notícia"}

    assert check_round(correct, CAUSA_A_MAIS) == []
    assert check_round(correct, with_it) == [
        "a finding about a detail that IS in the telling (split across frases): "
        f'"{THE_EXTRA_CAUSE}"'
    ]
