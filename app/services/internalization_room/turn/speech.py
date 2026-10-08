"""What the room says back: the Guide speaks, or exact app-owned wording stands in for it."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from app.core.config import Settings
from app.db.models.internalization_room import IRSession
from app.services.internalization_room.fail_safe import inaudible_ladder
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.languages import LANGUAGE_NAMES, room_language
from app.services.internalization_room.passage_turn import run_turn
from app.services.internalization_room.validated_turn import TurnOutcome


def mother_tongue_note(language_code: str, take_ms: float | None) -> str:
    """Her note for a take in the team's own language, verbatim (`src/turn/openingNote.ts`).

    The seconds are said as her note says a number: `2.5` stays `2.5` and `40` is never
    `40.0`. A take the tablet measured arrives already rounded to the second.
    """
    seconds = f"{take_ms / 1000:g}" if take_ms else ""
    if language_code == "pt":
        held = f" por cerca de {seconds} segundos" if seconds else ""
        return (
            f"[A equipe falou na língua materna{held}; sem transcrição — nenhuma palavra "
            "chegou até você.]"
        )
    held = f" for about {seconds} seconds" if seconds else ""
    return f"[The team spoke in their own language{held}; no transcription — no words reached you.]"


def interrupted_note(language_code: str) -> str:
    """Her note for a team that cut the Guide's previous reply short, verbatim."""
    if language_code == "pt":
        return "[A equipe interrompeu a sua fala anterior neste ponto.]"
    return "[The team interrupted your previous turn at this point.]"


@dataclass(frozen=True)
class ForTheGuide:
    """What a heard take hands the Guide: the room's note, and the team's words behind it."""

    note: str
    words: str

    @property
    def spoken_to_the_guide(self) -> str:
        return " ".join(part for part in (self.note, self.words) if part)

    def kept_apart(self, outcome: TurnOutcome) -> TurnOutcome:
        """The outcome with the room's note as the room's and only the team's words as theirs."""
        if self.note:
            return replace(outcome, transcript=self.words, room_note=self.note)
        return outcome


def what_the_guide_is_handed(
    *,
    language_code: str,
    opening: bool,
    words: str,
    mother_tongue: bool,
    take_ms: float | None,
    interrupted: bool,
) -> ForTheGuide | None:
    """The one choice every spoken turn makes about a take: a miss, or the note and the words.

    A take with no words that is not the mother tongue is a miss, whether or not it followed a
    cut, and is answered with the ladder's line: nothing reaches the Guide. Any other take
    reaches the Guide with the room's notes in front, and the words of a mother-tongue take
    never travel.
    """
    if not opening and not mother_tongue and not words.strip():
        return None
    note = " ".join(
        part
        for part in (
            interrupted_note(language_code) if interrupted else "",
            mother_tongue_note(language_code, take_ms) if mother_tongue else "",
        )
        if part
    )
    return ForTheGuide(note=note, words="" if mother_tongue else words)


def a_miss(messages: list[dict[str, Any]], language_code: str) -> TurnOutcome:
    """The turn for a take that was a miss: the ladder's line, and nothing reaches the Guide."""
    line, fixed = inaudible_ladder(messages, language_code)
    return TurnOutcome(
        speech=line, transcript="", used_fail_safe=True, degraded=True, fixed_line=fixed
    )


def stamped_with_what_was_heard(outcome: TurnOutcome, speech: HeardSpeech) -> TurnOutcome:
    """The outcome keeping the language, its probability, the mother-tongue decision, the length."""
    return replace(
        outcome,
        language=speech.language_code,
        language_probability=speech.language_probability,
        mother_tongue=speech.mother_tongue,
        take_ms=speech.take_ms,
    )


async def speak_back(
    *,
    mother_tongue: bool,
    take_ms: float | None,
    session: IRSession,
    messages: list[dict[str, Any]],
    transcript: str,
    opening: bool,
    book: str,
    guide_prompt: str,
    validator_prompt: str,
    pericope: str,
    settings: Settings,
    interrupted: bool = False,
) -> TurnOutcome:
    """The Guide's reply to the team's turn, or the inaudible ladder's line in its place.

    The room's notes — the team cut the Guide short, the team spoke in the mother tongue —
    are handed to the Guide in front of the team's words, and come back as the room's, apart
    from them, so the conversation keeps them as the room's entry and only the team's words
    are ever settled. Words the recognizer made of a mother-tongue take never travel.

    A take with no words that is not the mother tongue is a miss, and draws the ladder's line
    whether or not it followed a cut: nothing reaches the Guide.
    """
    handed = what_the_guide_is_handed(
        language_code=session.language,
        opening=opening,
        words=transcript,
        mother_tongue=mother_tongue,
        take_ms=take_ms,
        interrupted=interrupted,
    )
    if handed is None:
        return a_miss(messages, session.language)
    language = room_language(session.language)
    outcome = await run_turn(
        transcript=handed.spoken_to_the_guide,
        coverage_state=session.coverage_state or {},
        messages=messages,
        session_language=LANGUAGE_NAMES[language],
        language_code=language,
        guide_prompt=guide_prompt,
        validator_prompt=validator_prompt,
        pericope_num=pericope,
        book=book,
        opening=opening,
        settings=settings,
        session_id=session.id,
        ask_for_movements=opening and not messages,
        earlier_passages=session.earlier_passages,
    )
    return handed.kept_apart(outcome)
