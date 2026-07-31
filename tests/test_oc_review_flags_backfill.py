"""The retroactive backfill (ENG-373).

The precedent this copies, `20260518_0002_backfill_ph_bootstrap_admin.py`, exists because
an earlier migration silently no-op'd when a precondition was missing and nobody noticed.
So these tests assert what an operator would actually see in the upgrade log: rows
flagged, a count reported, and a second run that honestly reports having changed nothing.

The suite never runs Alembic — it builds its schema from `Base.metadata` — so the
migration's callable is imported from the revision file by path and driven against the
test connection, the same way Alembic drives it against a real one.
"""

import importlib.util
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ReviewFlagCode, UploadStatus
from app.db.models.oc_genre import OC_Genre, OC_Subcategory
from app.db.models.oc_recording import OC_Recording
from tests.baker import make_language, make_project, make_user

UNCLASSIFIED = "unclassified"
SUFFICIENT = "a description long enough to satisfy the rule"
INSUFFICIENT = "too short"

_REVISION = (
    Path(__file__).resolve().parents[1]
    / "alembic"
    / "versions"
    / "20260731_0001_add_review_flags_to_oc_recordings.py"
)


def _load_backfill():
    spec = importlib.util.spec_from_file_location("_eng373_backfill", _REVISION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.backfill_review_flags


async def _run_backfill(db: AsyncSession, *, batch_size: int | None = None):
    backfill = _load_backfill()
    connection = await db.connection()
    if batch_size is None:
        return await connection.run_sync(backfill)
    return await connection.run_sync(lambda sync_conn: backfill(sync_conn, batch_size=batch_size))


async def _seed_taxonomy(db: AsyncSession) -> tuple[OC_Genre, OC_Subcategory]:
    sentinel_genre = OC_Genre(id=UNCLASSIFIED, name="Unclassified", sort_order=9999)
    genre = OC_Genre(name="narrative", sort_order=0)
    db.add_all([sentinel_genre, genre])
    await db.flush()

    sentinel_sub = OC_Subcategory(
        id=UNCLASSIFIED, genre_id=UNCLASSIFIED, name="Unclassified", sort_order=9999
    )
    sub = OC_Subcategory(genre_id=genre.id, name="folktale", sort_order=0)
    db.add_all([sentinel_sub, sub])
    await db.commit()
    await db.refresh(genre)
    await db.refresh(sub)
    return genre, sub


async def _seed_unflagged_recording(
    db: AsyncSession,
    *,
    project_id: str,
    genre_id: str,
    subcategory_id: str,
    user_id: str,
    register_id: str | None = None,
    storyteller_id: str | None = None,
    description: str | None = None,
    title: str = "legacy recording",
) -> OC_Recording:
    """A row as it exists today: real metadata, empty flags, nothing has recomputed it."""
    recording = OC_Recording(
        project_id=project_id,
        genre_id=genre_id,
        subcategory_id=subcategory_id,
        register_id=register_id,
        storyteller_id=storyteller_id,
        user_id=user_id,
        title=title,
        description=description,
        duration_seconds=10.0,
        file_size_bytes=1024,
        format="m4a",
        upload_status=UploadStatus.VERIFIED,
        recorded_at=datetime.now(UTC),
    )
    db.add(recording)
    await db.commit()
    await db.refresh(recording)
    return recording


async def test_the_backfill_flags_rows_that_were_never_reviewed(
    db_session: AsyncSession,
) -> None:
    await _seed_taxonomy(db_session)
    user = await make_user(db_session)
    lang = await make_language(db_session)
    project = await make_project(db_session, lang.id)
    recording = await _seed_unflagged_recording(
        db_session,
        project_id=project.id,
        genre_id=UNCLASSIFIED,
        subcategory_id=UNCLASSIFIED,
        user_id=user.id,
        description=INSUFFICIENT,
    )
    assert recording.review_flags == []

    await _run_backfill(db_session)

    await db_session.refresh(recording)
    assert {flag["code"] for flag in recording.review_flags} == {
        ReviewFlagCode.MISSING_CLASSIFICATION,
        ReviewFlagCode.INSUFFICIENT_DESCRIPTION,
        ReviewFlagCode.MISSING_STORYTELLER,
    }


async def test_the_backfill_counts_only_the_rows_it_actually_rewrote(
    db_session: AsyncSession,
) -> None:
    """Marking zero rows in silence is a failure, not a success — and so is inflating it.

    The table holds three rows needing flags and two that are already right, so a report
    that simply echoes the row count is wrong in a way a same-shaped fixture would hide.
    """
    genre, sub = await _seed_taxonomy(db_session)
    user = await make_user(db_session)
    lang = await make_language(db_session)
    project = await make_project(db_session, lang.id)
    from app.db.models.oc_storyteller import OC_Storyteller

    storyteller = OC_Storyteller(
        project_id=project.id, name="Ana", sex="female", created_by_user_id=user.id
    )
    db_session.add(storyteller)
    await db_session.commit()

    for index in range(3):
        await _seed_unflagged_recording(
            db_session,
            project_id=project.id,
            genre_id=UNCLASSIFIED,
            subcategory_id=UNCLASSIFIED,
            user_id=user.id,
            description=INSUFFICIENT,
            title=f"legacy {index}",
        )
    for index in range(2):
        await _seed_unflagged_recording(
            db_session,
            project_id=project.id,
            genre_id=genre.id,
            subcategory_id=sub.id,
            user_id=user.id,
            register_id="formal",
            storyteller_id=storyteller.id,
            description=SUFFICIENT,
            title=f"already fine {index}",
        )

    report = await _run_backfill(db_session)

    assert report.scanned == 5
    assert report.changed == 3


async def test_running_the_backfill_twice_changes_nothing_the_second_time(
    db_session: AsyncSession,
) -> None:
    await _seed_taxonomy(db_session)
    user = await make_user(db_session)
    lang = await make_language(db_session)
    project = await make_project(db_session, lang.id)
    recording = await _seed_unflagged_recording(
        db_session,
        project_id=project.id,
        genre_id=UNCLASSIFIED,
        subcategory_id=UNCLASSIFIED,
        user_id=user.id,
        description=INSUFFICIENT,
    )

    first = await _run_backfill(db_session)
    await db_session.refresh(recording)
    flags_after_first = recording.review_flags

    second = await _run_backfill(db_session)
    await db_session.refresh(recording)

    assert first.changed == 1
    assert second.scanned == 1
    assert second.changed == 0
    assert recording.review_flags == flags_after_first


async def test_the_backfill_corrects_flags_that_are_stale_rather_than_absent(
    db_session: AsyncSession,
) -> None:
    """The empty-to-populated direction is the easy one.

    A row that already carries flags, but the wrong ones, has to end up with the right
    ones — an implementation that only fills in rows it finds empty would leave it lying.
    """
    await _seed_taxonomy(db_session)
    user = await make_user(db_session)
    lang = await make_language(db_session)
    project = await make_project(db_session, lang.id)
    recording = await _seed_unflagged_recording(
        db_session,
        project_id=project.id,
        genre_id=UNCLASSIFIED,
        subcategory_id=UNCLASSIFIED,
        user_id=user.id,
        description=INSUFFICIENT,
    )
    recording.review_flags = [{"code": ReviewFlagCode.MISSING_STORYTELLER, "origin": "system"}]
    await db_session.commit()

    report = await _run_backfill(db_session)

    await db_session.refresh(recording)
    assert report.changed == 1
    assert {flag["code"] for flag in recording.review_flags} == {
        ReviewFlagCode.MISSING_CLASSIFICATION,
        ReviewFlagCode.INSUFFICIENT_DESCRIPTION,
        ReviewFlagCode.MISSING_STORYTELLER,
    }


async def test_the_backfill_crosses_more_rows_than_fit_in_one_batch(
    db_session: AsyncSession,
) -> None:
    """Keyset pagination that mishandles its cursor stops after the first page.

    Driven with a deliberately tiny batch so seven rows span four of them; at the
    production batch size no test could seed enough rows to notice.
    """
    row_count = 7
    await _seed_taxonomy(db_session)
    user = await make_user(db_session)
    lang = await make_language(db_session)
    project = await make_project(db_session, lang.id)
    for index in range(row_count):
        await _seed_unflagged_recording(
            db_session,
            project_id=project.id,
            genre_id=UNCLASSIFIED,
            subcategory_id=UNCLASSIFIED,
            user_id=user.id,
            description=INSUFFICIENT,
            title=f"legacy {index}",
        )

    report = await _run_backfill(db_session, batch_size=2)

    assert report.scanned == row_count
    assert report.changed == row_count
    # Read every row back: a loop that counts all seven but only writes the first page
    # reports exactly the same numbers as a correct one.
    result = await db_session.execute(select(OC_Recording))
    assert all(recording.review_flags for recording in result.scalars().all())
