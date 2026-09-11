"""What the intake link serves, what a submission may say, and what a coordinator reads back.

Four surfaces and one rule between them: **the public form is the narrow one**. Everything a
signed-in coordinator sees of a submission is here too, and the two are deliberately not the
same shape — a link forwarded through WhatsApp reaches whoever it reaches, and the question is
never *who did we mean to send it to*.

**The intake form is a leaving shape, and it declares no field of a place.** Both halves of
that sentence are the decision. It carries the definition, the language name and when the link
dies, and nothing else: OBT-401 asks for *the minimum that makes the form answerable*, and a
submission form that also reads the record turns a forwarded message into a disclosure.
``tests/test_shema/test_intake_link.py`` pins the key list and then pins the stronger claim —
that no value from any column of the project appears anywhere in the response — because an
allowlist of keys is a test of what somebody wrote down and the DoD's fourth line is a claim
about what leaves.

**It inherits** :class:`~app.models.shema_privacy.LeavingShape` **anyway**, and the *anyway* is
the point. BE-04's route audit only fires on a shape that declares a place field, so a shape
with none passes whether or not it inherits — which makes inheriting a choice here rather than
a requirement. It is the choice that survives the next edit: the day somebody adds ``location``
so the leader can confirm which project they are answering for, the boundary is already
underneath the shape and the field arrives redacted instead of arriving. That is BE-04's own
argument — a rule applied by *declaring a field* is the one act an author cannot skip — taken
at a surface where the rule has nothing to do yet.

``locationWithheld`` is therefore **always true here and says nothing**: the shape passes no
``sensitive_country``, so the fail-closed default stands and the bit is a constant. A shape
that answered it honestly would be answering *is this project in a sensitive country* to an
anonymous link-holder, which is one bit of project data the form does not need.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import AliasGenerator, BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.models.shema_privacy import LeavingShape
from app.utils.shema_forms import MAX_FREE_TEXT

_OUTWARD = ConfigDict(
    from_attributes=True,
    populate_by_name=True,
    alias_generator=AliasGenerator(serialization_alias=to_camel),
)

_INWARD = ConfigDict(
    extra="forbid",
    populate_by_name=True,
    alias_generator=AliasGenerator(validation_alias=to_camel),
)


class IntakeField(BaseModel):
    """One question, as the form renders it — the stored spec minus what the client may not see.

    ``column`` is dropped on the way out, and not for tidiness: the spec's mapping names record
    columns, three of which the consent gate guards, and publishing *which column a prayer
    request lands in* to an unauthenticated caller is a description of the record's shape that
    the form does not need in order to be answerable.

    ``labelKey`` and never a sentence: the console owns the copy, in both languages, and a
    server that shipped Portuguese strings would be putting unapproved client-facing wording
    in front of a field team on nobody's decision.
    """

    model_config = _OUTWARD

    key: str
    type: str
    required: bool
    label_key: str
    max_length: int | None = None
    options: list[str] = Field(default_factory=list)


class IntakeForm(LeavingShape):
    """What ``GET /api/shema/intake/{token}`` answers — the whole of what the link grants.

    ``definitionVersion`` is in the payload because the answer has to name it: the client posts
    it back, the server checks it against the version the **link** was minted with, and a
    mismatch is refused rather than silently re-read against today's definition. That is the
    difference between a form that is versioned and a form that merely has versions.
    """

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        alias_generator=AliasGenerator(serialization_alias=to_camel),
    )

    kind: str
    definition_version: int
    #: The one thing of the project the form carries, and it is what makes the form
    #: answerable: a leader holding two links has to be able to tell them apart. It is not a
    #: guarded field — ``app/models/shema_privacy.py``'s list is places, bases and contacts —
    #: and it is already what ``shema_submissions`` snapshots for the same reason.
    language_name: str
    #: A calendar day, like every date on this product's wire (FE-44 §9.0).
    expires_at: date
    fields: list[IntakeField]


class IntakeSubmission(BaseModel):
    """What a leader posts back through the link.

    ``answers`` is an untyped map **on purpose**, and this is the one shape in the module where
    that is the right answer: the keys are the definition's, the definition is a row, and a
    Pydantic model cannot be a function of a database row. So the envelope is typed and refuses
    everything around the answers, and the answers themselves are checked against the stored
    spec by ``app/services/shema/_form_validation.py`` — which is where *rejected whole on
    mismatch* lives, because it is the only place that knows what the form said.

    ``definitionVersion`` is required. A submission that cannot say which version it answered
    is a submission somebody has to guess about later, and the guess is always *the newest*,
    which is the one answer that is wrong by construction.
    """

    model_config = _INWARD

    definition_version: int
    answers: dict[str, Any]


class IntakeLinkCreate(BaseModel):
    """What a coordinator asks for when they mint a link.

    ``projectId`` is **required**, against FE-44 §9.9's own ``{projectId?, expiresAt}``. The
    optional spelling has no meaning the DoD allows: *project-scoped* is the first word of the
    line this credential is judged by, and a link with no project is a link to all of them.

    ``expiresAt`` is optional and defaults, because a coordinator on a phone should not have to
    compute a date for the link to be safe — the default is a real expiry, not *never*.
    """

    model_config = _INWARD

    project_id: str = Field(min_length=1, max_length=120)
    expires_at: date | None = None


class IntakeLink(BaseModel):
    """A link as its coordinator sees it — everything but the token.

    The raw token is in :class:`IntakeLinkCreated` and leaves exactly once, which is what every
    other token in this repository does (``refresh_tokens``, ``password_reset_tokens``,
    ``access_invites``) and what the stored SHA-256 is for. A listing that could hand the token
    back would make *revoked* a word rather than a fact, because the credential would still be
    readable by anyone who can read the list.
    """

    model_config = _OUTWARD

    id: str
    project_id: str
    definition_version: int
    expires_at: date
    #: ``pending`` until the first answer, then ``used``; ``revoked`` and ``expired`` beat both.
    status: str
    created_at: date
    used_at: date | None = None
    revoked_at: date | None = None


class IntakeLinkCreated(IntakeLink):
    """The one response that carries the raw token, and the URL built around it."""

    token: str
    url: str


class ReceivedSubmission(BaseModel):
    """FE-44's ``ReceivedSubmission``, plus the two keys the DoD is proved with.

    ``kind`` is ``ArchivedKind`` — ``"pulso"`` and nothing else. The Avaliação de Saúde is
    filled in-app and produces no file, so nothing of it ever left to come back; a server that
    archived one would have landed a kind that by definition never travelled (FE-44 §5.7).

    ``definitionVersion`` and ``appliedAt`` are additions to a frozen shape and the PR declares
    them. They are additive keys a client may ignore, and each answers a question the inbox
    cannot work without: *which form was this answering*, and *has a person acted on it yet*.

    ``receivedAt`` is a **calendar day**, by FE-44 §9.0's rule that every date on this wire is
    one. The column keeps the moment and the listing is ordered by it, so nothing about the
    ordering rests on the day.
    """

    model_config = _OUTWARD

    id: str
    kind: str
    project_id: str
    language_name: str
    submitted_by: str
    received_at: date
    definition_version: int
    applied_at: date | None = None


class ReceivedSubmissionDetail(ReceivedSubmission):
    """One submission opened — the answers as they arrived, beside the form they answered.

    Without this the archive is write-only, and *a form that is submitted and never seen is
    worse than no form*. It is a coordination surface: authenticated, inside the caller's
    region, and it is where the free-text answers the import deliberately does **not** apply to
    the record — the voice and the blockers — are read by the person who decides what to do
    about them.
    """

    fields: list[IntakeField]
    answers: dict[str, Any]


class SubmissionImport(BaseModel):
    """A submission a coordinator files directly, for a leader who answered some other way.

    The Pulse's whole point is that the person with the information is often offline, so the
    answer arrives on paper, in a voice note, or read out over a bad line. This is that answer
    typed in by somebody who is accountable for it — the same validation, the same archive, the
    same idempotency, and an actor the audit trail can name.

    ``definitionVersion`` is **optional here and required on the link**, which is not an
    inconsistency: the leader was *shown* a version and their answer is read against the one
    they saw, while a coordinator typing today is answering today's form. Stated and unknown is
    still refused; absent means the current published version, and whichever it was is what the
    row records.
    """

    model_config = _INWARD

    project_id: str = Field(min_length=1, max_length=120)
    definition_version: int | None = None
    answers: dict[str, Any]


#: The ceiling on one free-text answer, re-exported so a client can be told it before it types
#: four thousand characters into a phone rather than after.
MAX_ANSWER_LENGTH = MAX_FREE_TEXT
