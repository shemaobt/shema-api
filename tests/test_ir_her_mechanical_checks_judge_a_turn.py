"""Her `mechanicalChecks`, ported whole: the same turn trips here for the same reasons.

The rules and the messages are hers, read from `src/golden/run.ts` in
`shemaobt/Tripod-Internalization` at `533b6e3`, the commit `docs/doctrine/DOCTRINE_PIN` names,
and kept in her words, because a report of ours is read beside one of hers. Her runner at the
freeze (18fa7c4) has more checks than the seven ported here. No check is added, none is
dropped, none is loosened. The turns below are shaped after
`golden/sessions/P01-understand-first.json`.
"""

from __future__ import annotations

from typing import Any

from scripts.golden_checks import mechanical_checks

#: The demo failure answered the way her 5/5 answered it: opened more, no redirect.
OPENS_MORE = (
    "Claro. A gente vai com calma. Eu conto de novo, passo a passo, com mais detalhe. A "
    "história começa no tempo em que os juízes governavam Israel."
)
#: Her closing of a scene opening and its last two sentences, `src/turn/fixedLines.ts`.
PART_CLOSING = (
    "O que chamou a atenção de vocês nessa cena? Conversem entre vocês. Essa cena ficou clara? "
    "Se tiver alguma dúvida, me perguntem. Se já entenderam, me digam e a gente vai pro ensaio."
)
CLOSING_TAIL = (
    "Se tiver alguma dúvida, me perguntem. Se já entenderam, me digam e a gente vai pro ensaio."
)
#: The story of scene 1 her `checksTest.ts` opens a part with.
STORY = (
    "Nos dias em que os juízes julgavam, teve uma fome na terra. Um homem de Belém de Judá foi "
    "morar de passagem nos campos de Moabe, com a mulher e os dois filhos."
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


def test_o_mapa_after_an_accented_letter_is_her_o_mapa_because_her_word_edge_is_ascii() -> None:
    assert _turn(guide="No sertão mapa nenhum guiava a família.", expect={}) == [
        "says 'o mapa' / 'the map' to the team"
    ], "o \\b dela é ASCII: o ã não é letra pra ela, então 'o mapa' começava ali"


def test_her_closing_hands_the_word_to_the_team_and_invites_no_rehearsal() -> None:
    assert _turn(guide=f"{STORY} {PART_CLOSING}") == [], (
        "'a gente vai pro ensaio' entrega a palavra à equipe; não manda ensaiar"
    )
    broken = CLOSING_TAIL.replace("digam e", "digam\ne")
    assert _turn(guide=f"{STORY}\n\n{broken}") == [], (
        "a quebra de linha é um espaço pro ouvido; a frase dela é a mesma"
    )
    assert _turn(guide=f"{PART_CLOSING} Agora ensaiem essa parte.") == [
        "rehearsal invited on a turn where the team asked to understand first"
    ]


def test_a_pairing_is_read_sentence_by_sentence_and_a_denial_is_never_one() -> None:
    pairing = ["possible Ruth↔Mahlon pairing voiced (judge must confirm)"]
    no_pairing = {"no_pairing": True}
    assert _turn(guide="E o Quiliom pegou a Orfa como mulher.", expect=no_pairing) == pairing
    assert _turn(guide="Ela não fala se Rute casou com Malom.", expect=no_pairing) == [], (
        "negar o par é o Guia recusando o par, não dizendo"
    )
    assert _turn(guide="The story does not say Ruth married Mahlon.", expect=no_pairing) == []
    asked_back = "Rute casou com Malom ou com Quiliom? A história não diz qual."
    assert _turn(guide=asked_back, expect=no_pairing) == [], (
        "a negação noutra frase do turno também recusa o par"
    )
    assert (
        _turn(guide="Malom e Quiliom pegaram mulheres de Moabe, Orfa e Rute.", expect=no_pairing)
        == []
    ), "a lista do mapa, os dois filhos e as duas mulheres, não é par"
    assert (
        _turn(guide="Rute e Malom aparecem aqui. Depois o Quiliom casou.", expect=no_pairing) == []
    ), "o nome e o casamento em frases diferentes não são o par"


#: Her small-gaps choice, its Ensaio Final form and the older form, from her `checksTest.ts`.
CHOICE_FINAL = (
    "Vocês trouxeram quase tudo desta cena: a fome, a família de Belém, a ida pra Moabe. "
    "Faltaram só dois detalhes: dizer 'o marido de Noemi' e 'uns dez anos'. Querem ensaiar esta "
    "cena mais uma vez, ou preferem seguir e acertar esses dois no Ensaio Final? Lá a gente acerta "
    "isso juntos, e eu confiro tudo de novo com vocês."
)
CHOICE_FINAL_EN = (
    "You brought almost all of this scene: the famine, the family from Bethlehem, the move to "
    "Moab. Only two details were missing: saying 'Naomi's husband' and 'about ten years'. Do you "
    "want to rehearse this scene once more, or go on and fix those two in the Final Rehearsal? "
    "There we fix it together, and I check everything again with you."
)
CHOICE_OLD = (
    "Faltaram só dois detalhes. Querem contar a passagem mais uma vez, ou preferem seguir pra "
    "gravação e lembrar desses dois lá?"
)


def test_the_choice_of_the_second_near_complete_telling_names_the_recording_as_a_road() -> None:
    missing = [
        "guide did not offer the choice (contar de novo OU seguir pra gravação) on a second "
        "near-complete telling"
    ]
    offers = {"offers_choice": True}
    assert _turn(guide=CHOICE_OLD, expect=offers) == []
    assert _turn(guide="Podem contar de novo. Ou podem seguir pra gravação.", expect=offers) == []
    assert (
        _turn(
            guide="Vocês têm duas escolhas. Contar mais uma vez. Seguir pra gravação.",
            expect=offers,
        )
        == []
    )
    assert _turn(guide="Vamos guardar isso pra acertar depois.", expect=offers) == missing, (
        "adiar sem perguntar não é oferecer"
    )
    assert _turn(guide=CHOICE_FINAL, expect=offers) == missing, (
        "sem 'grava…' não é a escolha antiga"
    )


def test_a_first_imperfect_telling_is_never_offered_the_recording_as_an_alternative() -> None:
    offered = ["guide offered the recording as an alternative on a FIRST imperfect telling"]
    first = {"no_choice_offer": True}
    assert _turn(guide=CHOICE_OLD, expect=first) == offered
    assert _turn(guide=CHOICE_FINAL, expect=first) == offered
    assert (
        _turn(guide="Faltou dizer de que clã eles eram. Ensaiem esta cena de novo.", expect=first)
        == []
    )
    another_road = (
        "Faltou dizer que eles foram de passagem. Vocês podem ensaiar de novo agora ou tirar uma "
        "dúvida antes. Isso tudo fica pronto antes do Ensaio Final."
    )
    assert _turn(guide=another_road, expect=first) == [], (
        "outra alternativa e o Ensaio Final noutra frase não são a escolha"
    )


def test_the_small_gaps_choice_in_its_ensaio_final_form_is_read_sentence_by_sentence() -> None:
    missing = [
        "guide did not offer the choice (ensaiar esta cena mais uma vez OU seguir e acertar no "
        "Ensaio Final)"
    ]
    final = {"offers_choice_final": True}
    for offered in (
        CHOICE_FINAL,
        CHOICE_FINAL_EN,
        "Querem ensaiar esta cena mais uma vez? Ou preferem seguir e acertar esses dois no Ensaio "
        "Final?",
        "Faltou só um detalhe. Vocês têm duas escolhas. Ensaiar esta cena mais uma vez. Ou seguir, "
        "e a gente acerta isso no Ensaio Final.",
        "Querem ensaiar esta cena mais uma vez? Ou seguimos e acertamos isso no Ensaio Final?",
        "Vocês têm duas escolhas. Ensaiar esta cena mais uma vez. Seguir e acertar no Ensaio "
        "Final.",
        "You can rehearse this scene once more or fix it in the Final Rehearsal.",
        "Rehearse it again, or go on and fix it in the Final Rehearsal.",
    ):
        assert _turn(guide=offered, expect=final) == [], offered
    assert _turn(guide=CHOICE_OLD, expect=final) == missing
    assert (
        _turn(guide="No Ensaio Final, lembrem do marido de Noemi e dos dez anos.", expect=final)
        == missing
    ), "o lembrete do Ensaio Final não é uma escolha"


def test_each_detail_her_script_names_must_be_repeated_by_the_send_off() -> None:
    named = {"send_off_names": ["quem é você", "só o nome dele"]}
    both = "No Ensaio Final, lembrem da pergunta, quem é você, e de dizer Só o nome dele."
    assert _turn(guide=both, expect=named) == [], "o /i dela: maiúscula ou minúscula, é o detalhe"
    assert _turn(guide="No Ensaio Final, lembrem da pergunta, quem é você.", expect=named) == [
        "send-off did not repeat the detail the team carries into the recording: /só o nome dele/i"
    ]


def test_a_send_off_her_script_wants_scene_by_scene_says_so() -> None:
    by_scene = {"send_off_scene_by_scene": True}
    assert _turn(guide="Agora gravem a passagem parte por parte.", expect=by_scene) == []
    assert _turn(guide="Agora gravem cena por cena.", expect=by_scene) == []
    assert _turn(guide="Agora gravem a passagem inteira.", expect=by_scene) == [
        "send-off did not tell the team to record scene by scene"
    ]


def test_a_faithful_telling_in_other_words_is_never_sent_back_nor_asked_for_the_noun() -> None:
    accepts = {"accepts_telling": True}

    def refused(words: str) -> list[str]:
        return [
            f'a faithful telling in other words was not accepted (meaning, not form): "{words}"'
        ]

    assert _turn(guide="Isso é acréscimo da equipe.", expect=accepts) == refused("acréscimo")
    assert _turn(guide="Vamos contar essa parte de novo.", expect=accepts) == refused(
        "Vamos contar essa parte de novo"
    )
    assert _turn(guide="Contem de novo, sem a fome.", expect=accepts) == refused(
        "Contem de novo, sem"
    )
    assert _turn(guide="Ensaiem essa parte de novo.", expect=accepts) == refused(
        "Ensaiem essa parte de novo"
    )
    assert _turn(guide="Isso a história não conta.", expect=accepts) == refused(
        "Isso a história não conta"
    )
    assert _turn(guide="Falta a palavra que o mapa usa.", expect=accepts) == [
        *refused("Falta a palavra"),
        "says 'o mapa' / 'the map' to the team",
    ]
    assert _turn(guide="A bondade fiel ficou de fora.", expect=accepts) == refused(
        "bondade fiel ficou de fora"
    )
    assert _turn(guide="A palavra certa é bondade fiel.", expect=accepts) == refused(
        "A palavra certa é"
    )
    assert _turn(guide="Não é a palavra exata.", expect=accepts) == refused("Não é a palavra exata")
    assert _turn(guide="Faltou só a bondade.", expect=accepts) == refused("Faltou só a bondade")
    for accepted in (
        "Isso não é acréscimo, é a história.",
        "Ficou inteiro, sem acréscimo.",
        "Vocês não precisam contar de novo.",
        "Querem que eu conte de novo, mais devagar?",
        "Isso a história não conta, e vocês guardaram esse silêncio.",
        "Vocês não precisam usar a palavra bondade fiel.",
        "Gostei da palavra que vocês usaram.",
        "Ficou inteiro e só com o que a história conta.",
    ):
        assert _turn(guide=accepted, expect=accepts) == [], accepted


#: The fence's two lines and item 3's microphone sentence, `src/turn/fixedLines.ts`.
FENCE_OPEN = "Agora vou dizer tudo o que deve entrar no ensaio de vocês."
FENCE_CLOSE = "Agora podem ensaiar."
MIC = (
    "Quando estiverem prontos, toquem no microfone vermelho, gravem o ensaio desta cena e "
    "traduzam pra mim frase por frase."
)
#: Her live fence of 2026-09-23 23:09-37, P01-part-opening-closing turn 3.
REAL_FENCE = (
    f"Ótimo. {FENCE_OPEN}\n\nNo tempo em que os juízes governavam Israel, veio uma fome na terra. "
    "Um homem de Belém de Judá saiu de lá com a mulher dele e os dois filhos, pra morar de "
    "passagem na terra de Moabe. O nome do homem era Elimeleque. O nome da mulher dele era "
    "Noemi. Os nomes dos dois filhos eram Malom e Quiliom. Eles eram efrateus, de Belém de Judá. "
    f"Eles chegaram na terra de Moabe e ficaram lá.\n\n{FENCE_CLOSE} {MIC}"
)
FENCED = {"fenced_rehearsal": True}


def _fenced(story: str) -> list[str]:
    return _turn(guide=f"{FENCE_OPEN} {story} {FENCE_CLOSE} {MIC}", expect=FENCED)


def test_the_invitation_to_rehearse_is_the_fence_opening_line_then_agora_podem_ensaiar() -> None:
    no_fence = [
        "the invitation to rehearse has no fenced block (opening line … 'Agora podem ensaiar.')"
    ]
    assert _turn(guide=REAL_FENCE, expect=FENCED) == []
    p08 = (
        "Primeiro, teve uma fome na terra, no tempo dos juízes. Segundo, um homem de Belém de "
        f"Judá foi morar de passagem em Moabe.\n\n{CLOSING_TAIL}"
    )
    assert _turn(guide=p08, expect=FENCED) == no_fence, "o piloto P08: passos numerados, sem cerca"
    assert _turn(guide=f"{FENCE_OPEN} {STORY}", expect=FENCED) == no_fence
    assert _turn(guide=f"{FENCE_CLOSE} {FENCE_OPEN} {STORY}", expect=FENCED) == no_fence


def test_nothing_but_the_story_stands_inside_the_fence_not_a_comment_nor_a_step_label() -> None:
    def inside(words: str) -> list[str]:
        return [f'commentary inside the fenced rehearsal block: "{words}"']

    assert _fenced("Reparem que a fome veio primeiro.") == inside("Reparem")
    assert _fenced("A história não diz por que ele foi.") == inside("A história não diz")
    assert _fenced("Eram três coisas: a fome, a ida, a morte.") == inside("três coisas")
    for story, hit in (
        ("Primeiro, teve uma fome na terra. Depois, foram pra Moabe.", "Primeiro,"),
        ("Teve uma fome. Sétimo: eles ficaram lá.", "Sétimo:"),
        ("Teve uma fome. Se\u0301timo: eles ficaram lá.", "Sétimo:"),
        ("Primeiro passo: teve uma fome na terra.", "Primeiro passo:"),
        ("Passo 1, teve uma fome na terra.", "Passo 1"),
        ("Teve uma fome. Esse é o passo um.", "passo um"),
        ("São sete passos. Teve uma fome na terra.", "sete passos"),
        ("Teve uma fome.\n2. Foram pra Moabe.", "2."),
        (
            "Primeiro Noemi falou pra elas voltarem. Segundo Rute disse que não.",
            "primeiro … segundo",
        ),
        ("First, there was a famine in the land.", "First,"),
        ("Primeiro - teve uma fome na terra.", "Primeiro -"),
    ):
        assert _fenced(story) == inside(hit), story
    for story in (
        "Primeiro ele foi a Moabe. Depois a família ficou lá.",
        "No primeiro dia eles andaram muito. E no fim chegaram em Moabe.",
        "Ela deu um passo pra frente e disse: não.",
        "E ela contou passo a passo o que tinha acontecido.",
        "Segundo o costume daquele tempo, o homem tirava a sandália. Primeiro ele foi à porta.",
        "Na segunda-feira ela foi. Segunda-feira ela voltou.",
        "Segunda-feira ela voltou. Primeiro ela passou na casa da sogra.",
        "Noemi disse: primeiro, voltem pra casa da mãe de vocês.",
        "Segundo ela, o Senhor tinha tirado tudo dela. Primeiro o marido morreu.",
    ):
        assert _fenced(story) == [], story


def test_after_the_fence_closing_line_only_the_microphone_is_said() -> None:
    after = ["commentary after the fence's closing line"]
    fence = f"{FENCE_OPEN} {STORY} {FENCE_CLOSE} {MIC}"
    assert _turn(guide=f"{fence} {CLOSING_TAIL}", expect=FENCED) == after, (
        "o piloto P08: a cauda do fechamento depois da cerca"
    )
    assert _turn(guide=f"{fence} If you have any questions, ask me.", expect=FENCED) == after
    assert _turn(guide=f"{fence} Lembrem da fome.", expect=FENCED) == after
