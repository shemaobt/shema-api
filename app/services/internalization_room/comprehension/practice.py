"""Mother-tongue practice as a process fact the room reads, never one it scripts.

A scene is marked practiced only after the Guide's own invitation for that scene, and only
by the team's own report that the rehearsal is finished — never by a retelling the app
assesses on its own. The Guide checks a retelling itself, item by item against the pinned
map, with the whole conversation in context; the app never claims to know what a
mother-tongue rehearsal said, in the bridge language or otherwise. Ported from
``src/comprehension/practice.ts``, where the invitation was the app's own fixed sentence and
its scope came from a probe.
"""

from __future__ import annotations

import re
import unicodedata

from app.services.internalization_room.comprehension.probe import ActiveProbe
from app.services.internalization_room.oral_decision import (
    oral_clause_has_negation,
    oral_clause_is_non_committal,
    oral_decision_clauses,
    oral_utterance_is_interrogative,
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
#: A bare past tense of the rehearsal verb, read only when it opens the team's first clause
#: back — "Ensaiamos, e entendemos que..." — never when it merely appears somewhere in the
#: reply. The anchor alone is not enough: a later clause can open with the same verb ("Lemos
#: tudo. Ensaiamos e seguimos.") without being the team's answer to the invitation, so the
#: caller checks this only against clause index 0.
_BARE_PAST_REPORT = (
    re.compile(r"^ensaiamos\b"),
    re.compile(r"^we\s+rehearsed\b"),
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
    for index, clause in enumerate(oral_decision_clauses(team_utterance)):
        if oral_clause_has_negation(clause) or oral_clause_is_non_committal(clause):
            continue
        if any(pattern.search(clause) for pattern in _FUTURE_REPORT):
            continue
        if any(pattern.search(clause) for pattern in _COMPLETED_REPORT):
            return True
        if index == 0 and any(pattern.search(clause) for pattern in _BARE_PAST_REPORT):
            return True
    return False


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


def scenes_practiced_by_the_report_the_guide_invited(
    prior_probe: ActiveProbe | None,
    previous_guide_utterance: str,
    team_utterance: str,
    reliable_bridge_speech: bool,
    current_scene: str | None,
) -> list[str]:
    """The scene just opened, when the team's own report of a finished rehearsal comes back.

    The invitation ends the opening of a scene, which is a turn before the planner has any
    reason to raise a practice probe for it — the scene is only opened by that very turn. A
    team that answers next is answered on the same terms as any other turn: only its own
    word that the rehearsal is done marks the scene. A retelling of the scene, however
    fluent and complete, is not read here at all — the Guide is the one who checks a
    retelling against the map, item by item, with the whole conversation in context; the
    app never claims to know what a mother-tongue rehearsal said.

    The scope is the scene the caller says the invitation was about — the one the Guide is
    opening while beads are still being opened, the first scene still owed a rehearsal once
    the necklace is full (`turn.scene_view.scene_the_invitation_is_about`); the Guide never
    chooses a scene itself. Nothing is marked when there is no scene in scope, and nothing
    is marked when the last line was not an invitation, which is what keeps an ordinary
    answer to an ordinary question from counting as a rehearsal.

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
    if prior_probe is not None:
        return []
    if current_scene is None:
        return []
    reported = reliable_bridge_speech and confirms_completed_mother_tongue_practice(
        previous_guide_utterance, team_utterance
    )
    if not reported:
        return []
    return [current_scene]
