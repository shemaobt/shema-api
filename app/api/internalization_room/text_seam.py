"""What both of the runner's seams share: the runner key, and the calls a turn made.

The Golden doors (`golden_doors.py`) and the back-translation door are test surfaces and
not product ones. Every one of them exists only where a runner key is configured, which
production never sets, and answers its caller with the model calls the turn paid for.
"""

from __future__ import annotations

import logging
import secrets
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from fastapi import Depends, Header

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError, NotFoundError, ValidationError
from app.models.internalization_room_text_seam import ModelCall, Outcome
from app.services import internalization_room as room
from app.services.internalization_room.languages import LANGUAGE_NAMES, normalize

#: The header the back-translation seam reads the runner key in. The Golden doors read the
#: same key as her runner sends it, a bearer credential.
ACCESS_CODE_HEADER = "X-Access-Code"


def _the_runner_key(presented: str | None, header: str) -> None:
    """The runner at a seam's door — and no door at all where no key was configured.

    Production sets no key, so every door behind it answers there as a route that does not
    exist: a 401 would announce a credential worth guessing at on a public deployment, and a
    400 naming the missing variable would say what to set. Only a deployment somebody pointed
    a runner at has anything here to refuse. One rule, whichever header the door reads.
    """
    configured = get_settings().internalization_room_runner_key
    if not configured:
        raise NotFoundError("Not Found")
    if not presented or not secrets.compare_digest(presented.encode(), configured.encode()):
        raise AuthenticationError(f"Missing or invalid {header} header")


async def require_runner(
    x_access_code: str | None = Header(default=None, alias=ACCESS_CODE_HEADER),
) -> None:
    _the_runner_key(x_access_code, ACCESS_CODE_HEADER)


runner_dep = Depends(require_runner)

#: The calls the turn in flight has made, when a turn is collecting them. A context variable
#: because the record is written by `call_agent` deep inside the turn, on the same task, and
#: two runners driving two sessions at once must not read each other's calls.
_COLLECTING: ContextVar[list[ModelCall] | None] = ContextVar(
    "internalization_room_text_seam_calls", default=None
)


class _ModelCalls(logging.Handler):
    """Reads each answered call off the usage line `call_agent` already writes.

    Not a second ledger: the room reports what a call cost in exactly one place, and this is
    that line read back for the runner instead of only for the operator's grep. A record that
    names a rung without token counts is the ladder stepping down, not a call answered.
    """

    def emit(self, record: logging.LogRecord) -> None:
        calls = _COLLECTING.get()
        written = record.__dict__
        if calls is None or "input_tokens" not in written:
            return
        calls.append(
            ModelCall(
                role=written["role"],
                rung=written["rung"],
                input_tokens=written["input_tokens"],
                output_tokens=written["output_tokens"],
                cache_read_tokens=written["cache_read_tokens"],
                cache_write_tokens=written["cache_write_tokens"],
                latency_ms=written.get("latency_ms"),
                cost_usd=written.get("cost_usd"),
            )
        )


logging.getLogger("app.services.internalization_room.llm").addHandler(_ModelCalls())


@contextmanager
def _collecting_model_calls() -> Iterator[list[ModelCall]]:
    calls: list[ModelCall] = []
    token = _COLLECTING.set(calls)
    try:
        yield calls
    finally:
        _COLLECTING.reset(token)


def _outcome_tag(outcome: room.TurnOutcome) -> Outcome:
    """The tag the judge is defined against, read off what the turn already records.

    A turn that fell to a pre-approved line says so. A voiced turn carrying the Validator's
    issues is one the Validator mended: its contract lists no issues on a `pass`, and the only
    other verdict that voices anything is `correct`, which lists every problem it repaired.
    """
    if outcome.used_fail_safe:
        return "fail_safe"
    if outcome.issues:
        return "corrected"
    return "pass"


def _language_code(named: str) -> str:
    """The room's code for a language named either way her scripts and our app name it."""
    code = normalize(named)
    if code is not None:
        return code
    spoken = named.casefold()
    for candidate, name in LANGUAGE_NAMES.items():
        if name.casefold() in spoken and normalize(candidate) is not None:
            return candidate
    raise ValidationError(f"The room does not speak {named!r}")
