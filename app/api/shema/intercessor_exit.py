"""The intercessor's exit link — the module's second unauthenticated seam.

A person in the prayer network has no account and never will, and until the client's answer of
22/sep there was no way for them to leave (*"ainda não existe caminho"*). Every send to the
network carries a link to the console's exit page (``/leave/{token}``); the page calls the two
routes below, and neither carries an ``Authorization`` requirement: **the token is the guard,
and the guard is a service function** (``leave_intercessor.py``), for the reason
``docs/shema.md`` §6.6 gives for the leader link.

**Opening changes nothing; confirming erases.** ``GET`` answers 204 while the link still opens
something — the page needs nothing else, and shows nothing about the person, because a
forwarded link must not tell whoever holds it who is in the network. ``POST`` erases the person,
their consents and every link they held, and answers 204. A link previewer fetches every URL it
is given, which is why the ``GET`` is not the act. Every link that opens nothing — unknown,
expired, already spent — is the same 404 with the same sentence.

**Included into the outer router on a named line** in ``app/api/shema/__init__.py``, and listed
in ``tests/test_shema/test_access.py``'s ``UNAUTHENTICATED_PATHS``: the exemption is an edit a
reviewer reads, as the intake's is.

**Rate-limited per address, and the bucket is named rather than inferred.** slowapi's default
scope for ``@limiter.limit`` is the request's URL, and here the URL carries the token — so a
limit written that way is per address *and per token*, which never notices one address walking
many tokens, and it keeps the raw token in the limiter's key. ``shared_limit`` with a fixed scope
makes the address the whole key. The numbers are what a person does on a bad connection: open
the page a few times, tap the button twice.

**No** ``from __future__ import annotations`` **in this file**, for the reason ``forms.py``
gives at length: the limit wraps the handler, and a string annotation would be resolved against
slowapi's module, turning ``Db`` into a required query parameter.
"""

from fastapi import APIRouter, Request, Response, status
from slowapi.util import get_remote_address

from app.api.shema._deps import Db
from app.core.rate_limit import limiter
from app.services.shema import leave_network, open_exit_link

router = APIRouter()

_EXIT = "/intercessors/leave/{token}"

#: How often one address may open exit pages. Generous against a phone reloading on a dropping
#: connection, small against somebody walking tokens.
EXIT_READ_RATE_LIMIT = "30/minute"

#: How often one address may confirm. A person leaves once and taps twice.
EXIT_WRITE_RATE_LIMIT = "10/minute"


@router.get(_EXIT, status_code=status.HTTP_204_NO_CONTENT, response_model=None)
@limiter.shared_limit(
    EXIT_READ_RATE_LIMIT, scope="intercessor-exit-read", key_func=get_remote_address
)
async def open_exit(token: str, request: Request, db: Db) -> Response:
    """Whether this link still lets somebody leave. Reads only; answers nothing but the fact."""
    await open_exit_link(db, token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(_EXIT, status_code=status.HTTP_204_NO_CONTENT, response_model=None)
@limiter.shared_limit(
    EXIT_WRITE_RATE_LIMIT, scope="intercessor-exit-write", key_func=get_remote_address
)
async def confirm_exit(token: str, request: Request, db: Db) -> Response:
    """Leave the network: the person, their consents and their links leave storage."""
    await leave_network(db, token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
