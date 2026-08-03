"""Review flags as the Flutter client actually receives them (ENG-373).

Asserting that `RecordingResponse` declares a field would be a test of a data structure.
What matters is that a real HTTP response body carries the flags — a field that exists on
the schema but never reaches the wire is exactly the bug this guards.
"""

from datetime import UTC, datetime

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ReviewFlagCode, ReviewFlagOrigin, UploadStatus
from app.db.models.oc_genre import OC_Genre, OC_Subcategory
from app.db.models.oc_recording import OC_Recording
from app.db.models.oc_storyteller import OC_Storyteller
from app.services.oral_collector.review_flags import recompute_review_flags
from tests.baker import make_language, make_project, make_user

RECORDINGS_PREFIX = "/api/oral-collector/recordings"
UNCLASSIFIED = "unclassified"
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


async def _seed_recording(
    db: AsyncSession,
    *,
    project_id: str,
    genre_id: str,
    subcategory_id: str,
    user_id: str,
    register_id: str | None = None,
    storyteller_id: str | None = None,
    description: str | None = None,
    title: str = "test recording",
) -> OC_Recording:
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
    recompute_review_flags(recording)
    db.add(recording)
    await db.commit()
    await db.refresh(recording)
    return recording


async def test_fetching_one_recording_returns_its_review_flags(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    await _seed_taxonomy(db_session)
    user = await make_user(db_session)
    lang = await make_language(db_session)
    project = await make_project(db_session, lang.id)
    recording = await _seed_recording(
        db_session,
        project_id=project.id,
        genre_id=UNCLASSIFIED,
        subcategory_id=UNCLASSIFIED,
        user_id=user.id,
        description=SUFFICIENT,
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
    genre, sub = await _seed_taxonomy(db_session)
    user = await make_user(db_session)
    lang = await make_language(db_session)
    project = await make_project(db_session, lang.id)
    storyteller = OC_Storyteller(
        project_id=project.id, name="Ana", sex="female", created_by_user_id=user.id
    )
    db_session.add(storyteller)
    await db_session.commit()

    incomplete = await _seed_recording(
        db_session,
        project_id=project.id,
        genre_id=UNCLASSIFIED,
        subcategory_id=UNCLASSIFIED,
        user_id=user.id,
        description=SUFFICIENT,
        title="incomplete",
    )
    complete = await _seed_recording(
        db_session,
        project_id=project.id,
        genre_id=genre.id,
        subcategory_id=sub.id,
        user_id=user.id,
        register_id="formal",
        storyteller_id=storyteller.id,
        description=SUFFICIENT,
        title="complete",
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
    await _seed_taxonomy(db_session)
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
    await _seed_taxonomy(db_session)
    user = await make_user(db_session)
    lang = await make_language(db_session)
    project = await make_project(db_session, lang.id)
    recording = await _seed_recording(
        db_session,
        project_id=project.id,
        genre_id=UNCLASSIFIED,
        subcategory_id=UNCLASSIFIED,
        user_id=user.id,
        description=SUFFICIENT,
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
