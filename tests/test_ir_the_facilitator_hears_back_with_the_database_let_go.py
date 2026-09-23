"""What the facilitator plays back is signed or fetched with the database let go.

The same shape ENG-1035/ENG-1049 fixed on the team's side: these two routes read the
facilitator's scope on the request's own session and then call GCS with that read's
transaction still open. The fake standing in for GCS reads `in_transaction()` on that
session when it is called.
"""

from __future__ import annotations

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ProjectRole
from app.db.models.internalization_room import IRTake, IRTakeKind
from tests.baker import (
    grant_facilitator_app_role,
    make_language,
    make_project,
    make_project_user_access,
    make_user,
)

IR = "/api/internalization-room"


@pytest.fixture()
async def client(db_session: AsyncSession):
    from fastapi import FastAPI

    from app.api.internalization_room import router
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    test_app = FastAPI()
    test_app.include_router(router, prefix=IR)
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def a_facilitator(db: AsyncSession, *, email: str = "fac@example.com"):
    user = await make_user(db, email=email)
    language = await make_language(db, name=f"Lang {email}", code=email[:3])
    project = await make_project(db, language.id, name=f"Team {email}")
    await make_project_user_access(db, project.id, user.id, role=ProjectRole.FACILITATOR)
    await grant_facilitator_app_role(db, user.id)

    from app.services.auth.issue_tokens import issue_tokens

    access, _refresh = await issue_tokens(db, user)
    return project, {"Authorization": f"Bearer {access}"}


async def a_recorded_take(db: AsyncSession, project_id: str, *, tag: str) -> IRTake:
    from app.db.models.internalization_room import IRSession

    session = IRSession(id=f"sessao-{tag}", pericope="P03", project_id=project_id)
    db.add(session)
    await db.flush()
    take = IRTake(
        id=f"take-{tag}",
        session_id=session.id,
        device_id=f"tablet-{tag}",
        project_id=project_id,
        pericope="P03",
        kind=IRTakeKind.ENSAIO,
        scope="passagem-inteira",
        storage_key=f"internalization-room/takes/{tag}.m4a",
        size_bytes=1024,
        sha256="0" * 64,
        crc32c="AAAAAA==",
        content_type="audio/mp4",
    )
    db.add(take)
    await db.commit()
    return take


async def test_a_take_the_facilitator_plays_back_is_signed_with_the_database_let_go(
    client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.config import get_settings
    from app.services.internalization_room import takes as takes_service

    project, headers = await a_facilitator(db_session)
    take = await a_recorded_take(db_session, project.id, tag="minha")
    held: dict[str, bool] = {}

    async def signs(bucket: str, key: str, **_: object) -> str:
        held["sign"] = db_session.in_transaction()
        return f"https://armazenamento.exemplo/{bucket}/{key}?assinado"

    monkeypatch.setattr(get_settings(), "gcs_platform_bucket", "balde-de-teste", raising=False)
    monkeypatch.setattr(takes_service, "generate_signed_download_url", signs)

    played = await client.get(
        f"{IR}/facilitator/takes/{take.id}/audio", headers=headers, follow_redirects=False
    )

    assert played.status_code == 307, played.text
    assert held == {"sign": False}, (
        "a leitura do take pela facilitadora ficava aberta enquanto o endereço era assinado"
    )
