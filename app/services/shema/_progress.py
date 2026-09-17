"""FE-44 §7.2's ``applyProgressUpdate``, server-side — the module's **single** progress writer.

Two rules travel with this file and neither is negotiable by a later caller.

**The history entry is produced here and never accepted from a client.** The previous values
are the server's own read of the record before the write; a client that could send them could
rewrite the trail the ETEN year-end reconstruction is rebuilt from (FE-44 §7.2). That is why
``app/models/shema.py`` carries no ``progressHistory`` key at all — the rule is an absence in
the request shape rather than a check somebody has to run.

**An imported update and a typed update go through the same function.** FE-44 §9.9 asks that
the two be indistinguishable afterwards, and the way to get that is for there to be one
function — which is why :func:`record_progress` takes ``source`` (BE-12's ``fromField`` and
``formType``) even though the record's own ``PATCH`` never fills it: a second writer that
learned to stamp provenance would be a second reading of *what counts as a change*.

**Only the tables that can express counts are rolled.** ``bookProgress`` and ``otherProgress``
have the three count columns; a story row has none, so a story-only table leaves the
aggregates alone instead of zeroing them. FE-44 §7.2 records this as a deliberate divergence
from the prototype's own roll-up, which included story rows and would overwrite counts the
form has no field to restore.

**The stamp is the actor's local day.** ``docs/shema.md`` §6.5's year-end boundary: in UTC-3 a
save after 21:00 lands on tomorrow's UTC date, and on 31 December in the next *year*, which is
exactly the boundary FE-44 §7.8's credit rule counts against. The day is the caller's to state
and this file only takes it — ``app/api/shema/projects.py`` is where it is read off the
request and bounded.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from datetime import date
from typing import Any, NamedTuple

from app.db.models.shema_progress import ShemaProgressEntry


class Aggregates(NamedTuple):
    """The four numbers the record carries and the history entry snapshots."""

    translated: int
    community: int
    approved: int
    total: int


class ProgressSource(NamedTuple):
    """Where an update came from, when it came from a form — FE-44's ``fromField``/``formType``.

    ``form_type`` is a free string and deliberately not the ``FormKind`` union: the values the
    product actually writes are ``full`` — the prototype's own generator mode — and ``field``,
    neither of which is a ``FormKind``, so typing it as the union rejects the prototype's own
    value on the first import (FE-44 §12.9).
    """

    from_field: str | None = None
    form_type: str | None = None


def _as_count(value: Any) -> int:
    """A progress cell as a number — ``Number(value) || 0``, which is what the console does.

    The rows are a JSON document and a cell can legitimately arrive as a string from an import
    that never went through the typed request shape (BE-12). Refusing here would make the
    roll-up the place a Pulse import fails; answering zero is what the frontend does and is
    what keeps one implementation of the sum.
    """
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return 0
    return number


def roll_up(counted: Iterable[Mapping[str, Any]]) -> Aggregates | None:
    """Sum the rows that carry counts, or ``None`` when there are none to sum.

    ``None`` and not a zeroed :class:`Aggregates`, and the distinction is the whole rule: *no
    counted rows* means the aggregates on the record stand as they are, while a zeroed roll
    would overwrite them with numbers no screen can restore.
    """
    rows = list(counted)
    if not rows:
        return None
    return Aggregates(
        translated=sum(_as_count(row.get("translated")) for row in rows),
        community=sum(_as_count(row.get("communityChecked")) for row in rows),
        approved=sum(_as_count(row.get("mentorApproved")) for row in rows),
        total=sum(_as_count(row.get("chapters")) for row in rows),
    )


def with_rolled_aggregates(
    *,
    book_progress: Sequence[Mapping[str, Any]],
    other_progress: Sequence[Mapping[str, Any]] | None,
    stated: Aggregates,
) -> Aggregates:
    """``withRolledAggregates``: the tables win, except over a scope they cannot express.

    ``stated`` is what the payload leaves on the record — the values a client typed on the
    progress tab's own totals, or what was already stored. The tables override the three
    counts whenever there is a counted row at all, and override the **total** only when the
    roll is above zero: a table of books nobody has scoped yet sums to zero chapters, and
    letting that erase a project's 260 is the one case where the tables know less than the
    record does.
    """
    roll = roll_up([*book_progress, *(other_progress or [])])
    if roll is None:
        return stated
    return Aggregates(
        translated=roll.translated,
        community=roll.community,
        approved=roll.approved,
        total=roll.total if roll.total > 0 else stated.total,
    )


def record_progress(
    project_id: str,
    *,
    previous: Aggregates | None,
    current: Aggregates,
    book_progress: Sequence[Mapping[str, Any]],
    story_progress: Sequence[Mapping[str, Any]],
    other_progress: Sequence[Mapping[str, Any]] | None,
    day: date,
    source: ProgressSource | None = None,
) -> ShemaProgressEntry | None:
    """The entry this save owes the trail, or ``None`` when no aggregate moved.

    **Only if an aggregate changed**, which is FE-44 §7.2's own condition and what keeps the
    trail a record of progress rather than a log of saves: a coordinator fixing a typo in the
    status comments has not moved a count, and an entry saying so would put a flat line through
    every report that reads this table.

    ``previous`` is ``None`` on a create, where the condition is different and is the
    contract's: an entry is written when the record is **born with counts**, marked
    :attr:`ShemaProgressEntry.initial`, so a project imported mid-flight has a starting point
    to measure from. A record created at zero gets no entry — there is nothing to say.

    The entry **snapshots the three tables**, including the story table the roll ignores. That
    is what makes ``progressAsOf`` a point-in-time reader rather than a guess, and what the
    ETEN year-end reconstruction reads.

    Returned rather than added to a session: the caller owns the transaction, and this function
    has no opinion about when the save is durable.
    """
    if previous is None:
        moved = any((current.translated, current.community, current.approved))
    else:
        moved = previous != current
    if not moved:
        return None

    entry = ShemaProgressEntry(
        project_id=project_id,
        entry_date=day,
        translated_units=current.translated,
        community_checked_units=current.community,
        approved_units=current.approved,
        total_units=current.total,
        book_progress=[dict(row) for row in book_progress],
        story_progress=[dict(row) for row in story_progress],
        other_progress=None if other_progress is None else [dict(row) for row in other_progress],
        initial=previous is None,
        from_field=None if source is None else source.from_field,
        form_type=None if source is None else source.form_type,
    )
    if previous is not None:
        entry.previous_translated = previous.translated
        entry.previous_community = previous.community
        entry.previous_approved = previous.approved
    return entry
