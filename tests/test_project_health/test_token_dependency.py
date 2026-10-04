from __future__ import annotations

import pytest

from app.api.project_health._deps import require_interview_token
from app.core.exceptions import AuthenticationError, AuthorizationError
from app.services.project_health.interview_token import encode_interview_token


async def test_require_interview_token_accepts_matching_id():
    token, _ = encode_interview_token("11111111-1111-1111-1111-111111111111")
    claims = await require_interview_token(
        "11111111-1111-1111-1111-111111111111",
        authorization=f"Bearer {token}",
    )
    assert claims.interview_id == "11111111-1111-1111-1111-111111111111"


async def test_require_interview_token_rejects_missing_header():
    with pytest.raises(AuthenticationError):
        await require_interview_token("anything", authorization=None)


async def test_require_interview_token_rejects_wrong_scheme():
    with pytest.raises(AuthenticationError):
        await require_interview_token("anything", authorization="Basic foo")


async def test_require_interview_token_rejects_mismatched_interview():
    token, _ = encode_interview_token("11111111-1111-1111-1111-111111111111")
    with pytest.raises(AuthorizationError):
        await require_interview_token(
            "22222222-2222-2222-2222-222222222222",
            authorization=f"Bearer {token}",
        )


async def test_require_interview_token_rejects_garbage_token():
    with pytest.raises(AuthenticationError):
        await require_interview_token("anything", authorization="Bearer garbage")
