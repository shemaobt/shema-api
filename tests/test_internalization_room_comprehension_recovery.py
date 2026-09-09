"""What the room still reads for itself: practice reported, consent given, empty answers.

The rehearsal invitation is the Guide's own sentence now, so the invitations written here
are ordinary Guide lines rather than a fixed prompt imported from the app. What the reader
asks of them is unchanged: it has to name the rehearsal, the team's own language, and the
word it wants back.
"""

from app.services.internalization_room.comprehension.practice import (
    bridge_language_retelling_completes_practice,
    confirms_completed_mother_tongue_practice,
    guide_invited_mother_tongue_practice,
    is_bare_polar_answer,
    is_semantically_empty_answer,
    scenes_practiced_by_the_telling_the_guide_invited,
)
from app.services.internalization_room.comprehension.probe import ActiveProbe, ProbePurpose
from app.services.internalization_room.rehearsal_readiness import (
    RECORDING_HANDOFF_REOFFER_AFTER_TURNS,
    rehearsal_consent_question,
    rehearsal_readiness_cue,
    resolve_rehearsal_consent,
    should_offer_recording_consent,
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


_CONSENT_PROBE = ActiveProbe(id="consent", purpose=ProbePurpose.RECORDING_HANDOFF_CONSENT)


def test_consent_needs_the_exact_question_and_probe() -> None:
    assert (
        resolve_rehearsal_consent(
            probe=_CONSENT_PROBE,
            previous_guide_utterance=rehearsal_consent_question("pt"),
            team_utterance="sim",
            reliable_bridge_speech=True,
        )
        == "accepted"
    )
    assert (
        resolve_rehearsal_consent(
            probe=_CONSENT_PROBE,
            previous_guide_utterance="Querem gravar em breve?",
            team_utterance="sim",
            reliable_bridge_speech=True,
        )
        == "unclear"
    )
    assert (
        resolve_rehearsal_consent(
            probe=None,
            previous_guide_utterance=rehearsal_consent_question("pt"),
            team_utterance="sim",
            reliable_bridge_speech=True,
        )
        == "unclear"
    )


def test_declining_consent_is_recognized() -> None:
    assert (
        resolve_rehearsal_consent(
            probe=_CONSENT_PROBE,
            previous_guide_utterance=rehearsal_consent_question("pt"),
            team_utterance="ainda não",
            reliable_bridge_speech=True,
        )
        == "declined"
    )


def test_uncertain_speech_never_consents() -> None:
    assert (
        resolve_rehearsal_consent(
            probe=_CONSENT_PROBE,
            previous_guide_utterance=rehearsal_consent_question("pt"),
            team_utterance="sim",
            reliable_bridge_speech=False,
        )
        == "unclear"
    )


def test_a_paused_handoff_is_not_reoffered_before_the_cooldown_elapses() -> None:
    assert not should_offer_recording_consent(
        eligible=True,
        paused=True,
        paused_turns=0,
        explicit_resume_requested=False,
        prior_decision="unclear",
        reliable_bridge_speech=True,
    )
    assert should_offer_recording_consent(
        eligible=True,
        paused=True,
        paused_turns=0,
        explicit_resume_requested=True,
        prior_decision="unclear",
        reliable_bridge_speech=True,
    )


def test_a_paused_handoff_is_reoffered_once_the_cooldown_elapses() -> None:
    """The team answered the app's own yes/no question with one of the two words it
    offered; the pause is a deferral, so the question comes back on its own."""
    assert not should_offer_recording_consent(
        eligible=True,
        paused=True,
        paused_turns=RECORDING_HANDOFF_REOFFER_AFTER_TURNS - 1,
        explicit_resume_requested=False,
        prior_decision="unclear",
        reliable_bridge_speech=True,
    )
    assert should_offer_recording_consent(
        eligible=True,
        paused=True,
        paused_turns=RECORDING_HANDOFF_REOFFER_AFTER_TURNS,
        explicit_resume_requested=False,
        prior_decision="unclear",
        reliable_bridge_speech=True,
    )


def test_an_elapsed_cooldown_never_outranks_the_other_gates() -> None:
    """Waiting is not readiness: the passage still has to be finished, the answer still
    has to be heard, and the turn that just declined still declines."""
    assert not should_offer_recording_consent(
        eligible=False,
        paused=True,
        paused_turns=RECORDING_HANDOFF_REOFFER_AFTER_TURNS,
        explicit_resume_requested=False,
        prior_decision="unclear",
        reliable_bridge_speech=True,
    )
    assert not should_offer_recording_consent(
        eligible=True,
        paused=True,
        paused_turns=RECORDING_HANDOFF_REOFFER_AFTER_TURNS,
        explicit_resume_requested=False,
        prior_decision="unclear",
        reliable_bridge_speech=False,
    )
    assert not should_offer_recording_consent(
        eligible=True,
        paused=True,
        paused_turns=RECORDING_HANDOFF_REOFFER_AFTER_TURNS,
        explicit_resume_requested=False,
        prior_decision="declined",
        reliable_bridge_speech=True,
    )


_INVITATION = (
    "A famine comes, and a family leaves Bethlehem for the fields of Moab. "
    "Rehearse this scene together in your own language; when you have finished, "
    "come back and tell me in English what you understood."
)


def test_the_room_hearing_itself_never_finishes_the_practice() -> None:
    """A microphone that picks up the app's own voice must not close the rehearsal.

    The telling the invitation asks for is the team's. The invitation itself, and the head
    or tail of it that a speaker can feed back into the microphone, are the room hearing
    itself — the one thing that is certainly not a rehearsal that happened.

    The head and the tail, and not the middle: a team whose telling repeats a phrase the
    Guide just used is telling, and refusing it would be the refusal this ticket exists to
    remove. The last case fixes that choice, so a widening to plain containment fails
    here instead of quietly costing real retellings."""
    assert not bridge_language_retelling_completes_practice(_INVITATION, _INVITATION, True)
    assert not bridge_language_retelling_completes_practice(
        _INVITATION, "come back and tell me in English what you understood", True
    )
    assert not bridge_language_retelling_completes_practice(
        _INVITATION, "A famine comes, and a family leaves Bethlehem for the fields of Moab.", True
    )
    assert bridge_language_retelling_completes_practice(
        _INVITATION, "A famine came and a family left Bethlehem to live in Moab", True
    )
    assert bridge_language_retelling_completes_practice(
        _INVITATION, "a family leaves Bethlehem for the fields of Moab", True
    )


def test_the_rooms_own_consent_question_never_marks_a_scene_practiced() -> None:
    """The recording-consent question reads exactly like an invitation to rehearse.

    "…record the first rehearsal in your own language?" carries the practice stem and the
    mother-tongue phrase in all three languages, so a team answering it with a whole
    sentence looked like a team reporting a rehearsal — of whatever scene the pointer
    happened to be on, which nobody had invited in that exchange.

    Reading the probe is not enough: accepting the recording clears the planned probe, so
    the readiness cue that follows is an app-owned invitation with no probe behind it at
    all. What settles it is the line — the room's own recording speech never counts, while
    the fixed practice prompt, which is a real invitation, still does."""
    consent = ActiveProbe(id="c", purpose=ProbePurpose.RECORDING_HANDOFF_CONSENT)
    assert (
        scenes_practiced_by_the_telling_the_guide_invited(
            consent,
            rehearsal_consent_question("en"),
            "Yes, let us go ahead and record it now",
            True,
            "S3",
        )
        == []
    )
    for language in ("en", "pt", "es"):
        for line in (rehearsal_consent_question(language), rehearsal_readiness_cue(language)):
            assert (
                scenes_practiced_by_the_telling_the_guide_invited(
                    None, line, "Yes, let us go ahead and record it now", True, "S3"
                )
                == []
            )
    assert scenes_practiced_by_the_telling_the_guide_invited(
        None, _INVITATION, "A famine came and a family left Bethlehem to live in Moab", True, "S1"
    ) == ["S1"]
    assert scenes_practiced_by_the_telling_the_guide_invited(
        None,
        INVITATION["en"],
        "A famine came and a family left Bethlehem to live in Moab",
        True,
        "S1",
    ) == ["S1"]


def test_an_announced_plan_is_not_the_telling_the_invitation_asked_for() -> None:
    """The likeliest reply to an invitation is the team saying it is about to obey.

    A plan is the one thing the other completion path had always refused, and the telling
    path was written without it: fluent, substantial, no question, no hedge, no denial, no
    echo — and no rehearsal yet. The scene would enter the practised list on a rehearsal
    that had not started."""
    invitation_pt = INVITATION["pt"]
    invitation_es = INVITATION["es"]

    assert not bridge_language_retelling_completes_practice(
        invitation_pt, "vamos ensaiar essa cena agora", True
    )
    assert not bridge_language_retelling_completes_practice(
        _INVITATION, "we are going to rehearse it now", True
    )
    assert not bridge_language_retelling_completes_practice(
        invitation_es, "ya vamos a ensayar esta escena", True
    )
    assert bridge_language_retelling_completes_practice(
        _INVITATION, "A famine came and a family left Bethlehem to live in Moab", True
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


def test_a_reflexive_se_in_the_telling_is_not_a_condition() -> None:
    """Session 1d142af3, in Portuguese, on the phone: the scene came back told and stayed
    unpractised.

    "teve que se mudar" is a verb carrying its clitic, and the guard read those two letters
    as the opening of a condition — so the one reply the invitation had asked for was filed
    as a team that had committed to nothing, and the next turn asked for the rehearsal
    again. Nearly every telling in Portuguese or Spanish carries a "se" like this one, and
    English carries none, which is why the same turn closed the practice three times over
    in English on the same day."""
    assert bridge_language_retelling_completes_practice(_INVITATION_PT, _TELLING_PT, True)
    assert scenes_practiced_by_the_telling_the_guide_invited(
        None, _INVITATION_PT, _TELLING_PT, True, "S1"
    ) == ["S1"]


def test_a_condition_that_opens_the_clause_holds_the_telling_back_without_a_subject() -> None:
    """ "Se quiserem a gente ensaia" names nobody and is still a condition.

    The subject list catches the same word inside a short reply; at the head of a clause
    the position alone says what the word is, because no clitic opens a clause. The reply
    the room must not be wrong about is the one that closes a practice that has not begun,
    and this is that reply one word away from the ones already refused.
    """
    for reply in (
        "Se quiserem a gente ensaia essa cena agora e depois conta pra você",
        "Se der tempo a gente ensaia essa cena e volta contando",
        "If possible we rehearse this scene together and then tell you",
        "Si es posible ensayamos esta escena juntos y luego les contamos",
    ):
        assert not bridge_language_retelling_completes_practice(_INVITATION_PT, reply, True), reply
    assert bridge_language_retelling_completes_practice(_INVITATION_PT, _TELLING_PT, True)


def test_a_told_scene_may_open_a_clause_on_the_clitic() -> None:
    """ "…, mas se mudaram pra Moabe" reaches the reader as the clause "se mudaram pra Moabe".

    A contrast marker splits the telling, and the second half opens on the clitic; Spanish
    drops the subject and opens on it outright. Both are session 1d142af3 one clause over,
    and refusing them would ask for the rehearsal again after the team had told it.
    """
    invitation_es = (
        "Ahora ensayen esta escena juntos en su lengua; cuando terminen, vuelvan y "
        "cuéntenme en español lo que entendieron."
    )
    for invitation, telling in (
        (
            _INVITATION_PT,
            "Eles ficaram em Belém por um tempo, mas se mudaram pra Moabe por causa da fome",
        ),
        (
            invitation_es,
            "Se mudaron a los campos de Moab, y allí murió Elimelec el marido de Noemí",
        ),
    ):
        assert bridge_language_retelling_completes_practice(invitation, telling, True), telling


def test_a_hedge_over_one_long_breath_still_holds_the_telling_back() -> None:
    """Counting a long single clause as a scene relieves the clitic, not the hedge.

    "Acho que a família se mudou pra Moabe por causa da fome e ficou lá" is one breath of
    doubt, however many words it takes; the hedge keeps refusing it, while the clitic in
    the same clause no longer does.
    """
    hedged = "Acho que a família se mudou pra Moabe por causa da fome e ficou lá um tempo"
    assert not bridge_language_retelling_completes_practice(_INVITATION_PT, hedged, True)


def test_a_told_reply_in_the_voices_own_words_is_not_a_telling() -> None:
    """Relaxing the hedge for a told reply must not relax the room hearing its words back.

    A team that says "você disse que a família se mudou e que Elimeleque morreu lá" is
    reporting the Voice, not the scene, however many clauses it takes to do it.
    """
    reported = (
        "Você disse que a família se mudou pra Moabe por causa da fome, "
        "e você disse que Elimeleque morreu lá"
    )
    assert not bridge_language_retelling_completes_practice(_INVITATION_PT, reported, True)


def test_a_told_scene_closes_the_practice_where_a_real_condition_still_refuses() -> None:
    """The clitic and the condition are the same two letters, and only one of them is a
    reason to refuse.

    A family that moved, a couple that married — the tellings this room exists to receive
    are full of them, in Portuguese and in Spanish alike, and each one was being read as a
    team that had not committed to anything. What a condition actually looks like is
    unchanged: it opens its clause and names who it is about, and a reply that is one short
    clause is still refused for a condition anywhere in it, so "a gente ensaia se vocês
    quiserem" does not become a rehearsal either."""
    invitation_pt = INVITATION["pt"]
    invitation_es = INVITATION["es"]

    assert bridge_language_retelling_completes_practice(
        invitation_es, "La familia se mudó a Moab por el hambre", True
    )
    assert bridge_language_retelling_completes_practice(
        invitation_pt, "A família se mudou pra Moabe", True
    )
    assert bridge_language_retelling_completes_practice(
        invitation_pt, "Eles se casaram e ficaram lá dez anos", True
    )
    assert not bridge_language_retelling_completes_practice(
        invitation_pt, "Se vocês quiserem a gente ensaia", True
    )
    assert not bridge_language_retelling_completes_practice(
        _INVITATION, "If you want we can rehearse", True
    )
    assert not bridge_language_retelling_completes_practice(
        invitation_pt, "Acho que não ensaiamos ainda", True
    )
    assert not bridge_language_retelling_completes_practice(
        invitation_pt, "A gente ensaia se vocês quiserem", True
    )
    assert not bridge_language_retelling_completes_practice(
        invitation_pt, "Se vocês quiserem a gente ensaia. Depois a gente conta tudo pra você", True
    )


def test_a_hedge_inside_a_told_scene_is_a_person_remembering_not_a_refusal() -> None:
    """Half remembering a scene out loud is how a scene comes back, not a team holding out.

    "acho que" between two told clauses is the sound of someone reaching for a name, and
    the gate read it the same way it reads "acho que a gente ensaiou" — a reply with no
    telling around it at all, where the hedge really is the whole answer. Two clauses of
    three words or more are what separates them."""
    invitation_pt = INVITATION["pt"]

    assert bridge_language_retelling_completes_practice(
        invitation_pt,
        "Tava tendo uma fome muito grande em Belém. Acho que a família do Elimeleque foi pra "
        "Moabe com a Noemi e os dois filhos",
        True,
    )
    assert not bridge_language_retelling_completes_practice(
        invitation_pt, "Acho que a gente ensaiou", True
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
            scenes_practiced_by_the_telling_the_guide_invited(
                None, question, "estava sim, nós dissemos que ela voltou com Rute", True, "S1"
            )
            == []
        ), language

    assert guide_invited_mother_tongue_practice(_INVITATION)
    assert scenes_practiced_by_the_telling_the_guide_invited(
        None, _INVITATION, "A famine came and a family left Bethlehem to live in Moab", True, "S1"
    ) == ["S1"]
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
