"""Her `mechanicalChecks`, ported whole: the same turn trips here for the same reasons.

The rules and the messages are hers, read from `src/golden/run.ts` in
`shemaobt/Tripod-Internalization` at her freeze (18fa7c4), with the helpers and the moment
reducer it calls, and kept in her words, because a report of ours is read beside one of hers.
At `533b6e3`, the commit `docs/doctrine/DOCTRINE_PIN` names, the function held seven checks;
the port is the freeze's now. No check is added, none is dropped, none is loosened. The turns
below are shaped after `golden/sessions/P01-understand-first.json` and the cases of her own
`src/golden/checksTest.ts` and `src/turn/momentTest.ts`; where her failure line quotes words,
the quote is what her function returns on the same sentence.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from scripts.golden_checks import (
    Moment,
    mechanical_checks,
    moment_after_reply,
    moment_at_turn_start,
)

#: The demo failure answered the way her 5/5 answered it: opened more, no redirect.
OPENS_MORE = (
    "Claro. A gente vai com calma. Eu conto de novo, passo a passo, com mais detalhe. A "
    "história começa no tempo em que os juízes governavam Israel."
)
PART_CLOSING = (
    "O que chamou a atenção de vocês nessa cena? Conversem entre vocês. Essa cena ficou clara? "
    "Se tiver alguma dúvida, me perguntem. Se já entenderam, me digam e a gente vai pro ensaio."
)
CLOSING_TAIL = (
    "Se tiver alguma dúvida, me perguntem. Se já entenderam, me digam e a gente vai pro ensaio."
)
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
        "earlier_guides": ["Oi, Daniel, oi, Suzuki! Bem-vindos, equipe Terena."],
        "parts": 4,
        "moment_before": None,
        "moment_after": None,
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


FENCE_OPEN = "Agora vou dizer tudo o que deve entrar no ensaio de vocês."
FENCE_CLOSE = "Agora podem ensaiar."
MIC = (
    "Quando estiverem prontos, toquem no microfone vermelho, gravem o ensaio desta cena e "
    "traduzam pra mim frase por frase."
)
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


PART_CLOSING_EN = (
    "What caught your attention in this scene? Talk it over among yourselves. Is this scene "
    "clear? If you have any questions, ask me. If you have understood it, tell me and we will go "
    "to the rehearsal."
)
PART_CLOSING_0923 = PART_CLOSING.replace("nessa cena", "nessa parte").replace(
    "Essa cena", "Essa parte"
)
P07_NEAR = (
    "Conversem entre vocês. Essa parte ficou clara? Se tiver alguma dúvida, me perguntem. Se já "
    "entenderam, me digam e a gente vai pro ensaio."
)
REMINDER_MIC = "Quando vocês gravarem essa primeira cena no microfone vermelho, lembrem dele."
FENCED_REPLY = (
    "Em Moabe acontece o resto da história. Mas vocês disseram que já entenderam a primeira parte. "
    "Então vamos ensaiar ela primeiro, pra ela entrar bem antes de seguir.\n\n"
    f"{FENCE_OPEN}\n\n{STORY}\n\n{FENCE_CLOSE}\n\n{MIC}"
)
WANTED_REPLY = (
    "A história não diz isso. Ela conta que os dois filhos, Malom e Quiliom, pegaram mulheres de "
    "Moabe. Uma se chamava Orfa, a outra se chamava Rute. Mas ela não diz qual filho casou com "
    "qual mulher.\n\nMas isso já é a terceira parte. A gente chega nela daqui a pouco, com calma."
    f"\n\n{CLOSING_TAIL}"
)
WHOLE_PASSAGE_QUESTION = (
    "Se tiver alguma dúvida, me perguntem. Se já entenderam, me digam, e a gente começa pela "
    "primeira parte."
)
NOT_ENDED = (
    "the part opening does not end with the fixed closing ('O que chamou a atenção de vocês "
    "nessa cena? … a gente vai pro ensaio.')"
)
NO_TAIL = (
    "the reply to the team's comment or question does not end with the closing's last two "
    "sentences ('Se tiver alguma dúvida, me perguntem. Se já entenderam, me digam e a gente vai "
    "pro ensaio.')"
)


def test_a_part_opening_ends_with_her_closing_and_sends_no_one_to_rehearse() -> None:
    opening = {"part_opening_closing": True}
    fence_now = "the fenced block was given in the same turn that opens a part"
    sent = (
        "the part opening sent the team to rehearse ('Agora podem ensaiar.' or the red "
        "microphone) before the team said it was ready"
    )
    broken = PART_CLOSING.replace("? ", "?\n")
    assert _turn(guide=f"{STORY}\n\n{broken}\n", expect=opening) == []
    assert _turn(guide=f"The story of the part. {PART_CLOSING_EN}", expect=opening) == []
    assert _turn(guide=f"{STORY} {PART_CLOSING_0923}", expect=opening) == [NOT_ENDED], (
        "o fechamento de 23/09 dizia 'parte'; desde 24/09 é 'cena'"
    )
    assert _turn(guide=f"{STORY} {P07_NEAR}", expect=opening) == [NOT_ENDED]
    assert _turn(guide=f"{STORY} {PART_CLOSING} {FENCE_OPEN}", expect=opening) == [
        NOT_ENDED,
        fence_now,
    ]
    probe = f"{STORY} {FENCE_CLOSE} {MIC} {PART_CLOSING}"
    assert _turn(guide=probe, expect=opening) == [sent]
    next_part = f"Posso, sim. {REMINDER_MIC} Agora vamos pra segunda parte.\n\n{PART_CLOSING}"
    assert _turn(guide=next_part, expect=opening) == [], (
        "lembrar do microfone vermelho não é mandar tocar nele"
    )
    for mention in (
        "Antes que vocês toquem no microfone vermelho, lembrem disso.",
        "Um toque no microfone vermelho = uma cena inteira.",
        "Toquem no círculo, não no microfone vermelho.",
        "When you tap the red microphone for the first scene, remember it.",
    ):
        assert _turn(guide=f"{mention} {PART_CLOSING}", expect=opening) == [], mention
    for instruction in (
        "Toquem de novo no microfone vermelho.",
        "Tap the red microphone and record your rehearsal of this scene.",
        "Now you can rehearse.",
    ):
        assert _turn(guide=f"{instruction} {PART_CLOSING}", expect=opening) == [sent], instruction


def test_a_take_up_ends_with_the_closing_tail_and_gives_no_fence_before_the_team_is_ready() -> None:
    take_up = {"take_up_closing": True}
    sent = (
        "the reply to the team's comment or question sent the team to rehearse ('Agora podem "
        "ensaiar.' or the red microphone) before the team said it was ready"
    )
    assert _turn(guide=WANTED_REPLY, expect=take_up) == []
    assert _turn(guide=f"Boa pergunta. {PART_CLOSING_0923}", expect=take_up) == []
    assert _turn(guide=FENCED_REPLY, expect=take_up) == [
        NO_TAIL,
        "the fenced block was given before the team said it was ready",
    ], "a regra (b): 'Entendi. E …?' não é a palavra pra ensaiar"
    assert _turn(guide=f"Toquem no microfone vermelho. {CLOSING_TAIL}", expect=take_up) == [sent]


def test_the_tail_is_asked_for_only_when_the_earlier_guide_turns_left_a_part_open() -> None:
    if_open = {"take_up_closing_if_open": True}
    reply = "A história não diz por que ele morreu."

    def after(*earlier: str, guide: str = reply) -> list[str]:
        return _turn(guide=guide, expect=if_open, earlier_guides=list(earlier))

    assert after(f"{STORY}\n\n{PART_CLOSING}") == [NO_TAIL]
    assert after(f"Boa pergunta. {CLOSING_TAIL}") == [NO_TAIL]
    assert after(WHOLE_PASSAGE_QUESTION, WHOLE_PASSAGE_QUESTION) == [], (
        "a pergunta da passagem inteira não abre parte nenhuma"
    )
    assert after() == []
    assert after(WHOLE_PASSAGE_QUESTION, PART_CLOSING, FENCED_REPLY) == [], "a cerca fecha a parte"
    assert after(FENCED_REPLY, PART_CLOSING) == [NO_TAIL]
    assert after(PART_CLOSING, "A história não diz por que ele morreu.") == [NO_TAIL], (
        "uma resposta sem nenhum dos dois finais deixa a pergunta pras de antes"
    )
    assert after(PART_CLOSING, guide=f"{reply} {CLOSING_TAIL}") == []
    assert after(guide=FENCED_REPLY) == [
        "the fenced block was given before the team said it was ready"
    ], "sem parte aberta a cauda não é pedida, mas a cerca nunca vem antes da palavra da equipe"


SEND_OFF = (
    "Todas as cenas já estão comigo. No Ensaio Final o aplicativo junta as gravações das cenas; "
    "vocês ouvem a passagem inteira e, se ainda faltar algum detalhe, a gente acerta isso juntos. "
    "Agora toquem no ponto laranja, no alto da tela, para abrir o Ensaio Final."
)
SEND_OFF_EN = (
    "Every scene is with me now. In the Final Rehearsal the app puts your scene recordings "
    "together; you listen to the whole passage and, if any detail is still missing, we fix it "
    "together. Now tap the orange dot at the top of the screen to open the Final Rehearsal."
)
UNRECORDED = "A cena 3 ainda não tem gravação: no Ensaio Final vocês gravam essa cena lá."
OLD_SEND_OFF = (
    "Ficou inteiro. Agora gravem o ensaio de vocês, na língua de vocês. Toquem no ponto laranja, "
    "no alto da tela, e gravem a passagem cena por cena. Depois, traduzam a gravação pra mim, "
    "frase por frase."
)


def test_the_invitation_to_rehearse_says_the_red_microphone_and_nothing_else_to_do() -> None:
    invites = {"invites_microphone": True}
    assert _turn(guide=f"{FENCE_CLOSE} {MIC}", expect=invites) == []
    assert _turn(guide="Now you can rehearse. Tap the red microphone.", expect=invites) == []
    assert _turn(guide=f"{FENCE_CLOSE} Ensaiem na língua de vocês.", expect=invites) == [
        "the Guide invited the rehearsal without the red-microphone instruction"
    ]
    two_at_once = [
        "the Guide asked for an oral telling-back in the same turn as the microphone (two "
        "instructions at once)"
    ]
    assert _turn(guide=f"{MIC} Depois me contem em português.", expect=invites) == two_at_once
    assert _turn(guide=f"{MIC} Then tell me back in English.", expect=invites) == two_at_once
    assert _turn(guide=f"{MIC} E me contem o que vocês contaram.", expect=invites) == two_at_once


def test_the_send_off_names_the_ensaio_final_and_the_orange_dot_never_the_red_microphone() -> None:
    final = {"send_off_ensaio_final": True}
    missing = [
        "send-off did not send the team to the Ensaio Final by the orange dot (Ensaio Final + "
        "ponto laranja)"
    ]
    assert _turn(guide=SEND_OFF, expect=final) == []
    assert _turn(guide=SEND_OFF_EN, expect=final) == []
    assert _turn(guide="Agora vamos para o Ensaio Final.", expect=final) == missing
    assert _turn(guide=f"{OLD_SEND_OFF} Ou no microfone vermelho.", expect=final) == [
        *missing,
        "send-off named the red microphone (the 2026-09-17 incident: the passage was recorded in "
        "the wrong place)",
    ]


def test_the_send_off_never_asks_for_the_passage_recorded_or_translated_again() -> None:
    again = {"no_record_again": True}

    def told(words: str) -> list[str]:
        return [f'guide told the team to record or translate the passage again: "{words}"']

    assert _turn(guide=OLD_SEND_OFF, expect=again) == told("gravem o ensaio de vocês")
    assert _turn(guide="Toquem no ponto laranja e gravem a passagem.", expect=again) == told(
        "gravem a passagem"
    )
    assert _turn(guide="Gravem o ensaio, na língua de vocês.", expect=again) == told(
        "Gravem o ensaio"
    )
    assert _turn(guide="Depois, traduzam essa gravação pra mim.", expect=again) == told(
        "traduzam essa gravação"
    )
    assert _turn(guide="Now record the whole passage again.", expect=again) == told(
        "record the whole passage again"
    )
    assert _turn(guide="Record your rehearsal, in your own language.", expect=again) == told(
        "Record your rehearsal"
    )
    assert _turn(guide="Then translate your recording for me.", expect=again) == told(
        "translate your recording"
    )
    for kept in (
        SEND_OFF,
        SEND_OFF_EN,
        UNRECORDED,
        MIC,
        "Gravem o ensaio dessa cena de novo.",
        "Gravem o ensaio da cena 2 e traduzam pra mim frase por frase.",
        "Tap the red microphone and record your rehearsal of this scene.",
    ):
        assert _turn(guide=kept, expect=again) == [], kept


def test_the_whole_passage_is_never_asked_for_again_one_scene_still_is() -> None:
    whole = {"no_whole_retelling_request": True}

    def asked(words: str) -> list[str]:
        return [f'guide asked for the whole passage to be told or rehearsed again: "{words}"']

    for request, words in (
        ("Muito bem. Agora contem a passagem inteira pra mim.", "contem a passagem inteira"),
        ("Agora ensaiem a passagem toda, de uma vez só.", "ensaiem a passagem toda"),
        ("Vocês podem contar a história inteira agora?", "podem contar a história inteira"),
        ("Querem recontar a história toda?", "Querem recontar a história toda"),
        ("Agora vamos ensaiar a passagem toda.", "vamos ensaiar a passagem toda"),
        ("Agora contem tudo de novo, do começo ao fim.", "contem tudo de novo, do começo ao fim"),
        ("Now tell me the whole passage.", "tell me the whole passage"),
        (
            "Now tell it all again, from beginning to end.",
            "tell it all again, from beginning to end",
        ),
    ):
        assert _turn(guide=request, expect=whole) == asked(words), request
    for kept in (
        "Ensaiem esta cena de novo, do começo ao fim.",
        "Contem essa parte do começo ao fim.",
        "Ensaiem só esta cena, não a passagem inteira.",
        "Rehearse this scene from beginning to end.",
        "No Ensaio Final vocês vão ouvir a passagem inteira.",
        SEND_OFF,
        "Primeiro eu vou contar a passagem inteira pra vocês.",
        "First I'll tell you the whole passage.",
        "Let me tell you the whole passage first.",
        "Ensaiem esta cena. A passagem inteira fica pro Ensaio Final.",
    ):
        assert _turn(guide=kept, expect=whole) == [], kept


def test_a_send_off_with_a_part_told_only_aloud_says_it_has_no_recording_yet() -> None:
    unrecorded = {"send_off_names_unrecorded_scene": True}
    for said in (
        UNRECORDED,
        "Scene 3 has no recording yet: in the Final Rehearsal you record that scene there.",
        "As cenas 2 e 3 ainda não têm gravação.",
        "a cena 2 nao tem gravacao",
    ):
        assert _turn(guide=said, expect=unrecorded) == [], said
    assert _turn(guide=SEND_OFF, expect=unrecorded) == [
        "send-off did not say that a part told only aloud has no recording yet"
    ]


def test_a_new_fact_is_named_as_something_the_story_does_not_tell() -> None:
    new_fact = {"names_new_fact": True}
    for named in (
        "A história guarda silêncio sobre o motivo.",
        "Ela fica quieta aí de propósito.",
        "Esse medo não vem da história.",
        "Isso a gente não sabe pela história.",
        "A história não explica por que ela voltou.",
        "Isso ficou de fora da história.",
    ):
        assert _turn(guide=named, expect=new_fact) == [], named
    assert _turn(guide="Que bonito: a Noemi voltou porque estava com medo.", expect=new_fact) == [
        "guide did not name the new fact as something the story does not tell"
    ], "aceitar a causa nova como se fosse da história é o incidente"


UNWORKED = json.loads(
    (Path(__file__).parent.parent / "golden/sessions/P10-earlier-passages-status.json").read_text(
        encoding="utf-8"
    )
)["turns"][0]["expect"]["no_recall_of_unworked"]
TOLD_AS_STORY = {"no_recall_of_unworked": UNWORKED, "tells_as_story": True}


def _recalled(sentence: str) -> list[str]:
    return [
        "the voice recalled a passage this team has not worked yet as if the team knew it "
        f"('lembrem' / 'na última parte'): \"{sentence}\""
    ]


def _untold(sentence: str) -> list[str]:
    return [
        "the voice spoke of a passage this team has not worked yet without 'a história conta "
        f'que…\': "{sentence}"'
    ]


def test_a_passage_the_team_has_not_worked_is_never_recalled_as_if_they_knew_it() -> None:
    recall = {"no_recall_of_unworked": UNWORKED}
    pilot = (
        "Lembrem: na última parte, Rute passou a noite no lugar da debulha, aos pés de Boaz, e ele "
        "fez um juramento."
    )
    assert _turn(guide=f"Boa pergunta. {pilot}", expect=recall) == _recalled(pilot), (
        "a fala de abertura do piloto P10, 24/09"
    )
    for frame in (
        "Na parte anterior, o homem jurou pelo Senhor.",
        "Como vocês já sabem, à meia-noite ele se assustou.",
    ):
        assert _turn(guide=frame, expect=recall) == _recalled(frame), frame
    assert _turn(guide="Lembrem que… o homem jurou pelo Senhor.", expect=recall) == _recalled(
        "Lembrem que o homem jurou pelo Senhor."
    ), "a reticência depois do 'que' junta, não termina a frase"
    for kept in (
        "Lembrem que Noemi mandou Rute ir, e a história conta que ele jurou pelo Senhor.",
        "Lembrem da Noemi. Ele jurou pelo Senhor.",
        "Lembrem: na última parte, Noemi mandou Rute descer à eira e deitar aos pés dele.",
    ):
        assert _turn(guide=kept, expect=recall) == [], kept
    assert _turn(guide=pilot, expect={"no_recall_of_unworked": []}) == []


def test_a_passage_the_team_has_not_worked_is_told_her_way_a_historia_conta_que() -> None:
    implicit = "É a mesma pergunta que o homem fez pra Rute no escuro."
    assert _turn(guide=implicit, expect=TOLD_AS_STORY) == _untold(implicit)
    assert _turn(guide=implicit, expect={"no_recall_of_unworked": UNWORKED}) == [], (
        "sem o tells_as_story do roteiro, só a lembrança é falta"
    )
    for told in (
        "A história conta que, naquela noite, Rute pediu proteção, e o homem fez um juramento "
        "pelo Senhor. Agora o dia está chegando.",
        "A história conta que ele jurou pelo Senhor. E à meia-noite ele tinha acordado assustado.",
        "A história conta que… o homem jurou pelo Senhor.",
        "A história conta que Rute fez tudo isso. Ele disse: e agora, minha filha, não tenha medo. "
        "Ele jurou pelo Senhor.",
        "A história conta que a sogra perguntou: quem é você, minha filha? À meia-noite ele tinha "
        "tremido.",
    ):
        assert _turn(guide=told, expect=TOLD_AS_STORY) == [], told
    for reply, sentence in (
        (
            "A história conta que ela chegou em casa e a sogra perguntou: quem é você, minha "
            f"filha? {implicit}",
            implicit,
        ),
        (f"A história não conta por que ela pergunta assim. {implicit}", implicit),
        ("A história nunca conta que ele jurou.", "A história nunca conta que ele jurou."),
        (
            "A história conta que ele jurou pelo Senhor. Agora o dia está chegando. À meia-noite "
            "ele tremeu.",
            "À meia-noite ele tremeu.",
        ),
        (
            "A história conta que Rute fez tudo isso.\n\nNo meio da noite Boaz acordou assustado.",
            "No meio da noite Boaz acordou assustado.",
        ),
        (
            "A história conta que Rute fez tudo isso. É aí que a nossa passagem começa. Ele jurou "
            "pelo Senhor.",
            "Ele jurou pelo Senhor.",
        ),
        (
            "A história conta que ele jurou pelo Senhor. Lembrem do plano de Noemi. À meia-noite "
            "ele tremeu.",
            "À meia-noite ele tremeu.",
        ),
        (f"A história conta que Rute fez tudo isso. {implicit}", implicit),
        (
            "Nesta passagem, a história conta que a sogra perguntou quem ela era. À meia-noite ele "
            "tinha tremido.",
            "À meia-noite ele tinha tremido.",
        ),
    ):
        assert _turn(guide=reply, expect=TOLD_AS_STORY) == _untold(sentence), reply


def test_the_teams_reading_is_received_as_theirs_never_confirmed_by_the_story() -> None:
    theirs = {"team_reading_stays_theirs": True}

    def confirmed(words: str) -> list[str]:
        return [
            "the team's reading was presented as the passage's own (the story confirms it, or "
            f'gives a sign of it): "{words}"'
        ]

    p10 = (
        "Que bom que vocês repararam nisso. É verdade: nessa parte a história não fala o nome de "
        "Deus. E mesmo assim vocês sentiram a esperança crescendo. A própria história dá um sinal "
        "disso. E lá no caminho de volta, Noemi pediu descanso pra elas."
    )
    assert _turn(guide=p10, expect=theirs) == confirmed("A própria história dá um sinal"), (
        "o piloto P10, 24/09, 11:09"
    )
    for said, words in (
        ("É isso mesmo, a história confirma.", "história confirma"),
        ("A história dá um sinal disso: a mulher ainda está de pé.", "história dá um sinal"),
        ("A própria passagem confirma o que vocês sentiram.", "A própria passagem confirma"),
        ("A própria história dá um sinal disso, não é?", "A própria história dá um sinal"),
        ("A história também mostra sinais disso.", "história também mostra sinais"),
        ("The story itself gives a sign of it.", "The story itself gives a sign"),
        ("Yes, the story confirms it.", "story confirms"),
        (
            "A própria história, no fim, dá um sinal disso.",
            "A própria história, no fim, dá um sinal",
        ),
        ("Sim, é isso que a história tá mostrando.", "é isso que a história tá mostrando"),
        ("Sim, é isso que a história tá mostrando, né?", "é isso que a história tá mostrando"),
        ("É isso mesmo: a história mostra essa esperança.", "É isso mesmo: a história mostra"),
        (
            "É verdade, a história mostra isso: a esperança está crescendo.",
            "É verdade, a história mostra isso",
        ),
        (
            "Exatamente, a passagem mostra essa esperança.",
            "Exatamente, a passagem mostra essa esperança",
        ),
        ("Yes, that's what the story is showing.", "that's what the story is showing"),
        ("Yes, the story shows that hope.", "Yes, the story shows that"),
        ("The story itself shows this.", "The story itself shows this"),
        ("The passage gives us a sign of that.", "passage gives us a sign"),
        (
            "Que bom. Exatamente, a passagem mostra essa esperança.",
            "Exatamente, a passagem mostra essa esperança",
        ),
    ):
        assert _turn(guide=said, expect=theirs) == confirmed(words), said
    for kept in (
        "Que bom que vocês trouxeram isso. Vocês estão vendo uma esperança pra Noemi.",
        "A própria história deixa essa pergunta aberta.",
        "A história não confirma nem nega isso.",
        "A própria história não dá sinal disso.",
        "A história não diz se a oração se cumpriu.",
        "Vocês acham que a história confirma isso?",
        "The story does not say whether the story confirms it.",
        "The story itself does not give a sign.",
        "Vocês tiraram isso da própria história, e estão vendo um sinal de esperança.",
        "A própria história deixa isso em aberto, e vocês estão vendo nisso um sinal de esperança.",
        "A própria história deixa isso em aberto e vocês estão vendo nisso um sinal.",
        "A própria história deixa isso em aberto, mas vocês veem nisso um sinal.",
        "A própria história em nenhum momento dá um sinal disso.",
        "A própria história jamais confirma isso.",
        "A própria história fica sem dar sinal nenhum.",
        "Vocês acham que é isso que a história tá mostrando?",
        "É verdade: a história mostra uma família ficando menor.",
        "É isso que a história conta nessa parte: a família sai de Belém.",
        "The story itself gives no sign of it.",
        "The story itself is significant here.",
    ):
        assert _turn(guide=kept, expect=theirs) == [], kept


def test_boaz_never_sleeps_nor_wakes_at_the_threshing_floor_night() -> None:
    asleep = {"boaz_never_asleep": True}
    for said, words in (
        (
            (
                "A história conta só o que conta: ela descobre o lugar dos pés dele, se deita, "
                "ele acorda assustado, e depois é só conversa até de manhã."
            ),
            (
                "que conta: ela descobre o lugar dos pés dele, se deita, ele acorda assustado, "
                "e depois é só conv"
            ),
        ),
        (
            (
                "E tem uma coisa que a história faz de propósito: essas são as mesmas palavras "
                "que Boaz perguntou na noite, na eira, quando acordou assustado: quem é você?"
            ),
            (
                "esmas palavras que Boaz perguntou na noite, na eira, quando acordou assustado: "
                "quem é você?"
            ),
        ),
        (
            "No meio da noite o homem acordou e viu uma mulher deitada aos pés dele.",
            "No meio da noite o homem acordou e viu uma mulher deitada aos",
        ),
        (
            (
                "Cena 2: no meio da noite, Boaz acorda assustado, pergunta quem é, e Rute faz o "
                "pedido."
            ),
            "Cena 2: no meio da noite, Boaz acorda assustado, pergunta quem é, e",
        ),
        (
            "Enquanto ele dorme, Rute descobre o lugar dos pés dele.",
            "Enquanto ele dorme, Rute descobre o lugar dos pé",
        ),
        (
            "Ele está dormindo, e ela se deita aos pés dele.",
            "Ele está dormindo, e ela se deita aos pés dele.",
        ),
        (
            "Boaz come, bebe e vai dormir no fim do monte de grão.",
            "Boaz come, bebe e vai dormir no fim do monte de grão.",
        ),
        (
            "Ele pegou no sono.",
            "Ele pegou no sono.",
        ),
        (
            "Boaz adormeceu depois de comer.",
            "Boaz adormeceu depois de comer.",
        ),
        (
            "Ela esperou até ele dormir.",
            "Ela esperou até ele dormir.",
        ),
        (
            "Ela chegou devagar, sem acordar ele.",
            "Ela chegou devagar, sem acordar ele.",
        ),
        (
            "Ela chegou devagarinho pra não o acordar.",
            "Ela chegou devagarinho pra não o acordar.",
        ),
        (
            "Ela se deitou sem acordá-lo.",
            "Ela se deitou sem acordá-lo.",
        ),
        (
            "Ele não dormiu a noite toda.",
            "Ele não dormiu a noite toda.",
        ),
        (
            "No meio da noite, acordou assustado e viu a mulher.",
            "No meio da noite, acordou assustado e viu a mulher.",
        ),
        (
            "A história não diz o nome dele. Ele acordou assustado.",
            "Ele acordou assustado.",
        ),
        (
            "At midnight he woke up and was afraid.",
            "At midnight he woke up and was afraid.",
        ),
        (
            "The man was asleep at the end of the heap.",
            "The man was asleep at the end of the heap.",
        ),
    ):
        assert _turn(guide=said, expect=asleep) == [
            f'the voice made Boaz sleep or wake at the threshing-floor night: "{words}" — P09 '
            "R19 / P10 R14: he lies down (3:7), trembles and twists (3:8); the text never says he "
            "slept or woke"
        ], said
    for kept in (
        (
            "O Boaz comeu e bebeu, o coração dele ficou alegre, e ele foi se deitar no fim do "
            "monte de grão."
        ),
        (
            "No meio da noite o homem estremeceu e se virou, e havia uma mulher deitada no "
            "lugar dos pés dele."
        ),
        "De acordo com o costume, o resgatador mais próximo vem primeiro.",
        "Eles fizeram um acordo.",
        "A Noemi concordou.",
        "Rute recordou o que a sogra tinha dito.",
        "Ela dormiu aos pés dele até de manhã.",
        "Rute se deitou aos pés dele e dormiu ali.",
        "Onde você dormir, eu durmo.",
        "Durma aqui esta noite.",
        "A história não diz se ele dormiu.",
        "A história não conta que ele acordou; ela conta que o homem estremeceu.",
        "The story does not say that he slept.",
        "The woman slept at his feet.",
        "Ela, com o sono leve, se deitou.",
    ):
        assert _turn(guide=kept, expect=asleep) == [], kept


F1 = "Vamos começar pela Familiarização. Primeiro eu conto a passagem inteira."
F3 = (
    "O que chamou a atenção de vocês nessa passagem? Conversem entre vocês. Se tiver alguma "
    "dúvida, me perguntem. Quando estiverem prontos, me digam e a gente vai pra Internalização da "
    "primeira cena."
)
F3_EN = (
    "What caught your attention in this passage? Talk it over among yourselves. If you have any "
    "questions, ask me. When you are ready, tell me and we will move to Internalization of the "
    "first scene."
)
F4 = (
    "Se tiver alguma dúvida, me perguntem. Quando estiverem prontos, me digam e a gente vai pra "
    "Internalização da primeira cena."
)


def test_the_whole_passage_asked_for_mid_session_is_told_without_f1_and_without_f3() -> None:
    mid_session = {"no_familiarization_lines": True}

    def said(line: str) -> list[str]:
        return [
            "the whole passage asked for mid-session was told with the Familiarization's "
            f"{line} — D7 (a): without F1 and without F3, the moment unchanged"
        ]

    assert _turn(guide=f"(fixture) a passagem inteira. {CLOSING_TAIL}", expect=mid_session) == []
    assert _turn(guide=f"(fixture). {F4}", expect=mid_session) == [], "o F4 sozinho não é F1 nem F3"
    assert _turn(guide=f"{F1} (fixture)", expect=mid_session) == said("first words (F1)")
    broken = F3.replace("? ", "?\n")
    assert _turn(guide=f"(fixture).\n{broken} (fixture)", expect=mid_session) == said(
        "closing (F3)"
    )
    assert _turn(guide=f"(fixture). {F3_EN}", expect=mid_session) == said("closing (F3)")


def test_a_scene_of_todays_passage_is_a_cena_never_a_parte() -> None:
    cena = {"scene_word_cena": True}
    for spoken, words in (
        ("Vamos abrir a primeira parte.", "primeira parte"),
        ("Isso fica pra próxima parte.", "próxima parte"),
        ("Nessa parte, a família sai de Belém.", "Nessa parte"),
        ("Mas isso já é a terceira parte.", "terceira parte"),
        ("E Rute ficou de fora dessa parte, do jeito que a história conta.", "dessa parte"),
        ("Vamos pra primeira parte da passagem.", "primeira parte"),
    ):
        assert _turn(guide=spoken, expect=cena) == [
            f'the voice called a scene of today\'s passage "parte" ("{words}") — D1 (c): "cena"'
        ], spoken
    for kept in (
        "Vamos pra Internalização da cena 1.",
        "Quando trabalharmos essa parte, vocês vão ver.",
        "O que vem depois, a história ainda vai contar. Quando a gente trabalhar essa parte, a "
        "gente vive isso junto.",
        "Lembrem: na última parte…",
        "O resto fica de fora, faz parte de outra história.",
        "Da parte dela, nada foi dito.",
        "No Ensaio Final vocês regravam uma parte.",
        "Essa é a primeira parte do livro de Rute.",
        "Essa cena é a primeira parte da noite, e ela é só movimento.",
        "Nessa parte da história ninguém fala.",
    ):
        assert _turn(guide=kept, expect=cena) == [], kept


KICKOFF = (
    "Bom dia. Eu sou o Facilitador Digital. Quando quiserem falar comigo, toquem no círculo; "
    f"toquem de novo quando terminarem. {F1} (a passagem inteira). Essa passagem tem quatro "
    "cenas. Cena 1: (fixture). Cena 2: (fixture). Cena 3: (fixture). Cena 4: (fixture).\n\n"
    f"{F3}"
)
FAMILIARIZATION = {"familiarization_entrance": True, "familiarization_closing": True}
NO_F3 = (
    "the Familiarization turn does not end with its closing, said whole ('O que chamou a atenção "
    "de vocês nessa passagem? … a gente vai pra Internalização da primeira cena.')"
)


def _in_four_scenes(guide: str, **expect: Any) -> list[str]:
    return _turn(guide=guide, expect=expect, parts=4)


def test_the_familiarization_opens_with_f1_and_ends_with_f3_said_whole() -> None:
    assert _turn(guide=KICKOFF, expect=FAMILIARIZATION) == []
    assert _turn(guide=f"(fixture). {F3_EN}", expect={"familiarization_closing": True}) == []
    assert _turn(guide=F3, expect=FAMILIARIZATION) == [
        "the Familiarization turn does not carry its first words, word for word ('Vamos começar "
        "pela Familiarização. Primeiro eu conto a passagem inteira.')"
    ]
    draft = F3.replace("nessa passagem", "nessa história")
    assert _turn(guide=draft, expect={"familiarization_closing": True}) == [NO_F3], (
        "o rascunho dizia 'nessa história'"
    )
    assert _turn(guide=f"{F3} Vamos lá?", expect={"familiarization_closing": True}) == [NO_F3]


def test_a_take_up_in_the_familiarization_ends_with_f4() -> None:
    tail = {"familiarization_tail": True}
    assert _turn(guide=f"Boa pergunta. (fixture). {F4}", expect=tail) == []
    assert _turn(guide=f"(fixture). {F3}", expect=tail) == [], "o F3 também termina com o F4"
    assert _turn(guide=f"(fixture). {CLOSING_TAIL}", expect=tail) == [
        "the take-up in the Familiarization does not end with its closing's last two sentences "
        "('Se tiver alguma dúvida, me perguntem. Quando estiverem prontos, me digam e a gente vai "
        "pra Internalização da primeira cena.')"
    ], "a cauda do fechamento da cena não é o F4"


def test_no_scene_is_opened_in_the_familiarization_before_the_teams_word() -> None:
    def opened(words: str) -> list[str]:
        return [f'a scene was opened in the Familiarization, before the team\'s word: "{words}"']

    p10_turn_3 = (
        "Vocês viram bem: (fixture). Guardem isso na cabeça enquanto a gente vai por cenas. "
        f"Vamos pra Internalização da cena 1. (fixture) a cena. {F4}"
    )
    assert _in_four_scenes(p10_turn_3, familiarization_tail=True) == opened(
        "Vamos pra Internalização da cena 1. (fixture) a cena. Se tiv"
    ), "o piloto P10, turno 3: respondeu e abriu a cena 1 no mesmo turno"
    assert _in_four_scenes(
        f"(fixture). {FENCE_OPEN} (fixture). {FENCE_CLOSE} {F4}", familiarization_tail=True
    ) == opened(FENCE_OPEN)
    assert _in_four_scenes(f"(fixture) a cena. {PART_CLOSING}", familiarization_closing=True) == [
        NO_F3,
        *opened("the part-opening closing"),
    ]
    assert _in_four_scenes(f"(fixture). {FENCE_CLOSE} {F4}", familiarization_tail=True) == opened(
        "a call to rehearse"
    )
    assert _in_four_scenes(KICKOFF, **FAMILIARIZATION) == [], (
        "o '…pra Internalização da primeira cena.' do F3 não abre cena nenhuma"
    )


def test_a_scene_opening_carries_its_numbered_internalization_line_and_no_other() -> None:
    no_line = (
        "the scene opening does not carry its numbered Internalization line, word for word "
        "('Vamos pra Internalização da cena 2.')"
    )
    assert _in_four_scenes("Vamos pra Internalização da cena 2. (fixture)", part_entrance=2) == []
    assert _in_four_scenes("Let's move to Internalization of scene 2.", part_entrance=2) == []
    assert _in_four_scenes("Agora vamos pra Internalização da segunda cena.", part_entrance=2) == [
        no_line
    ], "o detector lê o ordinal, a checagem quer as palavras aprovadas"
    assert _in_four_scenes("Vamos pra Internalização da cena 3.", part_entrance=2) == [
        no_line,
        "an Internalization line names another scene than the one being opened (2): 3",
    ]
    assert _in_four_scenes(
        "Vamos pra Internalização da cena 2. Agora vamos pra Internalização da última parte.",
        part_entrance=2,
    ) == ["an Internalization line names another scene than the one being opened (2): 4"], (
        "a última parte é a cena K da passagem"
    )
    assert _in_four_scenes(
        "Vamos pra Internalização da cena 2. Vamos pra Internalização da cena 7.", part_entrance=2
    ) == ["an Internalization line names another scene than the one being opened (2): 7"], (
        "um número fora da passagem ainda é lido, e relatado"
    )
    for not_a_line in (
        "Vamos pra Internalização da cena 2. E depois vamos pra Internalização da cena 3.",
        "Vamos pra Internalização da cena 2. Vamos pra Internalização da cena 3 e depois da 4.",
        "Vamos pra Internalização da cena 2. Vamos pra Internalização da cena 3?",
        "Vamos pra Internalização da cena 2. Depois vamos pra Internalização da cena 3.",
        "Vamos pra Internalização da cena 2. Não vamos pra Internalização da cena 3 ainda.",
        "Vamos pra Internalização da cena 2. Mas isso já é a terceira parte.",
    ):
        assert _in_four_scenes(not_a_line, part_entrance=2) == [], not_a_line
    for tolerated in (
        "Vamos pra Internalização da cena 2. Então, vamos pra Internalização da cena 3.",
        "Vamos pra Internalização da cena 2. Agora vamos pra Internalização da cena 3, o verso 14.",
        "Vamos pra Internalização da cena 2. Vamos para a Internalização da parte três.",
        "Vamos pra Internalização da cena 2. Let\u2019s go to the Internalization of part three.",
    ):
        assert _in_four_scenes(tolerated, part_entrance=2) == [
            "an Internalization line names another scene than the one being opened (2): 3"
        ], tolerated


def test_the_first_fence_of_a_scene_follows_its_articulation_line() -> None:
    no_line = (
        "the first fence of scene 2 does not follow its Articulation line, word for word ('Vamos "
        "pra Articulação da cena 2.' right before 'Agora vou dizer tudo o que deve entrar no "
        "ensaio de vocês.')"
    )
    assert (
        _in_four_scenes(
            f"Vamos pra Articulação da cena 2. {FENCE_OPEN} (fixture)", articulation_entrance=2
        )
        == []
    )
    english = (
        "Let's move to Articulation of scene 2.\nNow I will say everything that should go into "
        "your rehearsal."
    )
    assert _in_four_scenes(english, articulation_entrance=2) == []
    assert _in_four_scenes(
        f"Vamos pra Articulação da cena 2. (fixture) um comentário. {FENCE_OPEN}",
        articulation_entrance=2,
    ) == [no_line]
    assert _in_four_scenes("Vamos pra Articulação da cena 2.", articulation_entrance=2) == [no_line]
    assert _in_four_scenes(
        f"Vamos pra Articulação da cena 3. {FENCE_OPEN}", articulation_entrance=2
    ) == [
        no_line,
        "an Articulation line names another scene than the one being rehearsed (2): 3",
    ]


def test_the_reply_says_where_the_team_is_in_her_words_and_names_no_other_moment() -> None:
    j1 = (
        "Estamos na Articulação da cena 2. Primeiro a gente termina essa cena; depois vem a cena "
        f"3. (fixture) {FENCE_OPEN} (fixture) {FENCE_CLOSE}"
    )
    assert _in_four_scenes(j1, where_we_are=2) == [], "o J1 (ii): 'depois vem a cena 3' não é linha"
    assert _in_four_scenes("Estamos na Internalização da cena 1.", where_we_are=1) == []
    assert _in_four_scenes("We are in Articulation of scene 2.", where_we_are=2) == []
    assert _in_four_scenes("Estamos na Familiarização. (fixture)", where_we_are="F") == []
    assert _in_four_scenes("Ainda estamos na Articulação da cena 2.", where_we_are=2) == [
        "the reply does not say where the team is, word for word ('Estamos na Articulação da "
        "cena 2.' or 'Estamos na Internalização da cena 2.')"
    ], "o 'Ainda estamos' do rascunho é tolerância do detector, não as palavras aprovadas"
    assert _in_four_scenes("Estamos na Articulação da cena 2.", where_we_are="F") == [
        "the reply does not say where the team is, word for word ('Estamos na Familiarização.')",
        "a where-we-are line names another moment or scene than the one the team is in (F): 2",
    ]
    assert _in_four_scenes("Estamos na Familiarização.", where_we_are=2) == [
        "the reply does not say where the team is, word for word ('Estamos na Articulação da "
        "cena 2.' or 'Estamos na Internalização da cena 2.')",
        "a where-we-are line names another moment or scene than the one the team is in (2): F",
    ]


def test_no_where_we_are_line_is_said_after_the_send_off() -> None:
    assert _in_four_scenes(SEND_OFF, no_where_we_are=True) == []
    assert _in_four_scenes("Não estamos na Articulação da cena 2.", no_where_we_are=True) == []
    assert _in_four_scenes(
        "Não, ainda estamos na Internalização da cena 2. We're still in Familiarization.",
        no_where_we_are=True,
    ) == ["a where-we-are line was said after the send-off (2, F)"]
    assert _in_four_scenes(
        "We are in Familiarization. Estamos na Articulação da cena 2.", no_where_we_are=True
    ) == ["a where-we-are line was said after the send-off (F, 2)"], "na ordem em que a sala ouviu"


F = Moment("familiarization")
FC = Moment("familiarization", closed=True)
EF = Moment("ensaio_final")


def _i(part: int) -> Moment:
    return Moment("internalization", part)


def _a(part: int) -> Moment:
    return Moment("articulation", part)


I1_LINE = "Vamos pra Internalização da cena {}."
A1_LINE = "Vamos pra Articulação da cena {}."
SEND_OFF_LAST = "Agora toquem no ponto laranja, no alto da tela, para abrir o Ensaio Final."
FENCE = f"{FENCE_OPEN} (fixture) a cena. {FENCE_CLOSE} {MIC}"
CLOSE = f"(fixture). {PART_CLOSING}"


def _after(
    moment: Moment,
    reply: str,
    came_back: tuple[int, ...] = (),
    *,
    unmarked_now: bool = False,
    outcome: str = "pass",
) -> Moment:
    return moment_after_reply(
        moment,
        reply,
        outcome=outcome,
        parts=4,
        came_back=list(came_back),
        unmarked_now=unmarked_now,
    )


def _arriving(moment: Moment | None, part: int, *, heard: int = 1) -> Moment | None:
    return moment_at_turn_start(moment, heard=heard, parts=4, arriving=part)


def test_her_moment_starts_in_the_familiarization_and_follows_the_lines_the_voice_said() -> None:
    assert moment_at_turn_start(None, heard=0, parts=4, arriving=None) == F
    assert moment_at_turn_start(None, heard=2, parts=4, arriving=None) is None, "sessão antiga"
    assert moment_at_turn_start(None, heard=0, parts=0, arriving=None) is None
    assert _after(F, I1_LINE.format(2)) == _i(2)
    assert _after(F, A1_LINE.format(3)) == _a(3)
    assert _after(F, f"(fixture). {FENCE}") == F, "a cerca na Familiarização não tem número"
    assert _after(F, f"(fixture). {F3}") == FC
    assert _after(FC, CLOSE) == _i(1), "o fechamento depois do F3 abre a cena 1"
    assert _after(F, f"(fixture). {SEND_OFF_LAST}") == EF
    assert _after(_i(2), f"(fixture). {FENCE}") == _a(2)
    assert _after(_i(2), CLOSE) == _i(2), "o fechamento é a última fala da própria abertura"
    assert _after(_a(2), A1_LINE.format(2)) == _a(2)
    assert _after(_a(2), A1_LINE.format(3)) == _a(3)
    assert _after(_a(2), "Estamos na Internalização da cena 2.") == _i(2)
    assert _after(_a(2), "Estamos na Familiarização.") == F
    assert _after(FC, "Estamos na Familiarização.") == FC
    assert _after(_i(2), I1_LINE.format(9)) == _i(2), "um número fora da passagem não move nada"
    assert _after(_i(2), f"{I1_LINE.format(3)} {FENCE} {SEND_OFF_LAST}", outcome="fail_safe") == (
        _i(2)
    ), "uma fala enlatada não muda o momento"
    assert _after(_i(2), I1_LINE.format(3), outcome="corrected") == _i(3)
    assert _after(_a(1), f"{I1_LINE.format(2)} (fixture) a cena. {FENCE}") == _a(2), (
        "o que a sala ouviu por último"
    )


def test_her_closing_moves_on_only_when_the_part_came_back_and_never_after_the_send_off() -> None:
    assert _after(_a(2), CLOSE, (2,)) == _i(3)
    assert _after(_a(2), CLOSE, (1,)) == replace(_a(2), numberless_opening=True), (
        "reabrir a mesma cena pra entender nunca põe o próximo número na tela"
    )
    assert _after(_a(1), CLOSE, unmarked_now=True) == _i(2), "o P06 T9"
    assert _after(_a(4), CLOSE, (4,)) == _a(4), "depois da última cena"
    assert _after(
        _a(1), f"{I1_LINE.format(2)} (fixture) a cena. {FENCE} {PART_CLOSING}", (1, 2)
    ) == _a(2)
    old = (
        "(fixture). O que chamou a atenção de vocês nessa parte? Conversem entre vocês. Essa parte "
        "ficou clara? Se tiver alguma dúvida, me perguntem. Se já entenderam, me digam e a gente "
        "vai pro ensaio."
    )
    assert _after(_a(1), old, (1,)) == _i(2), "o fechamento de 23/09 ainda é lido"
    assert _after(EF, f"{I1_LINE.format(3)} (fixture) a cena. {PART_CLOSING}") == EF
    assert _after(EF, "Estamos na Articulação da cena 2.") == EF
    assert _after(EF, f"(fixture). {FENCE}") == EF
    assert _after(EF, CLOSE, (1, 2, 3)) == EF


def test_a_scene_rehearsal_moves_her_moment_only_for_the_scene_that_is_open() -> None:
    assert _arriving(_i(3), 3) == _a(3)
    assert _arriving(_i(3), 2) == _i(3)
    assert _arriving(_i(2), 3) == _i(2), (
        "uma cena contada adiante fica guardada, o momento não muda"
    )
    assert _arriving(_a(2), 2) == _a(2)
    assert _arriving(F, 1) == F
    assert _arriving(EF, 2) == EF
    assert _arriving(_i(2), 9) == _i(2)
    assert moment_at_turn_start(None, heard=0, parts=4, arriving=2) == F


def test_a_numberless_opening_lets_the_next_scenes_rehearsal_move_her_moment() -> None:
    opened = _after(_a(2), CLOSE)
    assert opened == replace(_a(2), numberless_opening=True)
    assert _arriving(opened, 3) == _a(3), "a cena 3 foi aberta, só o número se perdeu"
    assert _arriving(opened, 4) == opened
    assert _after(F, CLOSE) == replace(F, numberless_opening=True)
    assert _arriving(replace(F, numberless_opening=True), 1) == _a(1)
    assert _after(_i(2), CLOSE) == _i(2), "nunca na Internalização"
    assert _after(opened, "Estamos na Articulação da cena 2.") == _a(2), (
        "uma linha numerada diz de novo onde a sala está"
    )
    assert _after(opened, "(fixture) uma resposta.") == opened
    assert _after(replace(_i(2), numberless_opening=True), f"(fixture). {FENCE}") == replace(
        _a(2), numberless_opening=True
    )
    assert _after(_a(2), f"{I1_LINE.format(9)} (fixture). {PART_CLOSING}", (2,)) == (opened), (
        "um número fora da passagem não amarra nada"
    )
    assert _after(
        _a(2), f"Estamos na Articulação da cena 2. (fixture). {PART_CLOSING}", (2,)
    ) == _a(2)


def test_the_next_scene_is_never_opened_before_this_one_came_back_whole() -> None:
    def opened(guide: str, before: Moment | None) -> list[str]:
        return _turn(guide=guide, expect={"no_next_part": True}, moment_before=before)

    assert opened(I1_LINE.format(2), _a(2)) == [], "reabrir a mesma cena pra entender"
    assert opened(I1_LINE.format(3), _a(2)) == [
        "the next scene was opened before this scene came back whole (Internalization line for "
        "scene 3)"
    ]
    assert opened(I1_LINE.format(1), F) == [
        "the next scene was opened before this scene came back whole (Internalization line for "
        "scene 1)"
    ]
    assert opened(I1_LINE.format(1), EF) == [
        "the next scene was opened before this scene came back whole (Internalization line for "
        "scene 1)"
    ], "depois da despedida, qualquer abertura é cedo demais"
    assert opened(I1_LINE.format(0), F) == [], "a Familiarização é a cena 0"
    assert opened(I1_LINE.format(0), EF) == [
        "the next scene was opened before this scene came back whole (Internalization line for "
        "scene 0)"
    ]


def test_the_moment_her_script_expects_after_the_reply_is_the_one_the_reply_left() -> None:
    def left(after: Moment | None, wanted: str | list[str]) -> list[str]:
        return _turn(guide=OPENS_MORE, expect={"moment_after": wanted}, moment_after=after)

    assert left(_i(2), "I2") == []
    assert left(_a(3), ["I3", "A3"]) == []
    assert left(FC, "F") == []
    assert left(EF, "EF") == []
    assert left(_a(2), "I3") == ["the app's moment after this reply is A2, not I3"]
    assert left(_i(2), ["F", "I1"]) == ["the app's moment after this reply is I2, not F or I1"]
    assert left(None, "F") == [
        "the app kept no moment for this session (moment_after cannot be read)"
    ]


def test_every_fault_of_one_turn_at_her_freeze_comes_back_in_her_order() -> None:
    everything = (
        "Ensaiem agora. "
        "A Rute casou com Malom, diz o mapa. "
        "Isso é acréscimo. "
        "Agora vou dizer tudo o que deve entrar no ensaio de vocês. "
        "Reparem na fome. "
        "Agora podem ensaiar. "
        "Lembrem disso. "
        "Gravem a passagem inteira. "
        "Contem a passagem inteira pra mim. "
        "A própria história dá um sinal disso. "
        "Vamos começar pela Familiarização. "
        "Primeiro eu conto a passagem inteira. "
        "Vamos pra Internalização da cena 3. "
        "Vamos pra Articulação da cena 3. "
        "Estamos na Articulação da cena 3. "
        "Nessa parte ele dormiu. "
        "Amém."
    )
    expect = {
        "no_fail_safe": True,
        "no_rehearsal_invite": True,
        "no_pairing": True,
        "send_off_record": True,
        "offers_choice": True,
        "no_choice_offer": True,
        "send_off_names": ["quem é você"],
        "send_off_scene_by_scene": True,
        "accepts_telling": True,
        "fenced_rehearsal": True,
        "part_opening_closing": True,
        "take_up_closing": True,
        "invites_microphone": True,
        "send_off_ensaio_final": True,
        "no_record_again": True,
        "no_whole_retelling_request": True,
        "offers_choice_final": True,
        "send_off_names_unrecorded_scene": True,
        "names_new_fact": True,
        "team_reading_stays_theirs": True,
        "familiarization_entrance": True,
        "familiarization_closing": True,
        "familiarization_tail": True,
        "part_entrance": 2,
        "articulation_entrance": 2,
        "where_we_are": 2,
        "no_next_part": True,
        "no_where_we_are": True,
        "moment_after": "I2",
        "no_familiarization_lines": True,
        "scene_word_cena": True,
        "boaz_never_asleep": True,
    }
    assert _turn(
        guide=everything,
        outcome="fail_safe",
        expect=expect,
        previous_guide="",
        moment_before=_i(2),
        moment_after=_a(3),
    ) == [
        "fail_safe voiced in reply to a turn that must be answered",
        "rehearsal invited on a turn where the team asked to understand first",
        "possible Ruth↔Mahlon pairing voiced (judge must confirm)",
        (
            "guide did not offer the choice (contar de novo OU seguir pra gravação) on a second "
            "near-complete telling"
        ),
        ("send-off did not repeat the detail the team carries into the recording: /quem é você/i"),
        "send-off did not tell the team to record scene by scene",
        'a faithful telling in other words was not accepted (meaning, not form): "acréscimo"',
        'commentary inside the fenced rehearsal block: "Reparem"',
        "commentary after the fence's closing line",
        (
            "the part opening does not end with the fixed closing ('O que chamou a atenção de "
            "vocês nessa cena? … a gente vai pro ensaio.')"
        ),
        "the fenced block was given in the same turn that opens a part",
        (
            "the reply to the team's comment or question does not end with the closing's last "
            "two sentences ('Se tiver alguma dúvida, me perguntem. Se já entenderam, me digam e "
            "a gente vai pro ensaio.')"
        ),
        "the fenced block was given before the team said it was ready",
        "the Guide invited the rehearsal without the red-microphone instruction",
        (
            "send-off did not send the team to the Ensaio Final by the orange dot (Ensaio Final "
            "+ ponto laranja)"
        ),
        'guide told the team to record or translate the passage again: "Gravem a passagem"',
        (
            'guide asked for the whole passage to be told or rehearsed again: "Contem a '
            'passagem inteira"'
        ),
        (
            "guide did not offer the choice (ensaiar esta cena mais uma vez OU seguir e acertar "
            "no Ensaio Final)"
        ),
        "send-off did not say that a part told only aloud has no recording yet",
        "guide did not name the new fact as something the story does not tell",
        (
            "the team's reading was presented as the passage's own (the story confirms it, or "
            'gives a sign of it): "A própria história dá um sinal"'
        ),
        (
            "the Familiarization turn does not end with its closing, said whole ('O que chamou "
            "a atenção de vocês nessa passagem? … a gente vai pra Internalização da primeira "
            "cena.')"
        ),
        (
            "the take-up in the Familiarization does not end with its closing's last two "
            "sentences ('Se tiver alguma dúvida, me perguntem. Quando estiverem prontos, me "
            "digam e a gente vai pra Internalização da primeira cena.')"
        ),
        (
            "a scene was opened in the Familiarization, before the team's word: \"Vamos pra "
            'Internalização da cena 3. Vamos pra Articulação da"'
        ),
        (
            "the scene opening does not carry its numbered Internalization line, word for word "
            "('Vamos pra Internalização da cena 2.')"
        ),
        "an Internalization line names another scene than the one being opened (2): 3",
        (
            "the first fence of scene 2 does not follow its Articulation line, word for word "
            "('Vamos pra Articulação da cena 2.' right before 'Agora vou dizer tudo o que deve "
            "entrar no ensaio de vocês.')"
        ),
        "an Articulation line names another scene than the one being rehearsed (2): 3",
        (
            "the reply does not say where the team is, word for word ('Estamos na Articulação "
            "da cena 2.' or 'Estamos na Internalização da cena 2.')"
        ),
        "a where-we-are line names another moment or scene than the one the team is in (2): 3",
        (
            "the next scene was opened before this scene came back whole (Internalization line "
            "for scene 3)"
        ),
        "a where-we-are line was said after the send-off (3)",
        "the app's moment after this reply is A3, not I2",
        (
            "the whole passage asked for mid-session was told with the Familiarization's first "
            "words (F1) — D7 (a): without F1 and without F3, the moment unchanged"
        ),
        ('the voice called a scene of today\'s passage "parte" ("Nessa parte") — D1 (c): "cena"'),
        (
            'the voice made Boaz sleep or wake at the threshing-floor night: "Nessa parte ele '
            'dormiu." — P09 R19 / P10 R14: he lies down (3:7), trembles and twists (3:8); the '
            "text never says he slept or woke"
        ),
        "says 'o mapa' / 'the map' to the team",
        "religious farewell of its own",
    ], "a ordem dela é a ordem de mechanicalChecks em run.ts a 18fa7c4"


def test_her_word_edge_under_iu_counts_the_long_s_and_the_kelvin_sign_as_letters() -> None:
    assert _turn(guide="Vocês nem\u017f acréscimo.", expect={"accepts_telling": True}) == [
        'a faithful telling in other words was not accepted (meaning, not form): "acréscimo"'
    ], (
        "sob iu o \u017f é letra pro \\b dela: 'nem\u017f' não é 'nem', e o acréscimo não está "
        "negado"
    )
    assert _turn(guide="Vocês nem\u212a acréscimo.", expect={"accepts_telling": True}) == [
        'a faithful telling in other words was not accepted (meaning, not form): "acréscimo"'
    ]
    assert _turn(
        guide="A história\u017f conta que ele jurou.",
        expect={"no_recall_of_unworked": ["jurou"], "tells_as_story": True},
    ) == [
        "the voice spoke of a passage this team has not worked yet without 'a história conta "
        'que…\': "A história\u017f conta que ele jurou."'
    ], "'a história\u017f' não é a moldura dela"
    assert (
        _turn(
            guide="A história não diz. Ele \u017fjurou.",
            expect={"no_recall_of_unworked": [r"\bjurou"], "tells_as_story": True},
        )
        == []
    ), "as marcas do roteiro dela também são iu"
    assert _turn(guide="Segundo o mapa\u017f, a família era de Belém.", expect={}) == [
        "says 'o mapa' / 'the map' to the team"
    ], "sob i sem u o \\b dela é ASCII: o \u017f não é letra e 'o mapa' termina ali"
    assert _turn(guide="Segundo o mapa\u212a, a família era de Belém.", expect={}) == [
        "says 'o mapa' / 'the map' to the team"
    ]
    assert (
        _turn(
            guide=f"Toquem no \u017fmicrofone vermelho. {PART_CLOSING}",
            expect={"part_opening_closing": True},
        )
        == []
    ), "'\u017fmicrofone' não é o microfone vermelho pro \\b dela"
    assert _turn(
        guide="Contem a \u017fcena da passagem inteira.",
        expect={"no_whole_retelling_request": True},
    ) == [
        'guide asked for the whole passage to be told or rehearsed again: "Contem a \u017fcena da '
        'passagem inteira"'
    ], "'\u017fcena' não é uma cena: o pedido é da passagem inteira"
