"""What a client sends about a team's health, and what the module answers back.

``app/models/shema_record.py`` holds the **read** side of one assessment —
:class:`~app.models.shema_record.ShemaHealthAssessmentEntry`, which is FE-44's
``HealthAssessment`` and travels inside the record's ``healthHistory``. This file is the other
two halves: what the wizard posts, and the provenance table a past answer is read against.

**The submission carries more than the assessment, and FE-44 §9.4 is why.** What
``applyAssessment`` produces is one screen's worth of a conversation: the four ratings with
their per-dimension notes, the pastoral answer the mentor and the team agreed on, and — *only
when one was actually written* — a prayer request with its visibility. Those last five are
columns on the record rather than on the assessment, and splitting them into a second
``PATCH`` would mean a wizard whose second call can fail after the first landed. So they
arrive here and the service writes everything under one commit.

**Three keys the record's own write accepts and this one refuses**, because accepting them
would give the projection a second writer: ``healthEmotional`` and its three siblings,
``healthAssessmentDate``, ``healthAssessor`` and ``healthNotes`` are the *projection of the
newest entry* (``docs/shema.md`` §5.3) and ``extra="forbid"`` is what makes the refusal a 422
naming the key rather than a silent drop. ``app/models/shema.py``'s module docstring states
the rule from the other side; this is the endpoint it names.

**The running note is derived and not accepted as the truth.** ``dimensionNotes`` is the data
and ``notes`` is a reading of it (FE-44 §5.2). A client may still send ``notes`` and it is used
**only** when no per-dimension note arrived — a Pulse import or an older console has the blob
and never had the parts — so one source wins wherever there is one, and the blob is a fallback
rather than a second truth.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import (
    AliasGenerator,
    BaseModel,
    ConfigDict,
    field_validator,
    model_validator,
)
from pydantic.alias_generators import to_camel

from app.db.models.shema_enums import (
    ShemaHealthLevel,
    ShemaPrayerVisibility,
    ShemaYesNo,
)
from app.utils.shema_health_questions import (
    DIMENSIONS,
    QUESTION_SETS,
    HealthQuestionSet,
    ShemaHealthDimension,
    known_versions,
)

#: ``datetime.date`` under a second name, for the field FE-44 calls ``date`` — the same
#: aliasing ``app/models/shema_record.py`` needs and for the same reason: a field whose name
#: shadows its own annotation is a model Pydantic cannot build.
Day = date

#: camelCase inward, the house's snake_case still accepted — BE-06's ``_INWARD``, unchanged so
#: that a client posts an assessment in the spelling it posts a record in.
_INWARD = ConfigDict(
    extra="forbid",
    populate_by_name=True,
    alias_generator=AliasGenerator(validation_alias=to_camel),
)

_OUTWARD = ConfigDict(
    from_attributes=True,
    populate_by_name=True,
    alias_generator=AliasGenerator(serialization_alias=to_camel),
)

#: The record-side fields a submission may carry, as column names. The service applies
#: whichever of them arrived and leaves the rest untouched.
#:
#: **A list and not five attribute reads**, which is what keeps ``prayer_requests`` from having
#: a second reader: ``app/services/shema/_consent.py`` owns that column, and a service that
#: names it would be the defect ``tests/test_shema/test_privacy_owners.py`` exists to catch.
#: ``app/services/shema/_audit.py`` makes the same choice for the same reason and states it —
#: a write driven by a list singles nothing out, so there is nothing targeted to see.
RECORD_FIELDS: tuple[str, ...] = (
    "needs_pastoral_intervention",
    "pastoral_intervention_name",
    "pastoral_intervention_when",
    "prayer_requests",
    "prayer_visibility",
)


def compile_notes(dimension_notes: dict[str, str] | None) -> str:
    """The running note, derived from the per-dimension ones — FE-44 §5.2's ``compileNotes``.

    In the dimensions' own order, which is the order the wizard asks in, so the blob reads the
    way the conversation went. Empty notes are dropped rather than leaving blank paragraphs.

    **No dimension label is prefixed**, and that is the rule rather than a spartan choice:
    ``docs/shema.md`` §4.11 is explicit that this server serves keys and data and never rendered
    labels, and writing ``emotional:`` into a blob a console prints verbatim would put an
    untranslated identifier in front of a reader. The attribution lives in ``dimensionNotes``,
    which travels beside the blob on every read.
    """
    if not dimension_notes:
        return ""
    written = [
        note.strip()
        for note in (dimension_notes.get(dimension.value, "") or "" for dimension in DIMENSIONS)
        if note.strip()
    ]
    return "\n\n".join(written)


class ShemaHealthAssessmentSubmission(BaseModel):
    """One filled wizard: the four ratings, the notes, the pastoral answer, maybe a request.

    Every health field is ``| None`` and ``None`` means *not rated*, which is the transport's
    ``""`` arriving as the column's NULL. The four are all optional and **at least one must be
    rated** — see :meth:`_an_assessment_rates_something`.
    """

    model_config = _INWARD

    #: The day the reading happened, which is the mentor's to state: a visit written up on
    #: Monday happened on Friday, and the history is ordered by this rather than by the moment
    #: the row was inserted. Absent means today, resolved by the caller against the actor's own
    #: local day (``X-Shema-Local-Date``) rather than the server's.
    date: Day | None = None
    #: The person who read the team, as their name was then. Absent falls back to the author's
    #: own name, so the field is never a hole on a row somebody did file.
    assessor: str | None = None

    emotional: ShemaHealthLevel | None = None
    relational: ShemaHealthLevel | None = None
    spiritual: ShemaHealthLevel | None = None
    physical: ShemaHealthLevel | None = None

    #: ``{emotional?, relational?, spiritual?, physical?}`` — the data the blob is read off.
    dimension_notes: dict[str, str] | None = None
    #: Used **only** when no per-dimension note arrived; otherwise derived. See the module
    #: docstring.
    notes: str | None = None

    #: Which published set of guiding questions the wizard rendered. Absent means the current
    #: one; an unknown version is refused rather than coerced, because the whole value of the
    #: stamp is that it is true.
    question_set_version: int | None = None

    needs_pastoral_intervention: ShemaYesNo | None = None
    pastoral_intervention_name: str | None = None
    pastoral_intervention_when: str | None = None

    #: Sent **only when one was written** (FE-44 §8.2, ``docs/shema.md`` §7.4): an
    #: unconditional ``""`` on every assessment deletes an existing request as a side effect of
    #: an unrelated act, so *not sent* has to be a state this shape can express — which is what
    #: ``None`` plus ``model_fields_set`` is for.
    prayer_requests: str | None = None
    prayer_visibility: ShemaPrayerVisibility | None = None

    @field_validator("emotional", "relational", "spiritual", "physical", mode="before")
    @classmethod
    def _an_empty_rating_is_not_a_rating(cls, value: Any) -> Any:
        """``""`` is the transport's word for *not assessed*; the column's word is NULL.

        FE-44's ``HealthRating`` is ``HealthLevel | ""`` and a ``<select>`` needs the empty
        option, so the console legitimately sends it. Mapping it to NULL here is what keeps the
        database's three-member enum and the wire's four-value union from being two
        vocabularies — and it is the one translation that must never go the other way, because
        ``""`` becoming ``boa`` is the failure ``docs/shema.md`` §7.4 names.
        """
        return None if value == "" else value

    @field_validator("dimension_notes")
    @classmethod
    def _a_note_belongs_to_a_dimension(cls, value: dict[str, str] | None) -> dict[str, str] | None:
        """The document's keys are the four dimensions and nothing else.

        ``extra="forbid"`` cannot reach inside a ``dict`` field, and this one is stored as JSON —
        so a typo would be persisted silently and read back as a note belonging to no dimension.
        Named rather than dropped: a mentor whose paragraph vanished because a key was
        misspelled has lost the part of the assessment that carries the meaning.
        """
        if value is None:
            return None
        known = {dimension.value for dimension in ShemaHealthDimension}
        unknown = sorted(set(value) - known)
        if unknown:
            raise ValueError(f"{', '.join(unknown)}: not a health dimension")
        return value

    @field_validator("question_set_version")
    @classmethod
    def _the_set_has_to_exist(cls, value: int | None) -> int | None:
        """A version this server has never published is refused, not rounded to the nearest.

        ``app/utils/shema_health_questions.py`` explains why its lookup answers ``None`` instead
        of falling back; this is the same sentence at the door. A client one deploy ahead of the
        server is a real situation and the honest answer to it is *I do not know that set*.
        """
        if value is not None and value not in known_versions():
            raise ValueError(
                f"{value}: not a published question set — this server knows "
                f"{', '.join(str(v) for v in known_versions())}"
            )
        return value

    @model_validator(mode="after")
    def _an_assessment_rates_something(self) -> ShemaHealthAssessmentSubmission:
        """A submission that rates no dimension is not an assessment and is refused.

        ``docs/shema.md`` §7.4 and FE-44 §7.4 both say the same thing from the reading side: a
        ``healthAssessmentDate`` with four unrated dimensions reports a team as *heard* when
        nobody rated it, and ``isAssessed`` — at least one dimension rated — is what gates every
        count of an assessment, Rhythm's readiness included. Accepting an empty one here would
        manufacture exactly that row.

        Notes alone are not enough, deliberately: a paragraph with no rating is a note on the
        record (``notes``, ``needsNotes``) and the record's ``PATCH`` is where it belongs. What
        this endpoint files is a **reading**.
        """
        if all(getattr(self, dimension.value) is None for dimension in DIMENSIONS):
            raise ValueError(
                "an assessment rates at least one of "
                f"{', '.join(d.value for d in DIMENSIONS)} — a date with no rating would "
                "report the team as heard when nobody rated it"
            )
        return self

    def running_note(self) -> str:
        """What to store in ``notes`` — derived from the parts, or the blob when there are none."""
        if self.dimension_notes:
            return compile_notes(self.dimension_notes)
        return (self.notes or "").strip()


class ShemaHealthQuestionOut(BaseModel):
    """One dimension and the i18next key of the question a set asked about it."""

    model_config = _OUTWARD

    dimension: ShemaHealthDimension
    question_key: str


class ShemaHealthQuestionSetOut(BaseModel):
    """One published set, as the console reads it back."""

    model_config = _OUTWARD

    version: int
    questions: list[ShemaHealthQuestionOut]

    @classmethod
    def of(cls, question_set: HealthQuestionSet) -> ShemaHealthQuestionSetOut:
        return cls(
            version=question_set.version,
            questions=[
                ShemaHealthQuestionOut(dimension=q.dimension, question_key=q.question_key)
                for q in question_set.questions
            ],
        )


class ShemaHealthQuestionCatalogue(BaseModel):
    """Every set of guiding questions this server has published, and which one is current.

    **This is provenance, not a rendering source, and the distinction is the whole reason the
    route exists.** The console renders the wizard from its own frozen ``HEALTH_DIMENSIONS``
    and its i18next catalogue; serving a second copy of *what to render* would be the second
    owner this module spends files avoiding. What the console cannot answer is *what did set 1
    ask*, on the day it ships set 2 — and that is exactly the question an entry stamped ``1``
    raises. So this answers the history of the sets, current one included because a client that
    wants to stamp its submissions has to know which that is.
    """

    model_config = _OUTWARD

    current: int
    sets: list[ShemaHealthQuestionSetOut]

    @classmethod
    def published(cls) -> ShemaHealthQuestionCatalogue:
        return cls(
            current=QUESTION_SETS[-1].version,
            sets=[ShemaHealthQuestionSetOut.of(question_set) for question_set in QUESTION_SETS],
        )
