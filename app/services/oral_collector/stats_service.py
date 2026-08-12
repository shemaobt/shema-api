from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ACTIVE_UPLOAD_STATUSES, SplittingStatus
from app.db.models.oc_genre import OC_Genre, OC_Subcategory
from app.db.models.oc_recording import OC_Recording
from app.db.models.project import Project, ProjectUserAccess
from app.models.oc_stats import (
    AdminStatsResponse,
    GenreStatItem,
    GenreStatsResponse,
    SubcategoryStatItem,
)


def _counted_recording_conditions() -> list[ColumnElement[bool]]:
    """The recordings a number *about audio* describes, whatever it groups them by.

    A split leaves the parent behind as an `ARCHIVED_AFTER_SPLIT` row that keeps its
    `upload_status` and its full duration, sitting beside the segment rows that replaced it.
    Counting it reports audio the user cannot open, and reports the segments' audio a second
    time under the parent. An upload the server never received is duration that exists only on
    a device, which the platform cannot play and should not claim to hold.

    Every count and duration below shares this so they cannot drift apart from each other, or
    from `recording_service._listing_conditions`. The platform totals that are not about audio
    do not share it — see `get_admin_stats`.
    """
    return [
        OC_Recording.upload_status.in_(ACTIVE_UPLOAD_STATUSES),
        OC_Recording.splitting_status != SplittingStatus.ARCHIVED_AFTER_SPLIT,
    ]


def _counted_conditions(project_id: str) -> list[ColumnElement[bool]]:
    """`_counted_recording_conditions`, narrowed to one project."""
    return [OC_Recording.project_id == project_id, *_counted_recording_conditions()]


async def get_genre_stats(db: AsyncSession, project_id: str) -> GenreStatsResponse:

    genre_stmt = (
        select(
            OC_Recording.genre_id,
            OC_Genre.name.label("genre_name"),
            func.count(OC_Recording.id).label("recording_count"),
            func.coalesce(func.sum(OC_Recording.duration_seconds), 0.0).label("duration_seconds"),
        )
        .join(OC_Genre, OC_Genre.id == OC_Recording.genre_id)
        .where(*_counted_conditions(project_id))
        .group_by(OC_Recording.genre_id, OC_Genre.name)
        .order_by(OC_Genre.name)
    )
    genre_result = await db.execute(genre_stmt)
    genres = [
        GenreStatItem(
            genre_id=row.genre_id,
            genre_name=row.genre_name,
            recording_count=row.recording_count,
            duration_seconds=float(row.duration_seconds),
        )
        for row in genre_result.all()
    ]

    sub_stmt = (
        select(
            OC_Recording.subcategory_id,
            OC_Subcategory.name.label("subcategory_name"),
            OC_Recording.genre_id,
            func.count(OC_Recording.id).label("recording_count"),
            func.coalesce(func.sum(OC_Recording.duration_seconds), 0.0).label("duration_seconds"),
        )
        .join(OC_Subcategory, OC_Subcategory.id == OC_Recording.subcategory_id)
        .where(*_counted_conditions(project_id))
        .group_by(
            OC_Recording.subcategory_id,
            OC_Subcategory.name,
            OC_Recording.genre_id,
        )
        .order_by(OC_Subcategory.name)
    )
    sub_result = await db.execute(sub_stmt)
    subcategories = [
        SubcategoryStatItem(
            subcategory_id=row.subcategory_id,
            subcategory_name=row.subcategory_name,
            genre_id=row.genre_id,
            recording_count=row.recording_count,
            duration_seconds=float(row.duration_seconds),
        )
        for row in sub_result.all()
    ]

    return GenreStatsResponse(
        project_id=project_id,
        genres=genres,
        subcategories=subcategories,
    )


async def get_admin_stats(db: AsyncSession) -> AdminStatsResponse:
    """Platform-wide totals for the admin panel: projects, languages, hours and active users.

    Only `total_hours` is filtered, and the asymmetry is deliberate — do not harmonise it.
    Hours are a quantity of audio, so hours the server never received, or a split parent's
    hours already counted under the segments that replaced it, are hours the platform cannot
    play and must not claim to hold; sharing `_counted_recording_conditions` with
    `get_genre_stats` is what keeps that number agreeing with every other screen.

    The other three answer questions that are not about recordings, and filtering them by
    upload status would make each one wrong in the same way: a project collecting since
    yesterday, with every upload still in flight, is a project, and counting it by its audio
    would report "0 projects" and "1 language" about that same project in one response.
    `total_languages` and `active_users` were never filtered for exactly this reason.
    """
    project_count_stmt = select(func.count(func.distinct(OC_Recording.project_id)))
    project_result = await db.execute(project_count_stmt)
    total_projects = project_result.scalar_one()

    language_count_stmt = (
        select(func.count(func.distinct(Project.language_id)))
        .select_from(Project)
        .join(ProjectUserAccess, ProjectUserAccess.project_id == Project.id)
    )
    language_result = await db.execute(language_count_stmt)
    total_languages = language_result.scalar_one()

    hours_stmt = select(func.coalesce(func.sum(OC_Recording.duration_seconds), 0.0)).where(
        *_counted_recording_conditions()
    )
    hours_result = await db.execute(hours_stmt)
    total_seconds = float(hours_result.scalar_one())
    total_hours = total_seconds / 3600.0

    users_stmt = select(func.count(func.distinct(ProjectUserAccess.user_id)))
    users_result = await db.execute(users_stmt)
    active_users = users_result.scalar_one()

    return AdminStatsResponse(
        total_projects=total_projects,
        total_languages=total_languages,
        total_hours=round(total_hours, 2),
        active_users=active_users,
    )
