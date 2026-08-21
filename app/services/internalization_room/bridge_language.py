from __future__ import annotations

import logging

from langdetect import DetectorFactory, LangDetectException, detect_langs

logger = logging.getLogger(__name__)

DetectorFactory.seed = 0

MIN_LENGTH_TO_JUDGE = 40
MIN_CONFIDENCE_TO_REFUSE = 0.90


def strays_from(text: str, language_code: str = "pt") -> bool:
    """Whether a drafted line is confidently in some language other than the room's.

    The Meaning Map is written in English and the team hears everything only once, so a
    sentence that drifts out of the bridge language is not a blemish — it is a line the
    team cannot use. This refuses only what it is sure about: a short line the detector
    cannot place is no evidence, and silencing the facilitator costs more than an odd word.
    """
    stripped = (text or "").strip()
    if len(stripped) < MIN_LENGTH_TO_JUDGE:
        return False
    try:
        candidates = detect_langs(stripped)
    except LangDetectException:
        return False
    if not candidates:
        return False
    top = candidates[0]
    if top.lang == language_code or top.prob < MIN_CONFIDENCE_TO_REFUSE:
        return False
    logger.warning(
        "Draft strays from %s: detected %s at %.2f — %s",
        language_code,
        top.lang,
        top.prob,
        stripped[:120],
    )
    return True
