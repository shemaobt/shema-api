"""The retroactive backfill (ENG-373).

The precedent this copies, `20260518_0002_backfill_ph_bootstrap_admin.py`, exists because
an earlier migration silently no-op'd when a precondition was missing and nobody noticed.
So these tests assert what an operator would actually see in the upgrade log: rows
flagged, a count reported, and a second run that honestly reports having changed nothing.

The suite never runs Alembic — it builds its schema from `Base.metadata` — so the
migration's callable is imported from the revision file by path and driven against the
test connection, the same way Alembic drives it against a real one.

Every row here is seeded with `make_oc_recording`'s default `recompute_flags=False`: real
metadata, empty flags, nothing has recomputed it. That is the row this backfill exists for,
so seeding one that already carries flags would leave it with nothing to find.
"""

import importlib.util
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ReviewFlagCode
from app.db.models.oc_recording import OC_Recording
from app.services.oral_collector.review_flags import UNCLASSIFIED_GENRE_ID
from tests.baker import (
    make_language,
    make_oc_recording,
    make_oc_storyteller,
    make_oc_taxonomy_with_sentinel,
    make_project,
    make_user,
)

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


async def test_the_backfill_flags_rows_that_were_never_reviewed(
    db_session: AsyncSession,
) -> None:
    await make_oc_taxonomy_with_sentinel(db_session)
    user = await make_user(db_session)
    lang = await make_language(db_session)
    project = await make_project(db_session, lang.id)
    recording = await make_oc_recording(
        db_session,
        project.id,
        UNCLASSIFIED_GENRE_ID,
        UNCLASSIFIED_GENRE_ID,
        user_id=user.id,
        description=INSUFFICIENT,
        title="legacy recording",
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
    genre, sub = await make_oc_taxonomy_with_sentinel(db_session)
    user = await make_user(db_session)
    lang = await make_language(db_session)
    project = await make_project(db_session, lang.id)
    storyteller = await make_oc_storyteller(db_session, project.id, created_by_user_id=user.id)

    for index in range(3):
        await make_oc_recording(
            db_session,
            project.id,
            UNCLASSIFIED_GENRE_ID,
            UNCLASSIFIED_GENRE_ID,
            user_id=user.id,
            description=INSUFFICIENT,
            title=f"legacy {index}",
        )
    for index in range(2):
        await make_oc_recording(
            db_session,
            project.id,
            genre.id,
            sub.id,
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
    await make_oc_taxonomy_with_sentinel(db_session)
    user = await make_user(db_session)
    lang = await make_language(db_session)
    project = await make_project(db_session, lang.id)
    recording = await make_oc_recording(
        db_session,
        project.id,
        UNCLASSIFIED_GENRE_ID,
        UNCLASSIFIED_GENRE_ID,
        user_id=user.id,
        description=INSUFFICIENT,
        title="legacy recording",
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
    await make_oc_taxonomy_with_sentinel(db_session)
    user = await make_user(db_session)
    lang = await make_language(db_session)
    project = await make_project(db_session, lang.id)
    recording = await make_oc_recording(
        db_session,
        project.id,
        UNCLASSIFIED_GENRE_ID,
        UNCLASSIFIED_GENRE_ID,
        user_id=user.id,
        description=INSUFFICIENT,
        title="legacy recording",
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
    row_count = 7
    await make_oc_taxonomy_with_sentinel(db_session)
    user = await make_user(db_session)
    lang = await make_language(db_session)
    project = await make_project(db_session, lang.id)
    for index in range(row_count):
        await make_oc_recording(
            db_session,
            project.id,
            UNCLASSIFIED_GENRE_ID,
            UNCLASSIFIED_GENRE_ID,
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
