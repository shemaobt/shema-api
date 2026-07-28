from __future__ import annotations

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import select

from app.db.models.as_language_member import AsLanguageMember
from app.db.models.as_speaker import AsSpeaker
from app.db.models.as_tier_a import AsTierARecording, AsTierAWord
from app.db.models.as_tier_b import AsTierBPair, AsTierBRecording
from app.db.models.as_tier_c import AsTierCClip, AsTierCSortAssignment
from app.db.models.auth import Role
from tests.baker import make_app, make_role, make_user_app_role


@pytest.fixture()
async def as_app(db_session):
    """The annotation-studio app registry row plus its admin/facilitator roles."""
    app = await make_app(db_session, app_key="annotation-studio", name="Annotation Studio")
    await make_role(db_session, app.id, role_key="admin", label="Admin", is_system=True)
    await make_role(db_session, app.id, role_key="facilitator", label="Facilitator", is_system=True)
    return app


@pytest.fixture()
async def client(db_session):
    """An ASGI client whose handlers run against the test session.

    Mounts only the annotation-studio router (with the real exception handlers, so
    AuthorizationError → 403) to avoid the full app's lifespan/inngest startup.
    Exercises the real dependency chain (auth → require_app_access → per-route
    assert_language_access) that the service-level tests bypass.
    """
    from fastapi import FastAPI

    from app.api.annotation_studio import router as as_router
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    test_app = FastAPI()
    test_app.include_router(as_router, prefix="/api/annotation-studio")
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def auth_header(db_session, user) -> dict[str, str]:
    """A real bearer token for ``user`` (decoded by the auth dependency)."""
    from app.services.auth.issue_tokens import issue_tokens

    access, _refresh = await issue_tokens(db_session, user)
    return {"Authorization": f"Bearer {access}"}


async def grant_role(db_session, app_id: str, user_id: str, role_key: str) -> None:
    """Assign an existing seeded role (admin/facilitator) to a user."""
    role = (
        await db_session.execute(
            select(Role).where(Role.app_id == app_id, Role.role_key == role_key)
        )
    ).scalar_one()
    await make_user_app_role(db_session, user_id, app_id, role.id)


async def add_member(db_session, language_id: str, user_id: str) -> None:
    db_session.add(AsLanguageMember(language_id=language_id, user_id=user_id))
    await db_session.commit()


# ── as_* seed helpers (no baker entries exist for these yet) ──────────────────


async def make_word(db_session, language_id: str, label: str) -> AsTierAWord:
    word = AsTierAWord(language_id=language_id, label=label)
    db_session.add(word)
    await db_session.commit()
    await db_session.refresh(word)
    return word


async def make_speaker(db_session, language_id: str, label: str) -> AsSpeaker:
    speaker = AsSpeaker(language_id=language_id, label=label)
    db_session.add(speaker)
    await db_session.commit()
    await db_session.refresh(speaker)
    return speaker


async def add_tier_a_recording(
    db_session, word_id: str, speaker_id: str, rep_index: int, *, stored: bool, key: str
) -> AsTierARecording:
    rec = AsTierARecording(
        word_id=word_id,
        speaker_id=speaker_id,
        rep_index=rep_index,
        storage_key=key,
        export_filename=f"{key}.wav",
        upload_format="wav",
        upload_status="stored" if stored else "pending",
    )
    db_session.add(rec)
    await db_session.commit()
    return rec


async def make_pair(db_session, language_id: str, pair_number: int) -> AsTierBPair:
    pair = AsTierBPair(language_id=language_id, pair_number=pair_number)
    db_session.add(pair)
    await db_session.commit()
    await db_session.refresh(pair)
    return pair


async def add_tier_b_recording(
    db_session, pair_id: str, side: str, rep_index: int, *, stored: bool, key: str
) -> AsTierBRecording:
    rec = AsTierBRecording(
        pair_id=pair_id,
        side=side,
        rep_index=rep_index,
        storage_key=key,
        export_filename=f"{key}.wav",
        upload_format="wav",
        upload_status="stored" if stored else "pending",
    )
    db_session.add(rec)
    await db_session.commit()
    return rec


async def make_clip(
    db_session, language_id: str, clip_number: int, *, stored: bool, key: str
) -> AsTierCClip:
    clip = AsTierCClip(
        language_id=language_id,
        clip_number=clip_number,
        storage_key=key,
        export_clip_id=f"c{clip_number}",
        export_filename=f"{key}.wav",
        upload_format="wav",
        upload_status="stored" if stored else "pending",
    )
    db_session.add(clip)
    await db_session.commit()
    await db_session.refresh(clip)
    return clip


async def add_sort(
    db_session, clip_id: str, dimension: str, round_: str, group_label: str | None
) -> AsTierCSortAssignment:
    row = AsTierCSortAssignment(
        clip_id=clip_id, dimension=dimension, round=round_, group_label=group_label
    )
    db_session.add(row)
    await db_session.commit()
    return row
