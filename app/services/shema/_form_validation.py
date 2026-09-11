"""Checking a submission against the definition it answered — and refusing it whole.

**A submission is untrusted input, and the definition is the only thing that says what it may
say.** Three rules travel with this file:

**Rejected whole, and every fault named at once.** Not the first fault — every one of them,
keyed by the field it is in. A leader on a bad connection who is told *"period is not a month"*
and then, on the next attempt, *"prayerVisibility is not one of two words"* has paid twice for
one form, and the second round trip is the one that does not happen. That is the same property
BE-06 gets from Pydantic collecting a list's errors before it raises
(``app/models/shema.py``); here it is a loop that keeps going, for the same reason.

**Nothing is written until everything passes.** The refusal happens before the archive, before
the row and before the record — *never store an unvalidated payload to clean later*, because
later does not come and what is left is a column nobody can interpret. There is no partial
ingest in this module and no state a half-good submission can leave behind.

**What this file does not re-check.** The progress rows are handed to
``app/models/shema.py``'s ``ShemaProjectUpdate``, where BE-06 already refuses a book that is
not one of the 66, a scope longer than the book, and a count above its own row, and where
Pydantic names every bad row by index before raising. A second reading of *what a progress row
is* would drift from that one, and the drift would show as a Pulse the console can save and
the import cannot.

**The empty answer is not an answer, and that is a rule rather than a convenience.** A field
whose answer is absent or empty contributes nothing to the record write. FE-44 §8.2 states the
sharp case: a save that writes ``prayerRequests: ""`` unconditionally **deletes an existing
request as a side effect of an unrelated action** — and a monthly form with an untouched
prayer box would do exactly that, every month, to the team most likely to have written
something the month before.
"""

from __future__ import annotations

import re
from typing import Any

from app.core.exceptions import ValidationError
from app.db.models.shema_form import ShemaFormDefinition
from app.models.shema import ShemaProjectUpdate
from app.utils.shema_forms import ShemaFieldType

#: ``YYYY-MM``. The Pulse is monthly and the period is the month it is about — not a date, not
#: a range, and not a day, because a report filed on the 3rd is about the month that ended.
_PERIOD = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _fault(field: dict[str, Any], answer: Any) -> str | None:
    """What is wrong with one answer, or ``None``.

    One function per **type** rather than per field, so a second instrument added to
    ``app/utils/shema_forms.py`` is validated by this file without touching it. A validator
    written per form is a validator the second form does not get.
    """
    key = field["key"]
    kind = field["type"]
    if kind in (ShemaFieldType.TEXT, ShemaFieldType.LONG_TEXT):
        if not isinstance(answer, str):
            return f"{key}: expected text"
        limit = field.get("maxLength")
        if limit is not None and len(answer) > limit:
            return f"{key}: {len(answer)} characters, and the field holds {limit}"
        return None
    if kind == ShemaFieldType.CHOICE:
        options = field.get("options") or []
        if answer not in options:
            return f"{key}: {answer!r} is not one of {', '.join(options)}"
        return None
    if kind == ShemaFieldType.PERIOD:
        if not isinstance(answer, str) or not _PERIOD.match(answer):
            return f"{key}: {answer!r} is not a YYYY-MM month"
        return None
    if kind == ShemaFieldType.PROGRESS_ROWS:
        if not isinstance(answer, list):
            return f"{key}: expected a list of progress rows"
        return None
    return f"{key}: {kind!r} is a field type this server does not know how to read"


def _is_empty(answer: Any) -> bool:
    """Whether an answer says nothing — the state that writes nothing to the record."""
    if answer is None:
        return True
    if isinstance(answer, str):
        return answer.strip() == ""
    if isinstance(answer, list | dict):
        return len(answer) == 0
    return False


def validated_answers(definition: ShemaFormDefinition, answers: dict[str, Any]) -> dict[str, Any]:
    """The answers, checked against ``definition`` and returned unchanged — or every fault.

    Unchanged is deliberate: what is archived is what arrived, so this function may not
    normalise, trim or coerce. A value the server rewrote on the way in is a value the archive
    can no longer prove the leader sent.

    An **unknown key is a fault**, not something to ignore. A client sending a field this
    version of the form does not have is a client answering a different form — most often the
    next version of this one — and silently dropping it files an answer with a hole in it that
    nothing downstream can see.
    """
    spec = {field["key"]: field for field in definition.fields}
    faults = [f"{key}: this form has no such field" for key in sorted(answers) if key not in spec]

    for key, field in spec.items():
        present = key in answers
        if not present or _is_empty(answers[key]):
            if field["required"]:
                faults.append(f"{key}: required")
            continue
        fault = _fault(field, answers[key])
        if fault is not None:
            faults.append(fault)

    if faults:
        raise ValidationError(
            f"{definition.kind} v{definition.version}: the submission does not match the form, "
            f"so none of it was kept — {'; '.join(sorted(faults))}"
        )
    return answers


def record_update(definition: ShemaFormDefinition, answers: dict[str, Any]) -> ShemaProjectUpdate:
    """The answers, as a partial write of the record — and only the ones that map to a column.

    **The mapping is read off the definition, never written here**, which is what keeps this
    module from being a second reader of the columns
    ``app/services/shema/_consent.py`` guards: no guarded column name appears in this file, in
    ``receive_submission.py`` or in ``import_submission.py``. The spec in
    ``app/utils/shema_forms.py`` holds the names, the write path applies them, and
    ``tests/test_shema/test_privacy_owners.py`` needs no allowlist entry for BE-12.

    **Most of the form is not applied, and that is the decision.** The voice and the blockers
    map to no column: they are archived, shown to the coordinator who opens the submission, and
    acted on by a person. FE-44 §9.9 asks that an imported **progress** change go through the
    same write path as a typed one and asks nothing else of the record — and a Pulse that
    quietly replaced a coordinator's status comments with a leader's free text would be the
    record being edited through the weakest credential in the system.

    Validation of what survives is ``ShemaProjectUpdate``'s, which is BE-06's and is the same
    validation the ficha's own ``PATCH`` meets. A ``pydantic.ValidationError`` from here is the
    progress rows being refused row by row, and the caller lets it become the 422 FastAPI
    already gives a body it could parse and could not accept.
    """
    update: dict[str, Any] = {}
    for field in definition.fields:
        column = field.get("column")
        if column is None:
            continue
        answer = answers.get(field["key"])
        if _is_empty(answer):
            continue
        update[column] = answer
    return ShemaProjectUpdate.model_validate(update)
