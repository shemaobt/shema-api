from __future__ import annotations

import re

from app.services.internalization_room.languages import FLOOR

#: What an app-owned block says when the turn has none. The Validator is shared with every
#: conversation turn, where there is no finding, no ordered closing and no telling-back, and
#: an empty heading there reads as evidence withheld rather than as a block that does not
#: apply. The prompt says so in words; this is the same sentence in the slot itself.
NOT_THIS_TURN = "(not applicable to this turn)"

#: What the Validator is told when nobody spoke this turn. Composed in English like every
#: other backend instruction (ENG-822) — only {{SESSION_LANGUAGE}} carries what language the
#: team speaks. Two cases: the opening turn, where nobody has spoken yet, and the verdict
#: path, where the team has spoken — outside the conversation, into the telling-back — and
#: the opening line would say the opposite, which is the sentence the Validator quoted back
#: when it refused the verdict.
_NO_TEAM_UTTERANCE: dict[str, str] = {
    "opening": "(the team has not spoken yet — session opening)",
    "told_back": (
        "(the team has not spoken in this conversation; what they translated is in the "
        "block below)"
    ),
}


def _nobody_spoke_this_turn(telling_back: str) -> str:
    """What stands where the team's utterance would, on a turn that had none."""
    return _NO_TEAM_UTTERANCE["told_back"] if telling_back else _NO_TEAM_UTTERANCE["opening"]


#: What is asked of the Speaker on a turn with no team utterance and nothing to open — the
#: back-translation verdict, whose whole instruction is already in its system prompt. The
#: conversation used to reach the model as one block of text, which made a user message by
#: accident; now that it travels as the turns it was, the request would end on the Guide's
#: own last speech, and the API refuses that as an assistant prefill.
_SPEAK_THIS_TURN: dict[str, str] = {
    "pt": "Fale este turno.",
    "en": "Speak this turn.",
}


def speak_this_turn(language_code: str) -> str:
    return _SPEAK_THIS_TURN.get(language_code, _SPEAK_THIS_TURN[FLOOR])


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


OPENING_INSTRUCTION = (
    "The session is starting now and the team has not spoken yet. Open the "
    "session: introduce yourself briefly, give the team the whole before the "
    "parts, and stay with the team on understanding — the invitation to rehearse "
    "waits until they show they have the part."
)

ALREADY_MET_INSTRUCTION = (
    "This passage's session is starting now and the team has not spoken yet. "
    "You just walked the book's panorama together, so the team already knows "
    "you: do NOT introduce yourself again or say your name. Go straight into "
    "the passage: give the team the whole before the parts, and stay with the "
    "team on understanding — the invitation to rehearse waits until they show "
    "they have the part."
)

OPENING_MOVEMENT_INSTRUCTION = (
    "Write this opening in two movements, separated by a line containing only "
    f"{OPENING_MOVEMENT_MARK} and nothing else. Before the line: the whole of the "
    "passage, its arc and its tone. After the line: open the first scene and "
    "stay in it with the team; the invitation to rehearse does not close the "
    "opening. Do not write the mark anywhere else, and do not comment on it."
)


VALIDATOR_USER_MESSAGE = "Validate the drafted response now. Return only the JSON object."
