from __future__ import annotations

import re

TEAM_EVIDENCE_HEADING = (
    "## WHAT THE TEAM JUST SAID (evidence — NEVER truth about the passage)\n\n"
    "The drafted response answers this. Referring to these words is not a claim about the "
    "passage.\n\n"
)

EARLIER_PASSAGES_HEADING = (
    "## EARLIER PASSAGES FOR THIS TEAM (the app's fact about this team — NEVER truth about the "
    "passage)\n\nThe Guide read this same line this turn.\n\n"
)


TEAM_REPORTED_HEADING = (
    "\n\n---\n\n# WHAT THE TEAM REPORTED (their back-translation of their own recording)\n"
    "Evidence of what the team told back — NEVER truth about the passage. The drafted response "
    "may quote from it to name something reported that the passage does not tell; quoting this "
    "material is not a claim about the passage and must not be treated as ungrounded.\n\n"
)


def her_block(heading: str, text: str) -> str:
    return f"{heading}{text.strip()}" if text.strip() else ""


#: What is asked of the Speaker on a turn with no team utterance and nothing to open — the
#: back-translation verdict, whose whole instruction is already in its system prompt. The
#: conversation used to reach the model as one block of text, which made a user message by
#: accident; now that it travels as the turns it was, the request would end on the Guide's
#: own last speech, and the API refuses that as an assistant prefill. Composed in English like
#: every other backend instruction (ENG-822) — only {{SESSION_LANGUAGE}} carries what language
#: the team speaks.
SPEAK_THIS_TURN = "Speak this turn."


OPENING_MOVEMENT_MARK = "[[CENA]]"
_MOVEMENT_MARK = re.compile(r"^[ \t]*\[\[CENA\]\][ \t]*$", re.M)


def split_opening_movements(draft: str) -> tuple[str, list[str]]:
    """The draft with the mark taken out, and its two movements when the mark is exact.

    The text comes back mark-free whatever happens: a marker read aloud by the synthesiser
    is the one outcome nothing downstream recovers from. The movements come back empty
    unless the mark stands exactly once, alone on its own line, with speech on both sides —
    a half-offered structure has to be indistinguishable from no structure at all, because
    an opening told in one breath is what the room already does well.
    """
    parts = _MOVEMENT_MARK.split(draft)
    clean = _MOVEMENT_MARK.sub("", draft).replace(OPENING_MOVEMENT_MARK, " ")
    clean = re.sub(r"[ \t]{2,}", " ", clean)
    clean = re.sub(r"\n{3,}", "\n\n", clean).strip()
    if len(parts) != 2:
        return clean, []
    whole, scene = (part.strip() for part in parts)
    if not whole or not scene:
        return clean, []
    return clean, [whole, scene]


def opening_note(pericope_num: str, language_code: str) -> str:
    if language_code == "pt":
        return (
            f"[A sessão acabou de começar. A equipe abriu a passagem {pericope_num} e está à "
            "mesa, pronta para começar. Fale primeiro.]"
        )
    return (
        f"[The session has just begun. The team opened passage {pericope_num} and is at the "
        "table, ready to begin. Speak first.]"
    )


def panorama_note(book: str, language_code: str) -> str:
    if language_code == "pt":
        return (
            f"[A sessão acabou de começar. A equipe abriu o Panorama do Livro de {book} e está "
            "à mesa, pronta para conversar. Fale primeiro.]"
        )
    return (
        f"[The session has just begun. The team opened the Book Panorama of {book} and is at "
        "the table, ready to talk. Speak first.]"
    )


VALIDATOR_USER_MESSAGE = "Validate the drafted response now. Return only the JSON object."
