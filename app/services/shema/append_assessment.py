"""Filing one reading of a team's health: append, re-project, and tell somebody if it is critical.

**Append and never overwrite.** Every assessment is a new row with its own date and its own
author, and nothing in this module updates or deletes one. That is the immutability the issue
asks for, and it is a property of this file being the only writer rather than of a database
trigger: ``app/db/models/shema_health.py``'s class docstring argues — convincingly — that a
mentor's typo in a note is a person's to correct, and a trigger would make correcting it
impossible for the issue that eventually builds it. So the door stays open in the schema and
shut in the code, and there is exactly one place to read to know that.

**The flat fields are a projection and this is the one step that moves them.** The four
dimensions, the date, the assessor and the note on ``shema_projects`` are *the newest entry*,
never a second truth (``docs/shema.md`` §5.3). ``app/models/shema.py`` refuses them on the
record's own ``PATCH`` for exactly that reason, so a client cannot report a team as assessed with
no assessment behind it. Appending and re-projecting happen under one commit, which is what makes
*the projection is the newest entry* true at every moment anybody can read it.

**A backdated assessment does not overwrite a newer reading.** The projection is decided by
comparing days, not by assuming the last write wins: a reading filed today for a visit three
months ago is kept in the history and changes nothing on the record, because the team has been
read since. FE-44 §9.4 asks for this in one line and it is the reason the projection is a
comparison rather than an assignment.

**A record that predates the history has its flat fields carried in first.** Otherwise the first
assessment ever filed through this endpoint would silently replace a reading that was already on
the record — from the Notion export, or from BE-16's seed — and the history would start by losing
something. The carried row says what it is: no question set version, because it answered no
questionnaire, and no author, because nobody knows who filed it.

**The order, one transaction, one commit under all of it**, which is ``save_project``'s shape and
for its reason:

1. the record, **inside the caller's scope** — out of scope is refused exactly as absent is;
2. the audience — a narrower question than who may open the record (``_health_audience.py``);
3. the overall reading **before** anything is written, off the flat fields;
4. the carried entry, if the record predates the history;
5. the new entry;
6. the projection, and the record-side fields the submission carried;
7. the edit trail, and the notices if the reading entered critical — staged, committed once.

**There is no** ``If-Match`` **here, and that is a departure from the record's own write.**
``save_project`` requires it because ten tabs edit one row and last-write-wins discards work in
silence. Appending is not that: two mentors filing two readings are two rows and neither is lost,
so a version guard could only refuse one of them — and what it would refuse is a reading of a
team, taken in a conversation, because somebody edited the notes tab while the wizard was open.
The version is still **bumped**, because the record's flat fields moved and a client holding the
old one must learn so; the new value leaves in the ``ETag`` of the reply, exactly as a ``PATCH``'s
does. The cost is real and stated: the prayer request and the pastoral answer a submission may
carry are last-write-wins between two simultaneous wizards on one project. A second wizard open
on the same project at the same time is not a case this product has; losing a mentor's reading is.

**This file names no guarded column.** The five record-side fields a submission may carry —
including ``prayer_requests``, whose one reader is ``_consent.py`` — are applied by name from
``app/models/shema_health.py``'s ``RECORD_FIELDS``, which is the honest differ shape
``_audit.py`` describes and defends: a write driven by a list singles nothing out, so
``tests/test_shema/test_privacy_owners.py``'s glob sees no targeted read and there is nothing
for it to see.

**The pastoral escalation is stored and never derived.** FE-44 §5.9 is explicit that the
suggestion is made with its reasons and never applied — ``needsPastoralIntervention`` stays
``nao`` until a person picks otherwise — so a critical reading does not flip it here. The
notification is what a server may do about a critical reading; changing a field a person owns is
not.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.shema import ShemaProject
from app.db.models.shema_health import ShemaHealthAssessment
from app.models.shema_health import RECORD_FIELDS, ShemaHealthAssessmentSubmission
from app.services.shema import _audit
from app.services.shema._health_audience import require_reads_assessments
from app.services.shema._health_notice import entered_critical, notify_critical
from app.services.shema._scope import RegionScope, refuse_out_of_scope, visible_projects
from app.utils.shema_derivations import OverallHealth, overall_of
from app.utils.shema_health_questions import CURRENT_QUESTION_SET, DIMENSIONS

logger = logging.getLogger(__name__)

#: The record columns the projection writes, paired with the entry column each one mirrors.
#:
#: One tuple rather than seven assignments, so *the projection is the newest entry* is a list a
#: reader can check against the table instead of a sequence of lines they have to trust.
_PROJECTION: tuple[tuple[str, str], ...] = tuple(
    [(f"health_{dimension.value}", dimension.value) for dimension in DIMENSIONS]
    + [
        ("health_assessment_date", "assessment_date"),
        ("health_assessor", "assessor"),
        ("health_notes", "notes"),
    ]
)


#: The trail row every assessment writes, beside whatever record fields the submission moved.
#:
#: ``healthHistory`` is one of FE-44's own 73 keys, so the console looks it up where it looks up
#: its labels — the property ``_audit.py`` wants of every key it writes. The **values** are NULL,
#: as they are for a guarded field, and for a related reason rather than the same one: what
#: changed is a row in another table, and copying a team's ratings into the trail would put the
#: most sensitive thing this module stores in the store that is read by the most people and kept
#: the longest. The trail says *the health history gained an entry, by Maria, at 14:02*, which is
#: the sentence a 409 needs; the entry itself is read from the history, where the audience is
#: checked.
#:
#: The seven flat fields are **not** in the trail, and that is ``_audit.py``'s rule rather than an
#: omission: what it audits is what a client may write, and the projection is refused on the
#: record's own ``PATCH``. Its author is ``shema_health_assessments.created_by`` — a stronger
#: record than a trail row, because it sits on the thing that changed.
_HISTORY_GREW = _audit.FieldChange("healthHistory", None, None)


def _overall(carrier: ShemaProject | ShemaHealthAssessment) -> OverallHealth:
    """The worst of four, off either carrier — the record's flat fields or one entry's own.

    Two spellings of four dimensions and one rule to apply to both, which is why
    ``app/utils/shema_derivations.py`` grew :func:`~app.utils.shema_derivations.overall_of`: the
    record prefixes them ``health_`` and an assessment does not, and a second implementation of
    *the worst of four* is the one thing ``docs/shema.md`` says must not exist twice.
    """
    prefix = "health_" if isinstance(carrier, ShemaProject) else ""
    return overall_of(*(getattr(carrier, f"{prefix}{d.value}") for d in DIMENSIONS))


def _sort_key(entry: ShemaHealthAssessment) -> tuple[date, datetime]:
    """How the history is ordered — the day the reading happened, then the row's own moment.

    The same key ``app/services/shema/read_record.py`` orders the read by, written once here so
    that *the projection is the last entry the client sees* cannot become false by the two being
    sorted differently.
    """
    return (entry.assessment_date, entry.created_at)


def _carried_entry(project: ShemaProject, *, at: datetime) -> ShemaHealthAssessment | None:
    """The record's existing flat fields as a history row, or ``None`` if there is nothing to keep.

    ``None`` when no dimension is rated: a ``health_assessment_date`` with four empty dimensions
    is not a reading anybody took, and carrying it in would create the very row
    ``docs/shema.md`` §7.4 warns about — a team reported as heard when nobody rated it. The
    assessor and the note are carried only because a rating is what makes them an assessment.

    The date is the one the record holds; with none, the entry has no honest day of its own and
    the flat fields are treated as the assessment this submission is the first of.

    **The question set and the author are NULL and neither is invented.** These ratings answered a
    Notion column rather than a questionnaire, so stamping a version would manufacture provenance;
    and nobody knows who filed them, so ``created_by_name`` is ``""`` — which is the same honest
    empty ``shema_projects.updated_by_name`` takes for a record whose saver is unknown.
    """
    if project.health_assessment_date is None:
        return None
    if _overall(project) is OverallHealth.NA:
        return None
    return ShemaHealthAssessment(
        project_id=project.id,
        assessment_date=project.health_assessment_date,
        assessor=project.health_assessor,
        emotional=project.health_emotional,
        relational=project.health_relational,
        spiritual=project.health_spiritual,
        physical=project.health_physical,
        notes=project.health_notes,
        question_set_version=None,
        created_by=None,
        created_by_name="",
        created_at=at,
    )


async def _has_history(db: AsyncSession, project_id: str) -> bool:
    """Whether anything has ever been appended — which is what makes the carry happen once.

    Asked before the new rows are staged, and ``LIMIT 1`` because the answer is a yes or a no: a
    count over a project's whole history to decide one branch is a read that grows with the data
    for no reason.
    """
    stmt = (
        select(ShemaHealthAssessment.id)
        .where(ShemaHealthAssessment.project_id == project_id)
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none() is not None


def _project_onto(project: ShemaProject, entry: ShemaHealthAssessment) -> None:
    """Write one entry onto the record's seven flat fields, and nothing else."""
    for column, source in _PROJECTION:
        setattr(project, column, getattr(entry, source))


async def append_assessment(
    db: AsyncSession,
    scope: RegionScope,
    project_id: str,
    payload: ShemaHealthAssessmentSubmission,
    *,
    user: User,
    app_key: str,
    day: date,
) -> ShemaProject:
    """File one assessment and answer the record it landed on — the module docstring's seven steps.

    ``scope`` is positional and has no default, for the reason every query in this module states:
    a keyword with a permissive default is how a scope stops being applied. ``day`` is the
    actor's own local day, which the router resolves from ``X-Shema-Local-Date``; it is what a
    submission with no date of its own is filed under, because *today* is a fact about where the
    mentor is and not about where the server runs.

    ``app_key`` is a parameter because the app key is named in ``app/api/shema/_deps.py`` and
    nowhere else in the module, and a service that reached for it would be the second place to be
    wrong about it.

    **One moment for the whole write, and the carried entry a microsecond ahead of the new one.**
    Both rows land under one commit, so the transaction's clock would give them the same value and
    the history would come back in an order nobody chose — which would make *the projection is the
    last entry the client sees* false on the one case that needs it to be true. The carried entry
    **is** the older reading and has to read as one even when it shares a day with the new, so the
    offset is stated rather than left to a clock's resolution.
    """
    project = (
        await db.execute(visible_projects(scope).where(ShemaProject.id == project_id))
    ).scalar_one_or_none()
    if project is None:
        raise refuse_out_of_scope(
            scope, user=user, operation="append_assessment", project_id=project_id
        )

    await require_reads_assessments(db, user, app_key)

    before = _overall(project)
    snapshot = _audit.snapshot(project)

    at = datetime.now(UTC)

    entries: list[ShemaHealthAssessment] = []
    if not await _has_history(db, project.id):
        carried = _carried_entry(project, at=at)
        if carried is not None:
            entries.append(carried)

    assessed = ShemaHealthAssessment(
        project_id=project.id,
        assessment_date=payload.date or day,
        assessor=(payload.assessor or "").strip() or _audit.author_name(user),
        emotional=payload.emotional,
        relational=payload.relational,
        spiritual=payload.spiritual,
        physical=payload.physical,
        dimension_notes=payload.dimension_notes or None,
        notes=payload.running_note(),
        question_set_version=payload.question_set_version or CURRENT_QUESTION_SET.version,
        created_by=user.id,
        created_by_name=_audit.author_name(user),
        created_at=at + timedelta(microseconds=1),
    )
    entries.append(assessed)
    db.add_all(entries)

    newest = max(entries, key=_sort_key)
    if (
        project.health_assessment_date is None
        or _sort_key(newest)[0] >= project.health_assessment_date
    ):
        _project_onto(project, newest)

    for column in RECORD_FIELDS:
        if column in payload.model_fields_set:
            setattr(project, column, getattr(payload, column))

    version = await _bump_version(db, project)
    project.version = version
    project.updated_by = user.id
    project.updated_by_name = _audit.author_name(user)

    _audit.record_edits(
        db,
        project,
        version=version,
        changes=[*_audit.field_changes(snapshot, project), _HISTORY_GREW],
        user=user,
    )

    after = _overall(project)
    if entered_critical(before, after):
        await notify_critical(
            db,
            app_key=app_key,
            project_id=project.id,
            language_name=project.language_name,
            region=project.region_key,
            day=project.health_assessment_date or day,
            actor=user,
        )

    await db.commit()
    await db.refresh(project)
    return project


async def _bump_version(db: AsyncSession, project: ShemaProject) -> int:
    """Move the record's version on, unconditionally — the one thing here that is not a guard.

    ``save_project.py`` is the module's only *conditional* version bump and stays so: there the
    ``UPDATE ... WHERE version = expected`` is the race guard for a client that quoted a version.
    An assessment quotes none (see the module docstring), so there is nothing to race against and
    nothing to refuse — what the bump is for is telling the record screen that the flat fields
    moved underneath it.

    ``synchronize_session=False`` because the ORM's copy is set by hand a line later, which is
    cheaper than asking SQLAlchemy to re-read a row it is about to write.
    """
    current = project.version
    stmt = (
        update(ShemaProject)
        .where(ShemaProject.id == project.id)
        .values(version=ShemaProject.version + 1)
        .execution_options(synchronize_session=False)
    )
    await db.execute(stmt)
    return current + 1
