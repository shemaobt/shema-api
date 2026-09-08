from __future__ import annotations

_PEER_CUE_PHRASES = (
    "entre vocês",
    "entre voces",
    "conversem",
    "ensaiem",
    "ensaie",
    "na língua de vocês",
    "na lingua de voces",
    "among yourselves",
    "talk it over",
    "rehearse",
    "in your own language",
    "entre ustedes",
    "conversen",
    "ensayen",
    "ensaye",
    "en su lengua",
    "en su propia lengua",
)


def detects_peer_cue(speech: str) -> bool:
    """Whether the turn hands the talking to the team rather than back to the app.

    Read off the validated speech because the Guide returns prose, not a flag. It is a
    heuristic: a cleaner design would have the Guide mark the cue explicitly.
    """
    lowered = speech.casefold()
    return any(phrase in lowered for phrase in _PEER_CUE_PHRASES)
