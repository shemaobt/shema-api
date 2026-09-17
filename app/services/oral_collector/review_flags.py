"""What marks a recording as needing review (ENG-373).

The flags are persisted rather than derived on read, so the server owns the definition the
Flutter client used to carry. Each condition mirrors a rule that already exists elsewhere:
the `unclassified` sentinel seeded by migration, the ENG-354 description threshold, and the
storyteller foreign key.
"""

from typing import Any

from app.core.enums import ReviewFlagCode, ReviewFlagOrigin
from app.db.models.oc_recording import OC_Recording, ReviewFlag
from app.utils.description_rule import is_sufficient_description

UNCLASSIFIED_GENRE_ID = "unclassified"


def _flag(code: ReviewFlagCode) -> ReviewFlag:
    return {"code": str(code), "origin": str(ReviewFlagOrigin.SYSTEM)}


def flag_codes(stored: Any) -> set[str]:
    """The codes in a `review_flags` value read back from the column.

    Readers go through here rather than reaching for the key themselves, so the one string
    that ties the stored shape to the code that queries it lives in a single place.
    """
    return {flag["code"] for flag in stored or []}


def review_flags_for(
    *,
    genre_id: str | None,
    register_id: str | None,
    description: str | None,
    storyteller_id: str | None,
) -> list[ReviewFlag]:
    """The flags these four field values imply, in a fixed order.

    The order is part of the contract: the ENG-373 backfill decides whether a row needs
    rewriting by comparing the computed list against the stored one, so a rule that emitted
    the same flags in a different order would rewrite every row it read.
    """
    flags: list[ReviewFlag] = []

    if genre_id == UNCLASSIFIED_GENRE_ID or not register_id:
        flags.append(_flag(ReviewFlagCode.MISSING_CLASSIFICATION))
    if not is_sufficient_description(description):
        flags.append(_flag(ReviewFlagCode.INSUFFICIENT_DESCRIPTION))
    if storyteller_id is None:
        flags.append(_flag(ReviewFlagCode.MISSING_STORYTELLER))

    return flags


def recompute_review_flags(recording: OC_Recording) -> None:
    """Replace ``recording.review_flags`` with the flags its current field values imply.

    The whole list is assigned, never appended to, so running this twice on the same state
    leaves the same result and no write path can accumulate duplicates.
    """
    recording.review_flags = review_flags_for(
        genre_id=recording.genre_id,
        register_id=recording.register_id,
        description=recording.description,
        storyteller_id=recording.storyteller_id,
    )
