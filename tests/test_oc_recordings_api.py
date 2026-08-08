"""The recordings router over real HTTP, as the Flutter client actually drives it.

Asserting that `RecordingResponse` declares a field would be a test of a data structure.
What matters is that a real HTTP response body carries the flags (ENG-373) — a field that
exists on the schema but never reaches the wire is exactly the bug this guards. The same
reasoning covers `clear-stale` (ENG-397): what it deletes is only observable end to end.
"""

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ReviewFlagCode, ReviewFlagOrigin, UploadStatus
from app.db.models.oc_recording import OC_Recording
from app.db.models.project import ProjectUserAccess
from app.services.oral_collector.review_flags import UNCLASSIFIED_GENRE_ID
from tests.baker import (
    make_language,
    make_oc_recording,
    make_oc_storyteller,
    make_oc_taxonomy_with_sentinel,
    make_project,
    make_project_user_access,
    make_user,
)

RECORDINGS_PREFIX = "/api/oral-collector/recordings"
SUFFICIENT = "a description long enough to satisfy the rule"


@pytest.fixture()
async def client(db_session: AsyncSession):
    """ASGI client mounting only the recordings router, running the real auth chain."""
    from fastapi import FastAPI

    from app.api.oral_collector.recordings import recordings_router
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    test_app = FastAPI()
    test_app.include_router(recordings_router, prefix=RECORDINGS_PREFIX)
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _auth_header(db_session: AsyncSession, user) -> dict[str, str]:
    from app.services.auth.issue_tokens import issue_tokens

    access, _refresh = await issue_tokens(db_session, user)
    return {"Authorization": f"Bearer {access}"}


async def test_fetching_one_recording_returns_its_review_flags(
    client: httpx.AsyncClient, db_session: AsyncSession
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
        description=SUFFICIENT,
        recompute_flags=True,
    )

    response = await client.get(
        f"{RECORDINGS_PREFIX}/{recording.id}", headers=await _auth_header(db_session, user)
    )

    assert response.status_code == 200
    flags = response.json()["review_flags"]
    assert {flag["code"] for flag in flags} == {
        ReviewFlagCode.MISSING_CLASSIFICATION,
        ReviewFlagCode.MISSING_STORYTELLER,
    }
    # Origin travels too: it is what lets a user-raised flag join the same list later
    # without the client having to tell the two apart by code.
    assert {flag["origin"] for flag in flags} == {ReviewFlagOrigin.SYSTEM}


async def test_listing_recordings_returns_each_ones_flags(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    genre, sub = await make_oc_taxonomy_with_sentinel(db_session)
    user = await make_user(db_session)
    lang = await make_language(db_session)
    project = await make_project(db_session, lang.id)
    storyteller = await make_oc_storyteller(db_session, project.id, created_by_user_id=user.id)

    incomplete = await make_oc_recording(
        db_session,
        project.id,
        UNCLASSIFIED_GENRE_ID,
        UNCLASSIFIED_GENRE_ID,
        user_id=user.id,
        description=SUFFICIENT,
        title="incomplete",
        recompute_flags=True,
    )
    complete = await make_oc_recording(
        db_session,
        project.id,
        genre.id,
        sub.id,
        user_id=user.id,
        register_id="formal",
        storyteller_id=storyteller.id,
        description=SUFFICIENT,
        title="complete",
        recompute_flags=True,
    )

    response = await client.get(
        RECORDINGS_PREFIX,
        params={"project_id": project.id},
        headers=await _auth_header(db_session, user),
    )

    assert response.status_code == 200
    by_id = {item["id"]: item["review_flags"] for item in response.json()}
    assert {flag["code"] for flag in by_id[incomplete.id]} == {
        ReviewFlagCode.MISSING_CLASSIFICATION,
        ReviewFlagCode.MISSING_STORYTELLER,
    }
    assert by_id[complete.id] == []


async def test_an_unknown_review_flag_is_refused(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    await make_oc_taxonomy_with_sentinel(db_session)
    user = await make_user(db_session)
    lang = await make_language(db_session)
    project = await make_project(db_session, lang.id)

    response = await client.get(
        RECORDINGS_PREFIX,
        params={"project_id": project.id, "review_flag": "missing_storytellers"},
        headers=await _auth_header(db_session, user),
    )

    assert response.status_code == 422


async def test_a_known_review_flag_is_accepted(
    client: httpx.AsyncClient, db_session: AsyncSession
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
        description=SUFFICIENT,
        recompute_flags=True,
    )

    response = await client.get(
        RECORDINGS_PREFIX,
        params={
            "project_id": project.id,
            "review_flag": ReviewFlagCode.MISSING_STORYTELLER,
        },
        headers=await _auth_header(db_session, user),
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [recording.id]


async def _make_manager(db: AsyncSession, project_id: str, user_id: str) -> ProjectUserAccess:
    """`make_project_user_access` always writes role="member"; the gate wants "manager"."""
    access = ProjectUserAccess(project_id=project_id, user_id=user_id, role="manager")
    db.add(access)
    await db.commit()
    return access


async def _surviving_ids(db: AsyncSession) -> set[str]:
    """Ids straight from the table.

    A column-only select bypasses the identity map, so a row the endpoint kept in memory
    but deleted from the database cannot be mistaken for a survivor.
    """
    result = await db.execute(select(OC_Recording.id))
    return set(result.scalars().all())


async def test_clear_stale_deletes_failed_uploads_but_spares_an_upload_in_flight(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    genre, subcategory = await make_oc_taxonomy_with_sentinel(db_session)
    user = await make_user(db_session)
    lang = await make_language(db_session)
    project = await make_project(db_session, lang.id)
    await _make_manager(db_session, project.id, user.id)
    in_flight = await make_oc_recording(
        db_session,
        project.id,
        genre.id,
        subcategory.id,
        title="still uploading",
        upload_status=UploadStatus.UPLOADING,
    )
    failed = await make_oc_recording(
        db_session,
        project.id,
        genre.id,
        subcategory.id,
        title="upload failed",
        upload_status=UploadStatus.UPLOAD_FAILED,
    )

    response = await client.post(
        f"{RECORDINGS_PREFIX}/clear-stale",
        params={"project_id": project.id},
        headers=await _auth_header(db_session, user),
    )

    assert response.status_code == 200
    assert response.json() == {"deleted": 1}
    survivors = await _surviving_ids(db_session)
    assert in_flight.id in survivors
    assert failed.id not in survivors


async def test_clear_stale_leaves_another_projects_failed_upload_alone(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    genre, subcategory = await make_oc_taxonomy_with_sentinel(db_session)
    user = await make_user(db_session)
    lang = await make_language(db_session)
    project = await make_project(db_session, lang.id, name="Target Project")
    other_project = await make_project(db_session, lang.id, name="Other Project")
    await _make_manager(db_session, project.id, user.id)
    await _make_manager(db_session, other_project.id, user.id)
    failed = await make_oc_recording(
        db_session,
        project.id,
        genre.id,
        subcategory.id,
        title="upload failed",
        upload_status=UploadStatus.UPLOAD_FAILED,
    )
    other_failed = await make_oc_recording(
        db_session,
        other_project.id,
        genre.id,
        subcategory.id,
        title="upload failed elsewhere",
        upload_status=UploadStatus.UPLOAD_FAILED,
    )

    response = await client.post(
        f"{RECORDINGS_PREFIX}/clear-stale",
        params={"project_id": project.id},
        headers=await _auth_header(db_session, user),
    )

    assert response.status_code == 200
    assert response.json() == {"deleted": 1}
    survivors = await _surviving_ids(db_session)
    assert other_failed.id in survivors
    assert failed.id not in survivors


async def test_clear_stale_is_refused_to_a_plain_member_and_deletes_nothing(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    genre, subcategory = await make_oc_taxonomy_with_sentinel(db_session)
    user = await make_user(db_session)
    lang = await make_language(db_session)
    project = await make_project(db_session, lang.id)
    await make_project_user_access(db_session, project.id, user.id)
    failed = await make_oc_recording(
        db_session,
        project.id,
        genre.id,
        subcategory.id,
        title="upload failed",
        upload_status=UploadStatus.UPLOAD_FAILED,
    )

    response = await client.post(
        f"{RECORDINGS_PREFIX}/clear-stale",
        params={"project_id": project.id},
        headers=await _auth_header(db_session, user),
    )

    assert response.status_code == 403
    assert failed.id in await _surviving_ids(db_session)
