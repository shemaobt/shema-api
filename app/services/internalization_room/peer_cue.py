from __future__ import annotations

import re

_PEER_CUE_PHRASES = (
    "entre vocês",
    "entre voces",
    "conversem",
    "discutam",
    "um com o outro",
    "ensaiem",
    "ensaie",
    "na língua de vocês",
    "na lingua de voces",
    "among yourselves",
    "talk it over",
    "discuss",
    "to each other",
    "rehearse",
    "in your own language",
)

_PEER_CUE_PATTERN = re.compile(
    "|".join(rf"\b{re.escape(phrase)}\b" for phrase in _PEER_CUE_PHRASES)
)


def detects_peer_cue(speech: str) -> bool:
    """Whether the turn hands the talking to the team rather than back to the app.

    Read off the validated speech because the Guide returns prose, not a flag. It is a
    heuristic: a cleaner design would have the Guide mark the cue explicitly.
    """
    return _PEER_CUE_PATTERN.search(speech.casefold()) is not None
