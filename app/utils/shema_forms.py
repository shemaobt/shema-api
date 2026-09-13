"""The Pulse's field spec — the definition a submission is validated against, as data.

**Definitions are configured, not designed in-app** (OBT-401's *Out of scope*), so the spec is
authored here, in code, and published into ``shema_form_definitions`` by
``app/services/shema/_form_definitions.py``. There is no builder, no admin endpoint and no
migration that seeds a row: the table holds what this file has said, versioned by the content
of what it said, and an edit here becomes version *n+1* the first time a link is minted. Every
submission already filed keeps answering the version it answered.

**Why** ``app/utils/`` **and not the service package.** Two reasons that agree. The first is
``docs/shema.md`` §3.1's own: a table of pure data that both services and response models
need lives where a response model may reach it, because ``app/models/`` may not import
``app/services/`` (``tests/test_app_boots.py``'s
``test_no_dto_module_reaches_up_into_the_service_layer``).
The second is sharper and is this file's own — :attr:`FormField.column` names record columns,
three of which are guarded by ``app/services/shema/_consent.py``. Keeping the mapping here
means the ingest service never writes a guarded column *name* at all: it hands the definition's
own strings to ``ShemaProjectUpdate`` and the write path does the rest, so
``tests/test_shema/test_privacy_owners.py`` needs no allowlist entry for BE-12 and the gate
keeps exactly one reader. ``app/models/`` is outside that glob for the same reason and
``tests/test_shema/test_privacy_owners.py`` says so in its own words.

**The five questions are FE-44's, not invented here.** ``PULSE_QUESTIONS`` in the console's
``src/constants/forms.ts`` freezes them — voice, photo, chapters, blockers, prayer — and what
GATE-03 still owns is the **serialization**: the format, which of two formats is authoritative
when they disagree, the distribution model, and withdrawal from an already-distributed file
(``docs/shema.md`` §9.3). A field spec is not a file format. Nothing here names an extension,
and nothing here may: wave 1 removed every mention of one from the product's copy.

**The photo is missing, deliberately.** ``forms_q_photo`` has no field because BE-04 *named
and did not build* ``_media_storage.py`` (``docs/shema.md`` §6.4's third declared departure),
and this module's one upload path returns a public bucket URL (FE-44 §3.1). Accepting a file
on an **unauthenticated** route into a public bucket is the fail-open spelling of the rule
FE-44 §8.3 spends a section on. It arrives with the bucket, in the issue that first serves a
file.
"""

from __future__ import annotations

import enum
import hashlib
import json
from collections.abc import Mapping
from typing import Any, Final, NamedTuple


class ShemaFieldType(enum.StrEnum):
    """What an answer to one field may be.

    A small vocabulary on purpose. Each member is a rule ``_form_validation.py`` can apply
    with no knowledge of which form it is applying it to, which is what keeps *rejected whole
    on mismatch* one function rather than one per instrument.

    ``PROGRESS_ROWS`` is the only member that is not a scalar, and it does not validate itself:
    it hands the rows to ``app/models/shema.py``'s ``ShemaProjectUpdate``, where BE-06 already
    refuses a book that is not a book and a scope longer than the book, and where Pydantic
    collects **every** bad row before it raises. Re-checking them here would be a second
    reading of what a progress row is, and the two would drift.
    """

    TEXT = "text"
    LONG_TEXT = "longText"
    CHOICE = "choice"
    PERIOD = "period"
    PROGRESS_ROWS = "progressRows"


class FormField(NamedTuple):
    """One question, and where its answer goes.

    ``column`` is the record column the answer is applied to, or ``None`` for an answer that
    is **archived and not applied**. The distinction is a decision and not a gap: a Pulse that
    silently replaced a coordinator's ``statusComments`` with a leader's free text would be the
    record being edited through the weakest credential in the system, and FE-44 §9.9 asks only
    that an **imported progress change** go through the same write path as a typed one. So the
    voice and the blockers are kept, shown to the coordinator who reads the submission, and
    applied by a person.

    ``label_key`` is an i18n key and never a sentence. The console owns the copy in both
    languages; a server that shipped Portuguese strings would be putting unapproved
    client-facing wording in front of a field team.
    """

    key: str
    type: ShemaFieldType
    required: bool
    label_key: str
    column: str | None = None
    max_length: int | None = None
    options: tuple[str, ...] = ()

    def as_spec(self) -> dict[str, Any]:
        """The row as it is stored and as it is served, in one shape.

        Stored so an old submission stays readable against the definition it answered even
        after this file has moved on; served so the intake form the leader opens *is* the
        definition the answer is checked against, rather than a second rendering of it that
        can disagree.
        """
        return {
            "key": self.key,
            "type": self.type.value,
            "required": self.required,
            "labelKey": self.label_key,
            "column": self.column,
            "maxLength": self.max_length,
            "options": list(self.options),
        }


#: The only kind of submission that is archivable, and the reason ``shema_submissions`` has no
#: ``kind`` column: the Avaliação de Saúde is filled in-app, produces no file and so never left
#: to come back (FE-44 §5.7, ``docs/shema.md`` §5.12). It is ``ArchivedKind``, verbatim.
PULSE_KIND: Final = "pulso"

#: What an imported progress entry stamps in ``ProgressHistoryEntry.formType``.
#:
#: ``docs/shema.md`` §10 item 11 leaves the vocabulary open and hands it to *whoever closes the
#: Pulse*. It stays a **free string** and this is the Pulse's value in it. Narrowing the column
#: to ``FormKind`` would reject the prototype's own ``full`` and ``field`` on the first import
#: (FE-44 §12.9) and would put a cycle in the console's type graph; what this constant buys
#: instead is that the module writes one spelling, from one place.
PULSE_FORM_TYPE: Final = "pulso"

#: The longest free-text answer the intake accepts, per field. Not a product rule — a ceiling
#: on an **unauthenticated** write, so a forwarded link cannot be used to push megabytes into a
#: column. Generous against what a team leader types on a phone and small against what a script
#: would send.
MAX_FREE_TEXT = 4000

#: The Pulso Mensal, question for question.
#:
#: ``submittedBy`` and ``period`` are not among FE-44's five questions and are here for reasons
#: that are not decoration: ``ReceivedSubmission.submittedBy`` is a **snapshot on the row**
#: (``app/db/models/shema_form.py``) and ``fromField`` on the progress entry is the same value,
#: so a form with nowhere to state it could fill neither; and ``period`` is what makes two
#: honest monthly Pulses with identical numbers two submissions instead of one, which the
#: content-hash idempotency would otherwise collapse. A monthly report that cannot say which
#: month it is about is the thing being reported on, not a report.
PULSE_FIELDS: Final[tuple[FormField, ...]] = (
    FormField(
        key="submittedBy",
        type=ShemaFieldType.TEXT,
        required=True,
        label_key="forms_q_submitted_by",
        max_length=200,
    ),
    FormField(
        key="period",
        type=ShemaFieldType.PERIOD,
        required=True,
        label_key="forms_q_period",
    ),
    FormField(
        key="voice",
        type=ShemaFieldType.LONG_TEXT,
        required=False,
        label_key="forms_q_voice",
        max_length=MAX_FREE_TEXT,
    ),
    FormField(
        key="bookProgress",
        type=ShemaFieldType.PROGRESS_ROWS,
        required=False,
        label_key="forms_q_chapters",
        column="book_progress",
    ),
    FormField(
        key="blockers",
        type=ShemaFieldType.LONG_TEXT,
        required=False,
        label_key="forms_q_blockers",
        max_length=MAX_FREE_TEXT,
    ),
    FormField(
        key="prayerRequest",
        type=ShemaFieldType.LONG_TEXT,
        required=False,
        label_key="forms_q_prayer",
        column="prayer_requests",
        max_length=MAX_FREE_TEXT,
    ),
    #: **Absent is not** ``coordenacao`` **written down.** The column is nullable, NULL means
    #: ``coordenacao``, and ``app/services/shema/_consent.py`` is where that is read — so a
    #: leader who says nothing has said *keep it in coordination* without anything being
    #: written (FE-44 §8.2 rule 2, ``docs/shema.md`` §7.4). The field is optional for exactly
    #: that reason and the ingest writes the column only when an answer names one.
    FormField(
        key="prayerVisibility",
        type=ShemaFieldType.CHOICE,
        required=False,
        label_key="forms_q_prayer_visibility",
        column="prayer_visibility",
        options=("coordenacao", "rede"),
    ),
)

#: Every field spec this module publishes, by kind. One entry today, and the shape is what
#: lets a second instrument arrive without a second validator.
FORM_FIELDS: Final[dict[str, tuple[FormField, ...]]] = {PULSE_KIND: PULSE_FIELDS}


def field_specs(kind: str) -> list[dict[str, Any]]:
    """The stored form of one kind's spec, or an empty list when the kind is not published."""
    return [field.as_spec() for field in FORM_FIELDS.get(kind, ())]


def spec_hash(spec: list[dict[str, Any]]) -> str:
    """The identity of a spec's **content**, which is what a version is cut against.

    ``sort_keys`` and a compact separator, so the hash answers *did the definition change* and
    not *did the dictionary come back in a different order* — the second question is one a
    JSON column will eventually ask on its own, and answering it with a new version would
    retire a definition nobody edited.
    """
    payload = json.dumps(spec, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


#: The answer the consent gate governs, by its **wire key**.
#:
#: Named here rather than in a service so that the two ``shema`` packages contain no spelling
#: of a guarded column at all — ``app/services/shema/_consent.py`` stays the only reader of
#: the three prayer columns and BE-12 needs no line in ``test_privacy_owners.py``'s allowlist.
#: This is a form field, not a column: the mapping from one to the other is in
#: :data:`PULSE_FIELDS` above, which is data.
PRAYER_FIELD: Final = "prayerRequest"

#: The answer snapshotted onto ``shema_submissions.submitted_by`` and stamped as
#: ``ProgressHistoryEntry.fromField``. A wire key, named once, for the same reason the one
#: above is: the archive and the progress trail must carry the same name, and two call sites
#: spelling it themselves is how they stop.
SUBMITTED_BY_FIELD: Final = "submittedBy"


def carries_prayer_request(answers: Mapping[str, Any]) -> bool:
    """Whether this submission actually wrote a prayer request.

    Asked separately from *may it travel*, which is
    ``app/services/shema/_consent.py``'s question about the **project** and is not this
    module's to answer. Both have to be true before anything reaches the Resource Circle, and
    keeping them apart is what stops a notice firing for a project that consented last year
    about a form that said nothing this month.
    """
    answer = answers.get(PRAYER_FIELD)
    return isinstance(answer, str) and answer.strip() != ""
