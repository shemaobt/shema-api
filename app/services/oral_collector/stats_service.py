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


def _counted_conditions(project_id: str) -> list[ColumnElement[bool]]:
    """The recordings a project's stats describe: the ones its listing returns.

    A split leaves the parent behind as an `ARCHIVED_AFTER_SPLIT` row that keeps its
    `upload_status` and its full duration, sitting beside the segment rows that replaced it.
    Counting it reports audio the user cannot open, and reports the segments' audio a second
    time under the parent.

    Both aggregations below share this so they cannot drift apart from each other, or from
    `recording_service._listing_conditions`.
    """
    return [
        OC_Recording.project_id == project_id,
        OC_Recording.upload_status.in_(ACTIVE_UPLOAD_STATUSES),
        OC_Recording.splitting_status != SplittingStatus.ARCHIVED_AFTER_SPLIT,
    ]


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

    hours_stmt = select(func.coalesce(func.sum(OC_Recording.duration_seconds), 0.0))
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
