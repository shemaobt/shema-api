from __future__ import annotations

import hashlib

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request

limiter = Limiter(key_func=get_remote_address)


def bearer_token_key(request: Request) -> str:
    """Rate-limit bucket for an authenticated caller, falling back to the client address.

    `get_remote_address` puts a whole office — and everything behind one proxy — in a single
    bucket, so one abusive caller throttles everyone else. Metered endpoints want per-caller.

    ponytail: the bucket is the access token, not the user id: the key_func only sees the
    Request, and reading the user id means decoding the JWT before the auth dependency does.
    Someone holding two live tokens gets two buckets, which is fine — the abuse this guards
    against is a retry loop on one token, not a user minting sessions to grind past a limit.
    """
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() == "bearer" and token:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()
    return get_remote_address(request)
