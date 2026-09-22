"""What the room still reads for itself: practice reported, consent given, empty answers.

The rehearsal invitation is the Guide's own sentence now, so the invitations written here
are ordinary Guide lines rather than a fixed prompt imported from the app. What the reader
asks of them is unchanged: it has to name the rehearsal, the team's own language, and the
word it wants back.
"""

from app.services.internalization_room.comprehension.practice import (
    confirms_completed_mother_tongue_practice,
    guide_invited_mother_tongue_practice,
    is_bare_polar_answer,
    is_semantically_empty_answer,
    scenes_practiced_by_the_report_the_guide_invited,
)

INVITATION = {
    "pt": "Ensaiem esta cena juntos na língua de vocês; quando terminarem, digam pronto.",
    "en": "Rehearse this scene together in your own language; when you have finished, say done.",
    "es": "Ensayen juntos esta escena en su lengua; cuando terminen, digan listo.",
}


def test_pronto_after_the_exact_practice_prompt_confirms() -> None:
    assert confirms_completed_mother_tongue_practice(INVITATION["pt"], "pronto")


def test_a_bare_sim_confirms_only_a_direct_practice_question() -> None:
    assert not confirms_completed_mother_tongue_practice("O que aconteceu depois?", "sim")
    assert confirms_completed_mother_tongue_practice(
        "Vocês já ensaiaram esta cena na língua de vocês?", "sim"
    )


def test_a_denied_practice_never_confirms() -> None:
    assert not confirms_completed_mother_tongue_practice(
        INVITATION["pt"], "não terminamos de ensaiar na nossa língua"
    )


def test_a_future_plan_never_confirms() -> None:
    assert not confirms_completed_mother_tongue_practice(
        "Vocês já ensaiaram esta cena na língua de vocês?",
        "vamos ensaiar essa cena na língua de vocês depois",
    )


def test_a_plain_report_of_finished_practice_confirms() -> None:
    assert confirms_completed_mother_tongue_practice(INVITATION["pt"], "já ensaiamos")


def test_the_completion_word_confirms_inside_a_longer_utterance() -> None:
    assert confirms_completed_mother_tongue_practice(INVITATION["pt"], "pronto, terminamos")
    assert confirms_completed_mother_tongue_practice(
        INVITATION["pt"],
        "a gente leu, depois ensaiou junto, pronto, pode seguir",
    )


def test_asking_about_practice_never_confirms() -> None:
    assert not confirms_completed_mother_tongue_practice(INVITATION["pt"], "já ensaiamos?")
    assert not confirms_completed_mother_tongue_practice(
        INVITATION["pt"], "a gente tem que ensaiar agora?"
    )


def test_a_postponed_practice_never_confirms() -> None:
    assert not confirms_completed_mother_tongue_practice(
        INVITATION["pt"], "acho que a gente pode ensaiar depois"
    )
    assert not confirms_completed_mother_tongue_practice(INVITATION["pt"], "ainda não")


def test_a_negated_practice_never_confirms() -> None:
    assert not confirms_completed_mother_tongue_practice(INVITATION["pt"], "ainda não ensaiamos")
    assert not confirms_completed_mother_tongue_practice(INVITATION["pt"], "não, pronto não")
    assert not confirms_completed_mother_tongue_practice(INVITATION["pt"], "não, pronto")
    assert not confirms_completed_mother_tongue_practice(INVITATION["pt"], "sim, mas ainda não")
    assert not confirms_completed_mother_tongue_practice(INVITATION["pt"], "pronto, mas ainda não")


def test_wanting_another_round_does_not_undo_a_finished_practice() -> None:
    assert confirms_completed_mother_tongue_practice(
        INVITATION["pt"], "já ensaiamos, mas queremos de novo"
    )


def test_nothing_confirms_a_practice_the_room_never_invited() -> None:
    assert not confirms_completed_mother_tongue_practice("O que aconteceu depois?", "pronto")
    assert not confirms_completed_mother_tongue_practice("O que aconteceu depois?", "já ensaiamos")


def test_a_spanish_room_confirms_a_finished_practice_but_never_a_denied_one() -> None:
    """A Spanish room could not answer its practice probe at all: no matcher carried a
    Spanish word, so the room's own prompt was never read as an invitation."""
    assert confirms_completed_mother_tongue_practice(INVITATION["es"], "listo")
    assert not confirms_completed_mother_tongue_practice(
        INVITATION["es"], "no, todavía no ensayamos"
    )
    assert not confirms_completed_mother_tongue_practice(INVITATION["es"], "ya no ensayamos")
    assert not confirms_completed_mother_tongue_practice(
        INVITATION["es"], "ya vamos a ensayar esta escena"
    )


def test_the_closing_word_is_heard_at_the_end_of_a_clause_too() -> None:
    """The room heard its own word only when it stood alone.

    Session b553b480, in English: the team answered the fixed invitation with "I already
    said, it's done." and the room said the same invitation again, word for word. The
    token matcher was anchored to a whole segment, so the word arriving where people
    ordinarily put it — at the end of a short clause, after a copula — was not the word at
    all. What refuses stays refusing: the negation, the plan, and the question are each
    turned away by a different guard, and none of them depends on this anchoring.

    The denials are asked in all three languages because the opening is one shared regex
    with a branch per language: an edit to the pt/es branch alone would reopen this in
    pt/es while every English case stayed green. `ya no está listo` is refused here by the
    opening having to touch the word, not by the negation list — no Spanish `no` reaches
    it (ENG-731) — so it is exactly the case a widened opening would lose."""
    english = INVITATION["en"]

    assert confirms_completed_mother_tongue_practice(english, "I already said, it's done.")
    assert confirms_completed_mother_tongue_practice(english, "it's done")
    assert confirms_completed_mother_tongue_practice(english, "it is done")
    assert confirms_completed_mother_tongue_practice(INVITATION["pt"], "já está pronto")
    assert confirms_completed_mother_tongue_practice(INVITATION["es"], "ya está listo")

    assert not confirms_completed_mother_tongue_practice(english, "it's not done")
    assert not confirms_completed_mother_tongue_practice(english, "it will be done")
    assert not confirms_completed_mother_tongue_practice(english, "is it done?")
    assert not confirms_completed_mother_tongue_practice(INVITATION["pt"], "já não está pronto")
    assert not confirms_completed_mother_tongue_practice(INVITATION["es"], "ya no está listo")


_INVITATION = (
    "A famine comes, and a family leaves Bethlehem for the fields of Moab. "
    "Rehearse this scene together in your own language; when you have finished, "
    "come back and tell me in English what you understood."
)


def test_a_fluent_retelling_alone_never_marks_the_scene_it_retold() -> None:
    """The Guide checks a retelling itself, item by item against the pinned map, with the
    whole conversation in context (DOCTRINE.md §4) — the app never claims to know what a
    mother-tongue rehearsal said, in the bridge language or otherwise. A retelling used to
    be read here on its own terms — fluent, substantial, no question, no hedge, no denial,
    no echo of the room's own voice — and none of that reading survives: only the team's
    own report that the rehearsal is finished marks the scene.
    """
    for reply in (
        _INVITATION,
        "come back and tell me in English what you understood",
        "A famine comes, and a family leaves Bethlehem for the fields of Moab.",
        "A famine came and a family left Bethlehem to live in Moab",
        "a family leaves Bethlehem for the fields of Moab",
        "vamos ensaiar essa cena agora",
        "we are going to rehearse it now",
    ):
        assert (
            scenes_practiced_by_the_report_the_guide_invited(None, _INVITATION, reply, True, "S1")
            == []
        ), reply
    assert (
        scenes_practiced_by_the_report_the_guide_invited(
            None,
            INVITATION["en"],
            "A famine came and a family left Bethlehem to live in Moab",
            True,
            "S1",
        )
        == []
    )


_INVITATION_PT = (
    "Olá, eu sou o Facilitador Digital. Esta história começa num tempo de muita desordem em "
    "Israel, quando não havia um líder fixo. Uma família de Belém precisa fugir da fome e buscar "
    "abrigo nas terras estrangeiras de Moabe. O tom é pesado e triste, pois a família vai "
    "perdendo tudo aos poucos. No fim, sobra apenas uma mulher sozinha e longe de casa.\n\n"
    "No começo, a fome aperta a terra e um homem chamado Elimeleque leva sua esposa, Noemi, e "
    "seus dois filhos para morar em Moabe como estrangeiros. Agora, ensaiem essa primeira parte "
    "na língua de vocês; quando terminarem, me contem em português o que entenderam."
)
_TELLING_PT = (
    "Tava tendo uma fome muito grande na terra de Belém e aí uma família teve que se mudar pra "
    "os campos de Moabe. E essa era a família do Elimeleque, da Naomi e dos seus dois filhos"
)


def test_a_portuguese_retelling_never_marks_the_scene_it_retold() -> None:
    """Session 1d142af3, in Portuguese, on the phone: a fluent retelling used to be read as
    the completion report itself.

    "Tava tendo uma fome... uma família teve que se mudar pra os campos de Moabe" tells the
    scene back whole, but it says nothing about a rehearsal having finished — the report the
    invitation asked for is the team's own word, not the app's judgment of the retelling's
    content, which is the Guide's job alone (DOCTRINE.md §4)."""
    assert (
        scenes_practiced_by_the_report_the_guide_invited(
            None, _INVITATION_PT, _TELLING_PT, True, "S1"
        )
        == []
    )


_INVITATION_FOR_THE_SECOND_SCENE = (
    "Agora vamos entrar na segunda cena, o verso três. É curta. A história diz: Elimeleque, "
    "o marido de Noemi, morreu. E Noemi ficou com os dois filhos. Isso acontece lá em Moabe, "
    "longe de casa. Quem conta não diz por que ele morreu. Não fala de choro, não fala de "
    "enterro. Diz só isso, em poucas palavras, e segue.\n\n"
    "Ensaiem essa cena juntos, na língua de vocês. Podem mostrar com as mãos: o marido que se "
    "vai, a mulher que fica com os dois filhos. Quando terminarem, voltem e me contem em "
    "português o que vocês disseram."
)
_TELLING_THAT_CLOSES_ON_A_TAG = (
    "Eu vou te contar algumas coisas que a gente concluiu. Tudo isso aconteceu no tempo que os "
    "juízes julgavam Israel antes de ter rei. Eram os juízes que governavam naquela época, "
    "certo? Hã, os dois filhos tomaram esposas dentre as mulheres de Moabe, mulheres moabitas, "
    "uma se chamava Orfa e a outra Rute. Hã, eles moraram lá uns 10 anos, mais ou menos. A "
    "história não fala de nenhum filho nascido nesses casamentos, nenhuma criança é "
    "mencionada. Quando Elimeleque morre, Noemi ficou e ela sobrou com os dois filhos. E "
    "quando Malom e Quiliom morreram, a mulher ficou e sobrou sozinha lá na terra, sem os dois "
    "filhos e sem o marido, certo? Hã, e as mortes são contadas cada uma numa frase bem curta "
    "e seca, tipo, Elimeleque morreu, Malom e Quiliom morreram. A história não descreve o "
    "luto, nenhum sentimento do tipo, nenhum choro, nem nada de enterro. Não diz também que "
    "Deus fez nada disso. E, e não deixa claro também que alguém deixou família ou linhagem "
    "pra continuar, né?"
)


def test_a_telling_that_closes_on_a_confirmation_tag_still_marks_nothing() -> None:
    """Session dce19a6b, message 12: scene 2 told back whole, tag and all.

    The team closed its telling with "né?" and checked itself twice along the way with
    "certo?" — the Brazilian habit of asking the listener to nod, not a question about the
    passage. Read as a question or not, the telling was never the report: only the team's
    own word that the rehearsal is finished marks a scene, and this reply never says one.
    """
    assert (
        scenes_practiced_by_the_report_the_guide_invited(
            None, _INVITATION_FOR_THE_SECOND_SCENE, _TELLING_THAT_CLOSES_ON_A_TAG, True, "S2"
        )
        == []
    )


_BOUNDARY_QUESTIONS = (
    (
        "pt",
        "No que vocês me contaram de volta, não ouvi a fome. "
        "A fome entrou no ensaio na língua de vocês?",
    ),
    (
        "en",
        "In what you told me back, I did not hear the famine. "
        "Did the famine enter the rehearsal in your own language?",
    ),
    (
        "es",
        "En lo que me contaron, no escuché el hambre. ¿El hambre entró en el ensayo en su lengua?",
    ),
    ("pt", "Isso estava no ensaio na língua de vocês, ou entrou agora na explicação?"),
)


def test_a_question_about_a_rehearsal_is_not_an_invitation_to_one() -> None:
    """The Guide's own boundary question names the rehearsal and the language, like the
    invitation does.

    The prompt tells it to ask exactly that when something is missing from a report, so it
    is not a rare line — and answering it is the ordinary next turn. Read as an invitation,
    a plain answer marked the scene rehearsed for a rehearsal nobody had asked for, against
    this module's first rule: a scene is practised only after an invitation bound to it.
    An invitation tells the team to go and do something; a question asks about something
    already done or not. The question mark does not separate them — the Guide phrases
    invitations politely, as questions, all the time — and neither does the vocabulary,
    which is identical. What differs is the rehearsal's part in the sentence: the
    invitation has the team rehearsing, so the rehearsal is a verb; the boundary question
    has a detail sitting inside a rehearsal already over, so it is a noun — under an
    article, a possessive, or none at all. So the polite invitations here must all count,
    and the boundary questions must all not, whichever way each is worded."""
    for language, question in _BOUNDARY_QUESTIONS:
        assert not guide_invited_mother_tongue_practice(question), question
        assert (
            scenes_practiced_by_the_report_the_guide_invited(
                None, question, "estava sim, nós dissemos que ela voltou com Rute", True, "S1"
            )
            == []
        ), language

    assert guide_invited_mother_tongue_practice(_INVITATION)
    assert (
        scenes_practiced_by_the_report_the_guide_invited(
            None,
            _INVITATION,
            "A famine came and a family left Bethlehem to live in Moab",
            True,
            "S1",
        )
        == []
    )
    for language in ("pt", "en", "es"):
        assert guide_invited_mother_tongue_practice(INVITATION[language])

    assert guide_invited_mother_tongue_practice(
        "Does any of that sound familiar? Now rehearse this scene together in your own "
        "language, and come back and tell me in English what you understood."
    )
    for polite in (
        "Would you rehearse this scene together in your own language and then tell me?",
        "Could you all rehearse this together in your own language and tell me what you got?",
        "Podem ensaiar esta cena na língua de vocês? "
        "Quando terminarem, me contem o que entenderam.",
        "Vocês conseguem ensaiar essa cena na língua de vocês e depois me contar o que entenderam?",
    ):
        assert guide_invited_mother_tongue_practice(polite), polite
    assert guide_invited_mother_tongue_practice("Rehearse this scene... in your own language.")
    assert guide_invited_mother_tongue_practice("Ensaiem esta cena... na língua de vocês.")
    assert guide_invited_mother_tongue_practice(
        "Now, in this scene, rehearse it together in your own language."
    )
    for spoken in (
        "Vocês praticam essa cena juntos na língua de vocês.",
        "Vocês ensaiam essa cena juntos na língua de vocês.",
        "Ustedes ensayan juntos esta escena en su lengua.",
        "Tu ensaias essa cena na língua de vocês.",
    ):
        assert guide_invited_mother_tongue_practice(spoken), spoken
    for about_a_rehearsal in (
        "Did you mention that during your rehearsal in your own language?",
        "Did that come up while rehearsing in your own language?",
        "Isso apareceu durante o ensaio na língua de vocês?",
        "Did that come up in the practice in your own language?",
        "Was that in your practice in your own language?",
        "Did that happen in that practice in your own language?",
        "Was that in this practice in your own language?",
        "Did I mention that in my practice in your own language?",
        "Did that come up during practice in your own language?",
        "Isso apareceu na prática na língua de vocês?",
    ):
        assert not guide_invited_mother_tongue_practice(about_a_rehearsal), about_a_rehearsal


def test_bare_polar_answers_are_semantically_empty() -> None:
    """The reader came here with the assessor's parser, and this is what it is for: a shrug
    is not a report, and it is not a misunderstanding either."""
    for text in ("sim", "não", "isso mesmo", "aham", "ok"):
        assert is_bare_polar_answer(text)
        assert is_semantically_empty_answer(text)
    assert not is_bare_polar_answer("Noemi voltou")
    assert is_semantically_empty_answer("não sei")
    assert not is_semantically_empty_answer("sim, Noemi voltou para Belém")
