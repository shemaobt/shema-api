from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import select, text

from app.db.models.auth import Role
from app.db.models.oc_acousteme import OC_AcoustemeArtifact  # noqa: F401 (create_all)
from app.db.models.sound_necklace import (  # noqa: F401 (create_all)
    SnArtifact,
    SnAudioRef,
    SnConsent,
    SnProjectSettings,
    SnSession,
    SnSessionState,
    SnVoiceAnswer,
)
from tests.baker import (
    make_app,
    make_language,
    make_project,
    make_project_user_access,
    make_role,
    make_user,
    make_user_app_role,
)

APP_KEY = "sound-necklace"
SN = "/api/sound-necklace"


@pytest.fixture()
async def sound_necklace_app(db_session):
    """The sound-necklace app registry row plus its two seeded roles."""
    app = await make_app(db_session, app_key=APP_KEY, name="Sound Necklace")
    await make_role(db_session, app.id, role_key="facilitator", label="Facilitator", is_system=True)
    await make_role(
        db_session, app.id, role_key="project_admin", label="Project Admin", is_system=True
    )
    return app


@pytest.fixture()
async def client(db_session):
    """An ASGI client whose handlers run against the test session.

    Mounts only the sound-necklace router (with the real exception handlers, so
    AuthorizationError → 403) to avoid the full app's lifespan/inngest startup.
    Exercises the real dependency chain (auth → require_app_access) that gates
    every route in the module.
    """
    from fastapi import FastAPI

    from app.api.sound_necklace import router as sound_necklace_router
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    test_app = FastAPI()
    test_app.include_router(sound_necklace_router, prefix="/api/sound-necklace")
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
    """Assign an existing seeded role (facilitator/project_admin) to a user."""
    role = (
        await db_session.execute(
            select(Role).where(Role.app_id == app_id, Role.role_key == role_key)
        )
    ).scalar_one()
    await make_user_app_role(db_session, user_id, app_id, role.id)


async def make_facilitator(db_session, sound_necklace_app, project, email: str, name: str | None):
    """A sound-necklace facilitator who can reach ``project``, plus their bearer."""
    user = await make_user(db_session, email=email, display_name=name)
    await grant_role(db_session, sound_necklace_app.id, user.id, "facilitator")
    await make_project_user_access(db_session, project.id, user.id)
    return user, await auth_header(db_session, user)


def audio_of(project_id: str) -> str:
    """The audio id a project's fixture bucket holds.

    Derived from the project rather than fixed, because ``audio_id`` is a global primary
    key: any test that sets up two projects would collide on a shared literal, and the
    "another project is denied" cases all set up two.
    """
    return f"aud-{project_id}"


async def give_project_an_audio(db_session, project_id: str, audio_id: str | None = None) -> str:
    """Put an audio in a project's bucket, so a session can be opened on it.

    Every session names an audio, and since ENG-362 that name is a foreign key the
    service checks besides. A project with an empty bucket is a project no session can
    open — not the state these tests mean to set up, so this is fixture plumbing rather
    than something a test asserts on.
    """
    audio_id = audio_id or audio_of(project_id)
    db_session.add(SnAudioRef(audio_id=audio_id, project_id=project_id, consent_present=True))
    await db_session.commit()
    return audio_id


@pytest.fixture()
async def project(db_session):
    """A project with one audio in its bucket — the audio ``new_session`` cuts.

    The audio is part of the fixture because a session cannot name one the project does
    not have: ``audio_ref`` is a foreign key, and create_session checks it besides. A
    project without audios is a project no session can open, which is not the state any
    of these tests mean to set up.
    """
    language = await make_language(db_session, name="Nheengatu", code="yrl")
    project = await make_project(db_session, language.id, name="Projeto A")
    await give_project_an_audio(db_session, project.id)
    return project


@pytest.fixture()
async def alice(db_session, sound_necklace_app, project):
    return await make_facilitator(
        db_session, sound_necklace_app, project, "alice@example.com", "Alice"
    )


@pytest.fixture()
async def bob(db_session, sound_necklace_app, project):
    """A second editor on the same project — the other person, not the other tab."""
    return await make_facilitator(db_session, sound_necklace_app, project, "bob@example.com", "Bob")


async def new_session(client, headers, project_id: str) -> str:
    res = await client.post(
        f"{SN}/sessions",
        headers=headers,
        json={
            "audio_id": audio_of(project_id),
            "project_id": project_id,
            "story_name": "O Conto do Boto",
            "story_slug": "conto-do-boto",
            "granularity_level": "medium",
            "bead_sec": 0.5,
            "manifest_id": "fnv1a32:d31a8419",
            "pipeline_consent": True,
        },
    )
    assert res.status_code == 201, res.text
    return str(res.json()["id"])


async def set_lease_expiry(db_session, session_id: str, when: datetime) -> None:
    """Move a lease's expiry without waiting the TTL out.

    Writes behind the ORM's back. That is only safe while expiry is decided in SQL — if
    a guard ever reads ``session.lock_expires_at`` in Python it will see the identity
    map's stale copy and these tests will lie. Expiring the map instead is not the fix:
    the app runs on this very session, and the reload lands outside the greenlet.
    """
    await db_session.execute(
        text("UPDATE sn_sessions SET lock_expires_at = :when WHERE id = :sid"),
        {"when": when, "sid": session_id},
    )


async def expire_lease(db_session, session_id: str) -> None:
    """Age the lease past its TTL — the crashed-tab case."""
    await set_lease_expiry(db_session, session_id, datetime.now(UTC) - timedelta(seconds=1))


async def hand_lease_to(db_session, session_id: str, user_id: str) -> None:
    """Give the lease to somebody else, the way a takeover mid-request would.

    Writes behind the ORM's back for the same reason ``set_lease_expiry`` does: the app
    under test runs on this very session, so the alternative is a reload outside the
    greenlet. Use it where the turnover has to land *during* a request the test is
    already awaiting, which a second HTTP call cannot express.
    """
    await db_session.execute(
        text("UPDATE sn_sessions SET locked_by = :uid, lock_expires_at = :when WHERE id = :sid"),
        {"uid": user_id, "when": datetime.now(UTC) + timedelta(seconds=60), "sid": session_id},
    )
