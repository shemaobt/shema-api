"""The field-by-field trail: one diff, one key space, two append-only tables (BE-15).

GATE-02's D7 answered *"sim, sempre mantenha os históricos das mudanças"* (OBT-448,
27/aug/2026) over **both** the solicitação and the avaliação, at the granularity of its
own example — *"quem subiu uma nota de 2 para 5"*. BE-02 gave the answer its two tables,
``rr_request_field_history`` and ``rr_evaluation_field_history``; this module is what
writes them.

**One key space reaches the three homes a request's fields live in** — the six promoted
spine columns, the 45 answers inside ``rr_request_sections.content`` and the 26 rows of
``rr_budget_lines`` — because ``document()`` already merges the first two back into
``fields`` and carries the budget beside them. ``document_fields`` flattens that document:

* ``request_type``, ``currency``, ``declaration`` — the three top-level answers, by name.
* every key of ``fields`` — the 45 answers, the six promoted ones among them, so a trail
  reader never has to know which six are columns (the same promise the read path makes).
* ``budget.<category_key>.<column>`` — one key per cell of the budget grid, which is what
  lets the trail say *who changed the amount of* ``mat_didatico`` rather than *the budget
  changed*.
* ``langs``, ``team``, ``chrono``, ``checks.teamtype``, ``checks.trainformat`` — one key
  per table, its value the rows as canonical JSON. A table is the answer to one question,
  and rows have no stable identity: keyed by position, inserting a row above another would
  record a cascade of edits nobody made.

**Values are the wire's own strings**, taken from the flattened document on both sides,
so the trail records exactly what a reader of the API sees — ``1200.50`` after the money
render, never a ``Decimal`` repr. ``None`` means the key had no value at all (a question
the type does not ask, a budget cell not yet present); ``""`` means asked and not
answered. That is the contract's own distinction, kept where the mesa will read it.

**A creation writes no trail.** The trail records *changes*, and a birth is recorded by
``created_by``/``created_at`` on the document itself; every past state, the initial one
included, reconstructs from the current document walked backwards through the trail. The
same holds for ``open_revision`` (a copy into a new row, its provenance in
``revision_of_id``) and ``submit_request`` (``submitted_at`` is not a form field). The one
hook in the base is therefore ``update_draft``, and it is wired.

**The writers add rows and never commit**: the trail rides the same transaction as the
write it describes, because a trail that can miss its own write — written after a commit
that then fails, or committed while the write rolls back — is not a trail. ``changed_at``
is stamped here in Python rather than left to the column's ``server_default``: one shared
instant per save, so the rows of one save read as one event, at microsecond precision —
SQLite's ``CURRENT_TIMESTAMP`` is second-grained, and a trail whose rows tie cannot be
ordered.

**The avaliação half is delivered ahead of its endpoints.** The evaluation routes are
BE-06's (OBT-455, backlog) and do not exist in this base, so ``evaluation_fields`` and
``record_evaluation_trail`` are tested at the service level here and wired to nothing;
BE-06 threads them through its write path the way ``update_draft`` threads the request
half. Its key space is the model docstring's: a criterion key for a score, ``decision``
and ``comments`` for the two fields that are not scores.
"""

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, NamedTuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.resource_request import (
    RRDecision,
    RREvaluationFieldHistory,
    RRRequestFieldHistory,
)

_TABLES = ("langs", "team", "chrono")
_CHECK_GROUPS = ("teamtype", "trainformat")
_BUDGET_CELLS = ("description", "quantity", "amount")


class FieldChange(NamedTuple):
    """One field that moved: from what, to what."""

    field_key: str
    old_value: str | None
    new_value: str | None


def _canonical(value: Any) -> str:
    """Rows as JSON that two runs render identically, so equality is not about spacing."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def document_fields(doc: Mapping[str, Any]) -> dict[str, str | None]:
    """Flatten a ``document()`` into the trail's key space.

    Takes the document and not the ORM rows, so both sides of a diff go through the one
    serializer the module has — the trail then records what the read path shows, byte for
    byte, and cannot drift from it.
    """
    flat: dict[str, str | None] = {
        "request_type": doc["request_type"],
        "currency": doc["currency"],
        "declaration": "true" if doc["declaration"] else "false",
    }
    flat.update(doc.get("fields", {}))

    for table in _TABLES:
        flat[table] = _canonical(doc.get(table, []))
    checks = doc.get("checks", {})
    for group in _CHECK_GROUPS:
        flat[f"checks.{group}"] = _canonical(checks.get(group, []))

    for line in doc.get("budget", []):
        prefix = f"budget.{line['category_key']}"
        for cell in _BUDGET_CELLS:
            flat[f"{prefix}.{cell}"] = line[cell]

    return flat


def evaluation_fields(
    decision: RRDecision | None,
    comments: str,
    scores: Mapping[str, int | None],
) -> dict[str, str | None]:
    """Flatten an evaluation's writable fields into the trail's key space.

    Takes plain values rather than ORM rows on purpose: BE-06 will hold the stored side as
    rows and the incoming side as a payload, and one flattener that both go through is
    what keeps the two sides of its diff comparable. A ``None`` score is *not scored*,
    which is not a scored zero, and stays ``None`` — the side D7's own example starts from
    when a criterion is scored for the first time.
    """
    flat: dict[str, str | None] = {
        "decision": None if decision is None else decision.value,
        "comments": comments,
    }
    for criterion_key, score in scores.items():
        flat[criterion_key] = None if score is None else str(score)
    return flat


def field_changes(
    before: Mapping[str, str | None], after: Mapping[str, str | None]
) -> list[FieldChange]:
    """The keys that moved, sorted, with both sides of each.

    A key on one side only is a field that gained or lost its value entirely — a type
    change un-asks questions, a budget line appears — and the missing side is ``None``.
    """
    keys = sorted(set(before) | set(after))
    return [
        FieldChange(key, before.get(key), after.get(key))
        for key in keys
        if before.get(key) != after.get(key)
    ]


def record_request_trail(
    db: AsyncSession,
    request_id: str,
    changed_by: str,
    before: Mapping[str, str | None],
    after: Mapping[str, str | None],
) -> list[RRRequestFieldHistory]:
    """Add one trail row per field that moved, in the caller's open transaction."""
    now = datetime.now(UTC)
    rows = [
        RRRequestFieldHistory(
            request_id=request_id,
            field_key=change.field_key,
            old_value=change.old_value,
            new_value=change.new_value,
            changed_by=changed_by,
            changed_at=now,
        )
        for change in field_changes(before, after)
    ]
    db.add_all(rows)
    return rows


def record_evaluation_trail(
    db: AsyncSession,
    evaluation_id: str,
    changed_by: str,
    before: Mapping[str, str | None],
    after: Mapping[str, str | None],
) -> list[RREvaluationFieldHistory]:
    """The avaliação's half of the trail, notas included — BE-06 wires it to endpoints."""
    now = datetime.now(UTC)
    rows = [
        RREvaluationFieldHistory(
            evaluation_id=evaluation_id,
            field_key=change.field_key,
            old_value=change.old_value,
            new_value=change.new_value,
            changed_by=changed_by,
            changed_at=now,
        )
        for change in field_changes(before, after)
    ]
    db.add_all(rows)
    return rows
