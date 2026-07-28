"""Guard: every token decoder pins an explicit algorithm allowlist, so a token
signed with any other algorithm is rejected (no algorithm confusion).

Both decoders are covered — including the interview-token one, which decodes
tokens handed to external interviewees.

This guards the allowlists, not a CVE: the `python-jose == 3.5.0` pin is what
carries the CVE-2024-33663/33664 fixes.
"""

from __future__ import annotations

import pytest
from jose import jwt

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError, InvalidTokenError
from app.services.project_health.interview_token import (
    INTERVIEW_TOKEN_AUDIENCE,
    decode_interview_token,
)
from app.utils.jwt import decode_token

DECODERS = [
    pytest.param(
        decode_token,
        {"sub": "u", "type": "access"},
        InvalidTokenError,
        id="access-token",
    ),
    pytest.param(
        decode_interview_token,
        {"sub": "i", "aud": INTERVIEW_TOKEN_AUDIENCE},
        AuthenticationError,
        id="interview-token",
    ),
]


@pytest.mark.parametrize("decode,claims,expected_error", DECODERS)
def test_decode_rejects_algorithm_outside_the_allowlist(decode, claims, expected_error):
    settings = get_settings()
    other = "HS512" if settings.jwt_algorithm != "HS512" else "HS384"
    forged = jwt.encode(claims, settings.jwt_secret_key, algorithm=other)
    with pytest.raises(expected_error):
        decode(forged)
