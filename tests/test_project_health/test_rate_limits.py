from __future__ import annotations

import uuid

import httpx
import pytest
from httpx import ASGITransport

from app.core.database import get_db
from app.core.rate_limit import limiter
from app.main import create_app
from app.services.project_health.interview_token import encode_interview_token

CREATION_LIMIT = 10
MESSAGE_LIMIT = 60
REPORT_LIMIT = 60
CALLS = "/api/project-health"


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture()
async def client(db_session, ph_app, stub_llm):
    app = create_app()

    async def _get_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_db
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def _create(client, project: str, team: str) -> int:
    r = await client.post(
        f"{CALLS}/interviews",
        json={"project_name": project, "team_name": team, "language": "en"},
    )
    return r.status_code


async def _message(client, token: str, interview_id: str) -> int:
    r = await client.post(
        f"{CALLS}/interviews/{interview_id}/messages",
        json={"content": "hello"},
        headers={"Authorization": f"Bearer {token}"},
    )
    return r.status_code


def _interview() -> tuple[str, str]:
    interview_id = str(uuid.uuid4())
    token, _ = encode_interview_token(interview_id)
    return token, interview_id


async def test_creations_for_different_project_team_pairs_from_one_address_are_all_accepted(client):
    statuses = [await _create(client, f"P{i}", f"T{i}") for i in range(CREATION_LIMIT + 1)]

    assert statuses == [201] * (CREATION_LIMIT + 1)


async def test_the_eleventh_creation_for_one_project_team_pair_is_refused(client):
    statuses = [await _create(client, "P", "T") for _ in range(CREATION_LIMIT + 1)]

    assert statuses == [201] * CREATION_LIMIT + [429]


async def test_a_pair_over_its_limit_leaves_another_pair_accepted(client):
    for _ in range(CREATION_LIMIT + 1):
        await _create(client, "P", "T")

    assert await _create(client, "P", "Other") == 201


async def test_messages_under_different_interview_tokens_from_one_address_are_all_accepted(client):
    statuses = [await _message(client, *_interview()) for _ in range(MESSAGE_LIMIT + 1)]

    assert 429 not in statuses


async def test_the_message_past_the_limit_under_one_token_is_refused(client):
    token, interview_id = _interview()

    statuses = [await _message(client, token, interview_id) for _ in range(MESSAGE_LIMIT + 1)]

    assert statuses[-1] == 429
    assert 429 not in statuses[:-1]


async def test_team_reports_of_different_ids_from_one_address_are_all_accepted(client):
    statuses = [
        (await client.get(f"{CALLS}/reports/team/r{i}")).status_code
        for i in range(REPORT_LIMIT + 1)
    ]

    assert 429 not in statuses


async def test_the_team_report_past_the_limit_for_one_id_is_refused(client):
    statuses = [
        (await client.get(f"{CALLS}/reports/team/r1")).status_code for _ in range(REPORT_LIMIT + 1)
    ]

    assert statuses[-1] == 429
    assert 429 not in statuses[:-1]
