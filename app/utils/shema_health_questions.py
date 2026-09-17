"""The guiding questions, versioned — so an answer stays interpretable after the text moves.

**The questions are provisional and the answers are not.** FE-37 is where the client settles
what the four dimensions actually ask; the console's wizard asks something today, mentors are
already answering it, and the day the wording changes every row already in
``shema_health_assessments`` becomes an answer to a question nobody can quote. So a row records
the **version of the set it answered**, and this file is the table those versions are read out
of.

**What a version is, and what it deliberately is not.** A set is the dimensions asked and the
i18next key of each question — never the rendered sentence. ``docs/shema.md`` §4.11 is explicit
that this server serves keys and data and never rendered labels, and the same rule is what
makes a version cheap: the Portuguese and the English of ``health_q_emotional`` live in the
console's catalogue, in two files a translator edits, and nothing here has to be redeployed
when a comma moves. A **question** changing is a new key and a new version; a **translation**
changing is neither.

**A published version is never edited.** Appending is the only way the tuple below grows, and
that is the whole mechanism: an answer stamped ``1`` must mean the same thing in a year as it
means today, and the only way to guarantee that is for version 1 to be immutable. A reviewer
who sees an edit inside :data:`QUESTION_SETS` rather than a new entry beside it is looking at
the defect this file exists to prevent.

**Why this is a Python table and not a database one.** A version cannot be added by data
alone: a new question needs a key in the console's i18next catalogue before it can be
rendered, and that is a frontend deploy. A row inserted here with no catalogue entry would be
a question with no text — a set the server believes in and no mentor can read. So the two
halves ship together, and the half that lives on this side is a constant, the way
``app/utils/shema_books.py`` holds FE-44's 66 books rather than seeding them.

It is in ``app/utils/`` for ``docs/shema.md`` §3.1's reason: Pydantic response models need it,
and ``tests/test_app_boots.py::test_no_dto_module_reaches_up_into_the_service_layer`` forbids a
model from importing ``app/services/``.
"""

from __future__ import annotations

import enum
from typing import Final, NamedTuple


class ShemaHealthDimension(enum.StrEnum):
    """The four things an assessment asks about, in FE-44's own order.

    Not in ``app/db/models/shema_enums.py`` with the stored vocabularies because **no column
    holds it**: the dimensions are four columns on the assessment and four keys inside its
    ``dimension_notes`` document, so a native PostgreSQL enum would be a migration for a value
    that is never written. :class:`~app.utils.shema_derivations.OverallHealth` and
    :class:`~app.models.shema_privacy.ShemaAudience` are the same call made twice already.

    The order is content and not alphabetical: it is the order the wizard asks in, which is the
    order the running note is compiled in, so the blob reads the way the conversation went.
    """

    EMOTIONAL = "emotional"
    RELATIONAL = "relational"
    SPIRITUAL = "spiritual"
    PHYSICAL = "physical"


#: The four, as a tuple, for everything that has to walk them in order.
DIMENSIONS: Final[tuple[ShemaHealthDimension, ...]] = tuple(ShemaHealthDimension)


class HealthQuestion(NamedTuple):
    """One dimension and the i18next key of the question asked about it."""

    dimension: ShemaHealthDimension
    question_key: str


class HealthQuestionSet(NamedTuple):
    """One published set of guiding questions, addressed by its version.

    :attr:`version` is an integer and not a date: it is the thing a stored answer points at,
    and an integer is the only spelling of that pointer a client cannot get subtly wrong.
    """

    version: int
    questions: tuple[HealthQuestion, ...]

    def asks(self, dimension: ShemaHealthDimension) -> str | None:
        """The i18next key this set asked about ``dimension``, or ``None`` if it did not ask.

        A later set may drop a dimension — the four are the product's today and FE-37 has not
        spoken — and a set that never asked about one is why this answers ``None`` rather than
        raising: a stored rating for a dimension the set did not ask is a real inconsistency,
        and the caller that cares is the one that should say so.
        """
        return next((q.question_key for q in self.questions if q.dimension is dimension), None)


#: Every set that has ever been published, oldest first. **Append only** — see the module
#: docstring.
#:
#: Version 1 is the console's ``HEALTH_DIMENSIONS`` as it stands (``src/constants/health.ts``),
#: key for key. The keys are copied rather than renamed because they are the catalogue's own
#: and a translation table between two spellings of one vocabulary is a second place to be
#: wrong — the same argument ``docs/shema.md`` §2.3 makes for keeping the four role keys
#: camelCase.
QUESTION_SETS: Final[tuple[HealthQuestionSet, ...]] = (
    HealthQuestionSet(
        version=1,
        questions=tuple(
            HealthQuestion(dimension, f"health_q_{dimension.value}") for dimension in DIMENSIONS
        ),
    ),
)

#: What a submission is stamped with when it does not say which set it answered.
CURRENT_QUESTION_SET: Final[HealthQuestionSet] = QUESTION_SETS[-1]

_BY_VERSION: Final[dict[int, HealthQuestionSet]] = {s.version: s for s in QUESTION_SETS}


def question_set(version: int) -> HealthQuestionSet | None:
    """The set published under ``version``, or ``None`` when no such version exists.

    ``None`` and not a fallback to the current set: answering *here is what we ask now* to a
    question about what was asked then is the single most misleading thing this file could do,
    and it is what a caller would build on without noticing.
    """
    return _BY_VERSION.get(version)


def known_versions() -> tuple[int, ...]:
    """Every published version, oldest first — what a submission may be stamped with."""
    return tuple(s.version for s in QUESTION_SETS)
