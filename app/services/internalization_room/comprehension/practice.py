"""Mother-tongue practice as an app-owned process fact.

A scene is marked practiced only after an app-authored invitation bound to that scene,
confirmed by a completed-practice report, a bound completion word, or substantial audio
confidently recognized as not being the bridge language. The system never turns language
detection into a claim that it understood the content — it does not understand the team's
mother tongue at all. Ported from ``src/comprehension/practice.ts``.
"""

from __future__ import annotations

import re
import unicodedata

from app.services.internalization_room.comprehension.assessor import (
    is_semantically_empty_answer,
)
from app.services.internalization_room.comprehension.probe import (
    PROBES_THAT_INVITE_A_REHEARSAL,
    ActiveProbe,
    ProbePurpose,
    is_process_only,
)
from app.services.internalization_room.languages import FLOOR
from app.services.internalization_room.oral_decision import (
    normalize_oral_decision,
    oral_clause_has_negation,
    oral_clause_is_hedged,
    oral_clause_is_non_committal,
    oral_clause_reports_the_voice,
    oral_decision_clause_details,
    oral_decision_clauses,
    oral_utterance_is_interrogative,
)
from app.services.internalization_room.rehearsal_readiness import (
    is_exact_rehearsal_consent_question,
    is_exact_rehearsal_readiness_cue,
)


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^\w]+", " ", stripped.casefold(), flags=re.UNICODE).strip()


_AFFIRMATIVE = re.compile(
    r"^(sim|claro|isso|isso mesmo|ja|ja fizemos|fizemos|pronto|terminamos|acabamos"
    r"|yes|yeah|we did|already did|done|finished|ready|sure)$"
)
_PRACTICE = re.compile(r"\b(ensai|ensay|pratic|recont|tent\w*\s+cont|rehears|practic|retell)\w*")
_MOTHER_TONGUE = re.compile(
    r"\b(lingua de voces|lingua materna|lingua da equipe|su lengua|terena|own language"
    r"|mother tongue|team language)\b"
)
_CONFIRMATION = re.compile(
    r"\b(ja|conseguiram|termin\w*|acabar\w*|fizeram|tentaram|did you|have you"
    r"|were you able|finish\w*)\b"
)
_COMPLETION_TOKEN_INVITATION = re.compile(
    r"\b(?:pronto|pronta|prontos|prontas|digam\s+pronto|avisem|quando\s+conclu\w*"
    r"|quando\s+estiver\w*\s+pront\w*|listo|ready|say\s+ready|done|when\s+you\s+are\s+done"
    r"|let\s+me\s+know)\b"
)
#: The closing word the app asked for, alone in its clause or carried by a copula. A
#: subject and a verb of being are all that may precede it — "it is done", "já está
#: pronto", "ya está listo" — because that is how the word is ordinarily said and the
#: anchored form heard none of it. The prefix has to sit against the word: "ya no está
#: listo" and "it will be done" put something between them and are not this.
_COMPLETION_TOKEN = re.compile(
    r"^(?:(?:it\s+s|it\s+is|that\s+s|that\s+is|this\s+is|we\s+re"
    r"|(?:ja\s+|ya\s+)?(?:esta|estamos))\s+)?"
    r"(?:pronto|pronta|prontos|prontas|listo|listos|terminamos|acabamos|concluimos|ready|done"
    r"|finished|we\s+are\s+done|we\s+finished)$"
)
_SEGMENT_BOUNDARY = re.compile(r"[,;.!?\n]+")
_COMPLETED_REPORT = (
    re.compile(
        r"\b(ja|acabamos\s+de|terminamos\s+de)\b.{0,40}\b(ensai|pratic|recont|tent\w*\s+cont)\w*"
    ),
    re.compile(
        r"\b(we\s+already|we\s+did|we\s+have|we\s+finished)\b.{0,40}"
        r"\b(rehears|practic|retell|tried\s+\w*\s*tell)\w*"
    ),
)
_FUTURE_REPORT = (
    re.compile(
        r"\b(vamos|iremos|queremos|pretendemos|podemos)\b.{0,32}"
        r"\b(ensai|ensay|pratic|recont|tent\w*\s+cont)\w*"
    ),
    re.compile(
        r"\b(we\s+will|we'll|we\s+are\s+going\s+to|we\s+want\s+to|we\s+plan\s+to|we\s+can)\b"
        r".{0,32}\b(rehears|practic|retell|try\s+\w*\s*tell)\w*"
    ),
)


#: The rehearsal as something the team is being told to do. Verb forms only, listed
#: rather than stemmed, because the one thing this must not admit is the rehearsal named
#: as a thing — `ensaio`, `rehearsal`, `rehearsing`, `ensayo`, `prática` — which is how
#: the Guide's boundary question speaks of a rehearsal already over. English `practice` is
#: both verb and noun, so it is left out on the noun's account: which one it is can only
#: be told from the determiner in front, and that list has no end ("in that practice", "in
#: my practice", "during practice"). `rehearse` says the same thing and says it once.
_PRACTICE_AS_A_VERB = re.compile(
    r"\b(?:ensai(?:e|em|es|ar|am|amos|as|a)|ensay(?:e|en|es|ar|an|amos|as|a)"
    r"|pratiqu(?:e|em|emos)|pratic(?:ar|am|amos)"
    r"|practiqu(?:e|en|emos)|practic(?:ar|an|amos)"
    r"|recont(?:e|em|es|ar|am|amos|as|a)|rehearse|rehearses|practise|practises"
    r"|retell|retells)\b"
)


def guide_invited_mother_tongue_practice(guide_utterance: str) -> bool:
    """Whether a line the room said sent the team to rehearse in its own language.

    An invitation tells the team to go and do something. A question asks *about* a
    rehearsal — whether it happened, whether some detail was in it — and the Guide is told
    to ask exactly that whenever a report leaves something out, in the very same words:
    the practice stem and the mother-tongue phrase.

    The question mark does not separate them. The Guide writes in its own words and asks
    politely all the time — "podem ensaiar esta cena na língua de vocês?" is an invitation
    and ends in one. What separates them is what the rehearsal is doing in the sentence:
    the invitation has the team rehearsing, so the rehearsal is a verb, while the boundary
    question has a detail sitting inside a rehearsal already over, so it is a noun. So the
    verb forms are what is looked for, and they are listed rather than stemmed: a stem
    that reaches `ensaiar` reaches `ensaio` too, and that noun is the whole difficulty.
    English `practice` is left out for the same reason from the other side — it is verb and
    noun at once, and only the determiner in front tells which, a list with no end.

    An invitation that names the rehearsal instead of asking for it — "comecem o ensaio na
    língua de vocês" — is not read as one. That is the direction to be wrong in: a missed
    invitation costs a fixed line the room says anyway and a telling that goes uncredited,
    while a false one marks a scene practised that nobody rehearsed, against the rule this
    module opens with.
    """
    text = _normalize(guide_utterance)
    return bool(_PRACTICE_AS_A_VERB.search(text) and _MOTHER_TONGUE.search(text))


def _oral_segments(utterance: str) -> list[str]:
    """Split a spoken confirmation at the boundaries a listener hears.

    Commas count alongside the strong stops: a team that answers "pronto, terminamos"
    said the completion word, and matching only the whole utterance would lose it.
    """
    return [
        segment
        for segment in (_normalize(part) for part in _SEGMENT_BOUNDARY.split(utterance))
        if segment
    ]


def _explicit_completed_practice_report(team_utterance: str) -> bool:
    """The team reports its own finished practice in plain speech.

    Naming the language is the Guide's job, not the team's — the invitation already bound
    the scene and the language, so the report is read for a completed practice alone.
    """
    whole = _normalize(team_utterance)
    if not _PRACTICE.search(whole):
        return False
    if oral_utterance_is_interrogative(team_utterance):
        return False
    return any(
        not oral_clause_has_negation(clause)
        and not oral_clause_is_non_committal(clause)
        and not any(pattern.search(clause) for pattern in _FUTURE_REPORT)
        and any(pattern.search(clause) for pattern in _COMPLETED_REPORT)
        for clause in oral_decision_clauses(team_utterance)
    )


def confirms_completed_mother_tongue_practice(
    previous_guide_utterance: str, team_utterance: str
) -> bool:
    """A bare yes can establish a process fact only when bound to a direct, validated
    question about already completed mother-tongue practice. It never becomes semantic
    passage evidence.

    The team's answer is read segment by segment, so a confirmation spoken as part of a
    longer sentence still counts. Reading by segment costs the anchoring that used to
    refuse a negative on its own, so a question, a hedge or any negation anywhere in the
    answer refuses it explicitly instead: "sim, mas ainda não" is not a finished practice.
    """
    guide = _normalize(previous_guide_utterance)
    if oral_utterance_is_interrogative(team_utterance) or oral_clause_is_non_committal(
        team_utterance
    ):
        return False
    scoped_practice = bool(_PRACTICE.search(guide) and _MOTHER_TONGUE.search(guide))
    direct_confirmation = scoped_practice and bool(_CONFIRMATION.search(guide))
    completion_token = scoped_practice and bool(_COMPLETION_TOKEN_INVITATION.search(guide))
    if not direct_confirmation and not completion_token:
        return False
    if _explicit_completed_practice_report(team_utterance):
        return True
    segments = _oral_segments(team_utterance)
    if any(oral_clause_has_negation(segment) for segment in segments):
        return False
    if completion_token and any(_COMPLETION_TOKEN.match(segment) for segment in segments):
        return True
    return direct_confirmation and any(_AFFIRMATIVE.match(segment) for segment in segments)


_PRACTICE_PROMPT = {
    "pt": (
        "Agora ensaiem juntos esta cena na língua de vocês. "
        "Quando terminarem, digam somente: pronto."
    ),
    "en": (
        "Now rehearse this scene together in your own language. "
        "When you have finished, just say: done."
    ),
    "es": (
        "Ahora ensayen juntos esta escena en su lengua. Cuando terminen, digan solamente: listo."
    ),
}


def mother_tongue_practice_prompt(language: str = FLOOR) -> str:
    return _PRACTICE_PROMPT.get(language, _PRACTICE_PROMPT[FLOOR])


def is_exact_mother_tongue_practice_prompt(text: str) -> bool:
    """Whether a line the room already said was the practice prompt, in any language.

    Any language's, for the same reason the rehearsal matchers take all of them: the text
    was written on an earlier turn, and a room that only recognised the current language
    would fail to recognise its own question.
    """
    return _normalize(text) in {_normalize(said) for said in _PRACTICE_PROMPT.values()}


def the_practice_invitation_is_owed_by_the_app(
    prior_probe: ActiveProbe | None,
    planned_probe: ActiveProbe | None,
    previous_guide_utterance: str,
) -> bool:
    """Whether the app still has to say the fixed line because the Guide never invited.

    The invitation belongs to the Guide, at the end of the opening, in its own words and
    carrying the contract the team answers: rehearse, then come back and tell in the
    bridge language what you understood. Speaking the fixed sentence in that place took
    the turn away from the Guide, so the opening closed on a passage question and the app
    asked for the same rehearsal a turn later under a different contract.

    What is left for the fixed line is the turn after a probe stood through a whole turn
    with no invitation said. Reading the last line rather than the probe is what keeps it
    from arriving twice: the Guide's invitation and the app's own both read as
    invitations, so neither is followed by the other.
    """
    if planned_probe is None or planned_probe.purpose is not ProbePurpose.MOTHER_TONGUE_PRACTICE:
        return False
    if prior_probe is None or prior_probe.purpose is not ProbePurpose.MOTHER_TONGUE_PRACTICE:
        return False
    if prior_probe.practice_scene_ids != planned_probe.practice_scene_ids:
        return False
    return not guide_invited_mother_tongue_practice(previous_guide_utterance)


#: The subject a spoken condition opens on. A condition names who it is about — "se vocês
#: quiserem", "se a família ficasse", "if you want" — while the same letters against a verb
#: are the clitic that verb carries: "teve que se mudar", "eles se casaram", "la familia se
#: mudó". The subjects are listed rather than the verbs because a pronoun or a determiner is
#: a closed set and the verbs that can carry a clitic are not. Spanish `si` is read here and
#: `sí` never is, which is why the accent is taken off the text after that word is gone
#: rather than before.
_CONDITION_ON_A_SUBJECT = re.compile(
    r"\b(?:se|si|if)\s+(?:eu|tu|voce|voces|nos|a\s+gente|ele|eles|ela|elas"
    r"|yo|usted|ustedes|nosotros|vosotros|el|ella|ellos|ellas"
    r"|i|we|you|they|he|she|it"
    r"|o|a|os|as|um|uma|un|una|los|las|este|esta|esse|essa|isso|isto|aquele|aquela"
    r"|the|this|that|there|an)\b"
)
_SPANISH_YES = re.compile(r"\bsí\b", re.IGNORECASE)
#: A condition that opens a short reply is one whether or not it names who it is about:
#: "se quiserem a gente ensaia", "se der tempo", "if possible we rehearse". It is read only
#: on a reply that is not a telling, because a told scene opens clauses on the clitic all the
#: time — "…, mas se mudaram pra Moabe" arrives here as the clause "se mudaram pra Moabe",
#: and Spanish drops the subject and opens on it outright, "Se mudaron a los campos de Moab".
_CONDITION_OPENS_THE_CLAUSE = re.compile(r"^(?:se|si|if)\b")
#: The heads a subjectless condition opens on inside a telling: the verb forms that only a
#: condition takes ("se quiserem", "se der tempo", "se for possível", "si es posible",
#: "if possible"). A told clause that opens on "se" followed by a past-tense verb is the
#: clitic riding it — "se mudaram", "se mudaron" — and is left alone.
_CONDITION_HEADS = re.compile(
    r"^(?:se|si|if)\s+(?:quiser|quiserem|quisermos|der|derem|for|forem|puder|puderem"
    r"|tiver|tiverem|houver|conseguir|conseguirem|precisar|precisarem"
    r"|quiere|quieren|quisiera|quisieran|puede|pueden|hay|es\s+posible|posible|fuera"
    r"|possible|needed|necessary|wanted)\b"
)


def _the_telling_holds_back(team_utterance: str) -> bool:
    """Whether a team that came back telling the scene held back from telling it.

    The condition and the hedge both mean something else inside a telling than they mean
    inside a decision. A condition that is really one opens its clause and names who it is
    about; the "se" a whole session of Portuguese or Spanish is made of rides the verb that
    follows it, and refusing on that refused nearly every telling the invitation ever asked
    for. A hedge dropped into the middle of a told scene is a person telling a story they
    half remember, which is the ordinary way a scene comes back — so it only refuses a
    reply that has no telling around it. Two clauses of three words or more count as
    telling for the hedge. The clitic is relieved one step earlier: a single clause of
    eight words or more is a scene too — a Spanish telling that drops its subjects can be
    one long clause from end to end — but a hedge in a single clause, however long, still
    refuses, because "acho que…" over one breath is a person unsure, not one telling.

    A reply that is a single clause keeps the older, flatter reading: the hedge refuses,
    and so does a condition anywhere in it, not only one that opens it.
    """
    clauses = oral_decision_clause_details(team_utterance)
    told_in_clauses = sum(1 for clause in clauses if len(clause.text.split()) >= 3) >= 2
    told_at_length = any(len(clause.text.split()) >= 8 for clause in clauses)
    for clause in clauses:
        spoken = normalize_oral_decision(_SPANISH_YES.sub(" ", clause.raw))
        if _CONDITION_ON_A_SUBJECT.match(spoken) or _CONDITION_HEADS.match(spoken):
            return True
        if oral_clause_reports_the_voice(clause.raw):
            return True
        if not (told_in_clauses or told_at_length) and _CONDITION_OPENS_THE_CLAUSE.match(spoken):
            return True
        if told_in_clauses:
            continue
        if _CONDITION_ON_A_SUBJECT.search(spoken) or oral_clause_is_hedged(clause.raw):
            return True
    return False


def _echoes_the_line_the_room_just_said(previous_guide_utterance: str, team_utterance: str) -> bool:
    """Whether what was heard is the room's own voice coming back through the microphone.

    A speaker feeding the invitation back gives a transcript that is the line itself, or
    the head or tail of it that the microphone caught. None of it is a team telling
    anything, and all of it would otherwise read as one — the invitation is fluent bridge
    language, it is long, and it holds no negation, hedge or question.
    """
    said = _normalize(previous_guide_utterance)
    heard = _normalize(team_utterance)
    if not heard or not said:
        return False
    return heard == said or said.startswith(heard) or said.endswith(heard)


def bridge_language_retelling_completes_practice(
    previous_guide_utterance: str, team_utterance: str, reliable_bridge_speech: bool
) -> bool:
    """The team came back telling the scene, which is what the invitation asked it to do.

    The invitation names its own contract — rehearse, then tell me in the bridge language
    what you understood — so the telling is the completion report. The closing word still
    counts; it is simply no longer the only thing that does, and a team that did the
    larger thing is no longer refused for skipping the smaller one.

    It stays a process fact. This says the practice happened and nothing at all about what
    the telling is worth against the map: the probe authorizes no semantic evidence, and
    reading a retelling here does not change that.

    The room's own recording speech is refused before any of that. Both the consent
    question and the readiness cue speak of the first rehearsal in the team's own
    language, so both read as invitations, and neither is one: agreeing to record is not a
    rehearsal of the scene the pointer happens to be on. Reading the standing probe does
    not catch it — accepting the recording clears the planned probe, so the cue arrives
    with nothing behind it — which is why the line itself is what is checked. The fixed
    practice prompt is left alone: it is a real invitation, and the telling that answers it
    is a real telling.

    An announced plan is refused with them. It is the likeliest reply of all to an
    invitation the Guide has just given — the team saying it is about to obey — and it is
    fluent, substantial and holds no question, hedge or denial, so it would otherwise read
    as the telling itself and mark a rehearsal that had not started. The same patterns
    that refuse it on the reported-rehearsal path refuse it here.

    What is refused, besides the question, the hedge and the denial, is the room hearing
    its own voice: the invitation echoed whole, or the head or tail of it a speaker can
    feed back. A fragment from the middle of the line is not caught here — it would cost
    the ordinary retelling that reuses the words the Guide just used.
    """
    if not reliable_bridge_speech:
        return False
    if not guide_invited_mother_tongue_practice(previous_guide_utterance):
        return False
    if is_exact_rehearsal_consent_question(previous_guide_utterance) or (
        is_exact_rehearsal_readiness_cue(previous_guide_utterance)
    ):
        return False
    if _echoes_the_line_the_room_just_said(previous_guide_utterance, team_utterance):
        return False
    if oral_utterance_is_interrogative(team_utterance) or _the_telling_holds_back(team_utterance):
        return False
    clauses = oral_decision_clauses(team_utterance)
    if any(oral_clause_has_negation(clause) for clause in clauses):
        return False
    if any(pattern.search(clause) for clause in clauses for pattern in _FUTURE_REPORT):
        return False
    return not is_semantically_empty_answer(team_utterance)


def confident_non_bridge_audio_completes_scoped_practice(
    probe: ActiveProbe | None, confidently_non_bridge: bool
) -> bool:
    """A confident non-bridge-language recording is process evidence only when it answers
    the exact app-authored practice probe. It can mark that scoped practice happened, but
    can never become semantic evidence or mark an unknown/all-scenes scope."""
    return confidently_non_bridge and (
        probe is not None and probe.purpose in PROBES_THAT_INVITE_A_REHEARSAL
    )


def scenes_practiced_by_the_telling_the_guide_invited(
    prior_probe: ActiveProbe | None,
    previous_guide_utterance: str,
    team_utterance: str,
    reliable_bridge_speech: bool,
    current_scene: str | None,
) -> list[str]:
    """The scene just opened, when the telling its invitation asked for comes straight back.

    The invitation ends the opening of a scene, which is a turn before the planner has any
    reason to raise a practice probe for it — the scene is only opened by that very turn. A
    team that does what it was asked answers next, so reading the practice only through a
    standing probe threw away the one reply the invitation had asked for: the scene stayed
    unpractised, the probe arrived afterwards, and the room asked again for a rehearsal
    already told.

    The scope is the scene pointer, because that is what the invitation was about — the
    Guide opens the scene the pointer names and invites for that one; it never chooses a
    scene itself. Nothing is marked when there is no pointer, and nothing is marked when
    the last line was not an invitation, which is what keeps an ordinary answer to an
    ordinary question from counting as a rehearsal.

    A process-only probe of another purpose standing is the room saying what the turn is
    about, and it is not this — a scene opening included: it names the scene it is inviting
    for, and that scope is the probe's to give, not the pointer's. A semantic probe is no
    such claim — the Guide asks its question and invites the rehearsal in the same breath,
    which is the turn this exists for. That matters most for the recording-handoff consent,
    whose fixed question — record the first rehearsal in your own language? — carries the
    practice stem and the mother-tongue phrase in every language the room speaks, so a team
    agreeing to record would otherwise be read as a team reporting a rehearsal of whatever
    scene the pointer was on.
    """
    if (
        prior_probe is not None
        and is_process_only(prior_probe)
        and prior_probe.purpose is not ProbePurpose.MOTHER_TONGUE_PRACTICE
    ):
        return []
    if current_scene is None:
        return []
    if not bridge_language_retelling_completes_practice(
        previous_guide_utterance, team_utterance, reliable_bridge_speech
    ):
        return []
    return [current_scene]


def practiced_scenes_authorized_by_probe(probe: ActiveProbe, practice_reported: bool) -> list[str]:
    return list(probe.practice_scene_ids) if practice_reported else []
