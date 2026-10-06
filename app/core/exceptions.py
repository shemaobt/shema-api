from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Final

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.enums import USER_SETTABLE_CLEANING_STATUSES

if TYPE_CHECKING:
    # Only for the type checker: `canon/labels.py` reaches back into this module through
    # `canon/parse_map.py`'s own `from app.core.exceptions import ValidationError`, so a real
    # top-level import here would be circular. `from __future__ import annotations` above
    # means this name is never looked up at runtime — `register_exception_handlers` imports
    # the real class itself, deferred, where it needs the object rather than the type.
    from app.services.internalization_room.canon.labels import ElementLabelsBroken

logger = logging.getLogger(__name__)

ERROR_CODE_UNAUTHORIZED = "UNAUTHORIZED"
ERROR_CODE_FORBIDDEN = "FORBIDDEN"
ERROR_CODE_CONFLICT: Final = "CONFLICT"
# A 409 that means "someone else is editing this", not "your copy is stale". The two
# land on the same route and demand opposite reactions from the client — reload and
# retry, versus stop writing and open in review — so they cannot share a code.
ERROR_CODE_SESSION_LOCKED: Final = "SESSION_LOCKED"
# A third reaction: the lease refused the write and then lapsed, so there is nobody to
# name and nothing to reload from. Neither of the other two fits — CONFLICT promises a
# current_version these routes do not have, and SESSION_LOCKED promises a holder that no
# longer exists. Just try again.
ERROR_CODE_SESSION_LOCK_CHANGED: Final = "SESSION_LOCK_CHANGED"
ERROR_CODE_PROJECT_GRANULARITY_LOCKED: Final = "PROJECT_GRANULARITY_LOCKED"
#: An approval that cannot be numbered, because a release is named by project, pericope
#: and version and this session names no project. Its own code because the tablet acts on
#: it: nothing about the passage is wrong and retrying changes nothing — the room was
#: opened on the shared key, and only a credentialed device can approve.
ERROR_CODE_RELEASE_WITHOUT_PROJECT: Final = "RELEASE_WITHOUT_PROJECT"
#: A force asked for without the word that makes it one. Its own code for the reason above:
#: nothing about the passage is wrong and retrying changes nothing — the Desk arms the force
#: and asks again, and answering CONFLICT would send it looking for a blocker instead.
ERROR_CODE_NOTHING_TO_FORCE: Final = "NOTHING_TO_FORCE"
ERROR_CODE_REPLY_MOVED_ON: Final = "REPLY_MOVED_ON"
#: A heard mark on a question nobody has answered. Its own code for the reason above: there is
#: no version to reload and nothing to force — the tablet reads any non-2xx as not heard.
ERROR_CODE_NOTHING_TO_HEAR: Final = "NOTHING_TO_HEAR"
ERROR_CODE_BAD_REQUEST = "BAD_REQUEST"
#: A correction or a division aimed at a stretch that no longer counts. Its own code because
#: the tablet acts on it: it drops the pending translation and re-reads its stretches, which is
#: the wrong response to every other BAD_REQUEST, and it must not tell the two apart by the words.
ERROR_CODE_STRETCH_NO_LONGER_COUNTS: Final = "STRETCH_NO_LONGER_COUNTS"
#: A telling whose transcription holds no words. Its own code because the tablet says the
#: inaudible line named in the body instead of showing a refused call, and it must not tell
#: this from any other 422 by the words.
ERROR_CODE_WORDLESS_TELLING: Final = "WORDLESS_TELLING"
ERROR_CODE_PASSAGE_CLOSED: Final = "PASSAGE_CLOSED"
ERROR_CODE_IDEMPOTENCY_KEY_IN_FLIGHT: Final = "IDEMPOTENCY_KEY_IN_FLIGHT"
ERROR_CODE_IDEMPOTENCY_KEY_REUSED: Final = "IDEMPOTENCY_KEY_REUSED"
# Distinct from BAD_REQUEST: the payload parsed and every field is well formed, it just
# names a row that is not there. The client fixes it by picking a different id, not by
# reshaping the request.
ERROR_CODE_UNKNOWN_REFERENCE: Final = "UNKNOWN_REFERENCE"
ERROR_CODE_NOT_FOUND = "NOT_FOUND"
ERROR_CODE_INTERNAL = "INTERNAL_ERROR"
ERROR_CODE_UPSTREAM = "UPSTREAM_ERROR"
#: A model answered and the answer could not be read. Not UPSTREAM_ERROR: the provider was
#: up, and a code that says otherwise sends the investigation to the wrong place.
ERROR_CODE_UNREADABLE_REPLY: Final = "UNREADABLE_REPLY"

#: A device whose credential was revoked. Its own code because the tablet acts on it: it
#: forgets the credential it holds and shows its claim code again, which is the wrong
#: response to every other refusal.
ERROR_CODE_DEVICE_REVOKED: Final = "DEVICE_REVOKED"


class AuthenticationError(Exception):
    pass


class DeviceRevoked(AuthenticationError):
    """A device presented the credential a facilitator took away from it.

    Its own exception rather than a bare AuthenticationError because the two refusals ask
    the tablet for different things. An unrecognised credential is a bug on the device and
    it should keep what it has; a revoked one means the device is out of service and must
    forget its credential and show a claim code. A single 401 for both leaves the app
    unable to choose, and choosing wrong either wipes a working tablet or keeps a
    decommissioned one asking.

    Raising it does not mean the credential still authenticates — it does not, and nothing
    reads the column that recognises it until authentication has already failed.
    """


class AuthorizationError(Exception):
    pass


class ConflictError(Exception):
    pass


class SessionLockChanged(ConflictError):
    """A guarded write was refused by a lease that had lapsed by the time we looked.

    Its own exception rather than a bare ConflictError because the handler is what puts
    the code on the wire, and the generic one says CONFLICT — which this API defines as
    a stale version carrying a current_version to reload from.
    """


class ProjectGranularityLocked(ConflictError):
    """The project's bead granularity was asked to move after something was cut at it.

    Its own exception for the same reason SessionLockChanged is: the generic CONFLICT
    code promises a version to reload from, and there is none. Nothing the client can do
    makes this write succeed — re-cutting a project at a new granularity re-derives every
    manifest_id it has exported, which is a migration, not a retry.
    """


class ReleaseWithoutProject(ConflictError):
    """A session opened on the shared room key was asked to approve its passage.

    Its own exception for the reason SessionLockChanged is: the generic CONFLICT code
    promises a version to reload from, and there is none. Refused rather than numbered in
    a group belonging to nobody, because a release is named by project, pericope and
    version, and the shared key names no project.
    """


class NothingToForce(ConflictError):
    """The force route was called by a body that does not ask for a force.

    Its own exception beside ``ReleaseWithoutProject`` and for the same reason: the generic
    CONFLICT code promises a blocker or a version to reload from, and there is neither. The
    session was not even looked at — a route whose only purpose is to overrule the gate has
    nothing to say about a caller who did not ask it to.
    """


class ReplyMovedOn(ConflictError):
    """The reply the tablet heard is no longer the question's current one.

    Its own exception for the reason SessionLockChanged is: the generic CONFLICT code
    promises a version to reload from, and there is none. The tablet reads any non-2xx as
    not heard and offers the reply again.
    """


class NothingToHear(ConflictError):
    """A heard mark on a question that carries no reply.

    Its own exception for the reason ReplyMovedOn is: there is no version to reload from.
    A card the facilitator has not answered can never read as heard, whatever the tablet
    sends; the tablet reads any non-2xx as not heard, and there was nothing to offer.
    """


class IdempotencyKeyInFlight(ConflictError):
    pass


class PassageClosed(ConflictError):
    pass


class RoleError(Exception):
    pass


class InvalidTokenError(Exception):
    pass


class NotFoundError(Exception):
    pass


class UnknownReferenceError(Exception):
    """A write named a foreign key that does not exist.

    Kept apart from ValidationError, which answers 400: nothing about the request is
    malformed, so 422 is the honest status — the same one FastAPI already gives for a
    body it could parse but not accept. Before this existed the database raised, the
    error escaped the service, and the caller got a 500 for their own bad id.

    Sharing the status with FastAPI means sharing it with a different body: FastAPI puts
    a list of field errors in ``detail`` and nothing here registers a handler for
    ``RequestValidationError``, so a client meets two shapes on 422. ``code`` is what
    tells them apart — FastAPI's 422 carries no ``code`` at all, so a client that reads
    ``detail`` as a string only after matching ``code`` never meets the list. Unifying
    the two would mean rewriting the body of every validation error the API returns,
    which breaks existing clients and is not this exception's to do.
    """


class ValidationError(Exception):
    pass


class NoWordsHeard(ValidationError):
    """The recognizer heard the take and found no words in it, which is not a refusal.

    It carries the language the recognizer still reported, because a take with no words is
    told apart from a missed one by its length, and the record keeps what was heard.
    """

    def __init__(
        self,
        message: str,
        *,
        language_code: str | None = None,
        language_probability: float | None = None,
    ) -> None:
        super().__init__(message)
        self.language_code = language_code
        self.language_probability = language_probability


class StretchNoLongerCounts(ValidationError):
    """A stretch that was replaced, or whose Part was recorded again, was addressed anyway.

    Its own exception for the reason ERROR_CODE_STRETCH_NO_LONGER_COUNTS gives; still a 400.
    """


class WordlessTelling(ValidationError):
    """A telling was transcribed and holds no words, so it is no stretch and counts nothing.

    Carries the name of the inaudible line the room says in its place, chosen by whoever
    refuses, because the handler has no session to choose it from.
    """

    def __init__(self, fixed_line: str) -> None:
        super().__init__("The telling has no words in it")
        self.fixed_line = fixed_line


class IdempotencyKeyReused(ValidationError):
    pass


class StoredAnswer(Exception):
    def __init__(self, status_code: int, body: bytes) -> None:
        super().__init__("The answer stored under this Idempotency-Key")
        self.status_code = status_code
        self.body = body


class UpstreamServiceError(Exception):
    """A third-party provider failed on us — not a bad request from our client.

    Kept apart from ValidationError so a provider outage or rate limit does not masquerade
    as a 4xx: a client error page never pages anyone, and the right alert never fires.
    """


def upstream_or_validation_error(status_code: int, message: str) -> Exception:
    """Their outage is not our client's bad request.

    A revoked key or an exhausted quota (401, 403) is not silence any more than a rate
    limit is: both mean ElevenLabs refused the request, not that the room said nothing.
    """
    if status_code in (401, 403, 429) or status_code >= 500:
        return UpstreamServiceError(message)
    return ValidationError(message)


class UnreadableReply(Exception):
    """A model answered, and the answer could not be read — not a provider that is down.

    Kept apart from `UpstreamServiceError` because the two send an investigation to
    opposite places. On 2026-09-02 the analyst answered a real session with valid JSON
    and valid findings, the parser refused the reply over a contradiction it had no rule
    for, and the route raised the upstream error: the log said the provider had failed,
    the team heard that the service was unavailable, and a whole investigation went
    looking for an outage that never happened. Whoever raises this has the reply in
    hand; the parser that refused it is expected to have logged it with the reason.

    Still a 502: the reply *is* an invalid response from upstream, in the sense that
    status code has always had. Only the code and the log change.
    """


class TranscriptionDefect(Exception):
    """A mistake of ours on a transcription path — not a provider that is down.

    Kept apart from `UpstreamServiceError` for the same reason that one is kept apart from
    `ValidationError`: swallowing our own bug as if the provider were unavailable is how a
    defect produces empty transcripts for months and nobody looks. Raised with the original
    error as its cause and logged with a stack trace, so the difference survives in the type
    and in the log even where the caller answers the client as if nothing had gone wrong.

    It carries what the caller needs to answer without the object it could not finish
    working on. On the room's question path that is the raised hand: the question is already
    committed when this is raised, and a team standing in a room must not be told to record
    it again because of a bug on our side.
    """

    def __init__(self, *, question_id: str, status: str) -> None:
        super().__init__(f"Transcription failed on our side for {question_id}")
        self.question_id = question_id
        self.status = status


class InvalidCleaningStatusError(ValidationError):
    def __init__(self, status: str) -> None:
        super().__init__(
            f"Invalid cleaning status '{status}'. "
            f"Valid statuses are: {', '.join(USER_SETTABLE_CLEANING_STATUSES)}"
        )


class SecondaryClassificationConflictError(ValidationError):
    def __init__(self) -> None:
        super().__init__(
            "secondary classification must differ from the primary in at least "
            "one of register, genre, or subcategory"
        )


class SegmentClassificationConflictError(ValidationError):
    def __init__(self, segment_index: int) -> None:
        super().__init__(
            f"Segment {segment_index} primary classification would equal the "
            "parent recording's secondary classification."
        )


def _error_body(detail: str, code: str) -> dict[str, str]:
    return {"detail": detail, "code": code}


async def handle_authentication_error(_request: Request, exc: AuthenticationError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content=_error_body(str(exc), ERROR_CODE_UNAUTHORIZED),
    )


async def handle_device_revoked(_request: Request, exc: DeviceRevoked) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content=_error_body(str(exc), ERROR_CODE_DEVICE_REVOKED),
    )


async def handle_authorization_error(_request: Request, exc: AuthorizationError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content=_error_body(str(exc), ERROR_CODE_FORBIDDEN),
    )


async def handle_conflict_error(_request: Request, exc: ConflictError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content=_error_body(str(exc), ERROR_CODE_CONFLICT),
    )


async def handle_session_lock_changed(_request: Request, exc: SessionLockChanged) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content=_error_body(str(exc), ERROR_CODE_SESSION_LOCK_CHANGED),
    )


async def handle_project_granularity_locked(
    _request: Request, exc: ProjectGranularityLocked
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content=_error_body(str(exc), ERROR_CODE_PROJECT_GRANULARITY_LOCKED),
    )


async def handle_release_without_project(
    _request: Request, exc: ReleaseWithoutProject
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content=_error_body(str(exc), ERROR_CODE_RELEASE_WITHOUT_PROJECT),
    )


async def handle_nothing_to_force(_request: Request, exc: NothingToForce) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content=_error_body(str(exc), ERROR_CODE_NOTHING_TO_FORCE),
    )


async def handle_reply_moved_on(_request: Request, exc: ReplyMovedOn) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content=_error_body(str(exc), ERROR_CODE_REPLY_MOVED_ON),
    )


async def handle_nothing_to_hear(_request: Request, exc: NothingToHear) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content=_error_body(str(exc), ERROR_CODE_NOTHING_TO_HEAR),
    )


async def handle_passage_closed(_request: Request, exc: PassageClosed) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content=_error_body(str(exc), ERROR_CODE_PASSAGE_CLOSED),
    )


async def handle_stretch_no_longer_counts(
    _request: Request, exc: StretchNoLongerCounts
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=_error_body(str(exc), ERROR_CODE_STRETCH_NO_LONGER_COUNTS),
    )


async def handle_wordless_telling(_request: Request, exc: WordlessTelling) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            **_error_body(str(exc), ERROR_CODE_WORDLESS_TELLING),
            "fixed_line": exc.fixed_line,
        },
    )


async def handle_idempotency_key_in_flight(
    _request: Request, exc: IdempotencyKeyInFlight
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content=_error_body(str(exc), ERROR_CODE_IDEMPOTENCY_KEY_IN_FLIGHT),
    )


async def handle_idempotency_key_reused(
    _request: Request, exc: IdempotencyKeyReused
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=_error_body(str(exc), ERROR_CODE_IDEMPOTENCY_KEY_REUSED),
    )


async def handle_stored_answer(_request: Request, exc: StoredAnswer) -> Response:
    return Response(exc.body, exc.status_code, media_type="application/json")


async def handle_role_error(_request: Request, exc: RoleError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=_error_body(str(exc), ERROR_CODE_BAD_REQUEST),
    )


async def handle_invalid_token(_request: Request, exc: InvalidTokenError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content=_error_body(str(exc) or "Invalid or expired token", ERROR_CODE_UNAUTHORIZED),
    )


async def handle_unknown_reference(_request: Request, exc: UnknownReferenceError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=_error_body(str(exc), ERROR_CODE_UNKNOWN_REFERENCE),
    )


async def handle_validation_error(_request: Request, exc: ValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=_error_body(str(exc), ERROR_CODE_BAD_REQUEST),
    )


async def handle_upstream_service_error(
    _request: Request, exc: UpstreamServiceError
) -> JSONResponse:
    logger.warning("Upstream service failure: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content=_error_body(str(exc), ERROR_CODE_UPSTREAM),
    )


async def handle_unreadable_reply(_request: Request, exc: UnreadableReply) -> JSONResponse:
    logger.warning("Model reply could not be read: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content=_error_body(str(exc), ERROR_CODE_UNREADABLE_REPLY),
    )


async def handle_not_found_error(_request: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content=_error_body(str(exc), ERROR_CODE_NOT_FOUND),
    )


async def handle_element_labels_broken(_request: Request, exc: ElementLabelsBroken) -> JSONResponse:
    """Our own label catalogue is holed — the caller's request was fine.

    Still a 500, and still logged as ours: `ElementLabelsBroken`'s own docstring argues why a
    hole in a file we ship is never the caller's mistake. What changes is that the body names
    the pericope, the key and the language `str(exc)` already carries, instead of the generic
    catch-all's "please try again later" — the difference between a blank Desk screen and one
    that says which bead is missing.

    `logger.exception`, not `logger.error`: a specific handler stays on `ExceptionMiddleware`,
    which does not re-raise once it has built a response, unlike `ServerErrorMiddleware` for
    the bare-`Exception` fallback this used to reach — so `handle_unexpected`'s own
    `logger.exception` never runs for this one, and this is the only place left to keep the
    stack trace.
    """
    logger.exception("Label catalogue is broken: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_error_body(str(exc), ERROR_CODE_INTERNAL),
    )


async def handle_unexpected(_request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_error_body(
            "An unexpected error occurred. Please try again later.",
            ERROR_CODE_INTERNAL,
        ),
    )


async def handle_http_exception(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = ERROR_CODE_INTERNAL
    status_code = exc.status_code
    detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    if status_code == status.HTTP_401_UNAUTHORIZED:
        code = ERROR_CODE_UNAUTHORIZED
    elif status_code == status.HTTP_403_FORBIDDEN:
        if detail == "Not authenticated":
            status_code = status.HTTP_401_UNAUTHORIZED
            code = ERROR_CODE_UNAUTHORIZED
        else:
            code = ERROR_CODE_FORBIDDEN
    elif status_code == status.HTTP_404_NOT_FOUND:
        code = ERROR_CODE_NOT_FOUND
    elif status_code == status.HTTP_409_CONFLICT:
        code = ERROR_CODE_CONFLICT
    elif 400 <= status_code < 500:
        code = ERROR_CODE_BAD_REQUEST
    return JSONResponse(
        status_code=status_code,
        content=_error_body(detail, code),
    )


def register_exception_handlers(app: FastAPI) -> None:
    # The real class, not just the type: `add_exception_handler` needs the object to match
    # against. Deferred rather than a top-level import for the same circularity the
    # `TYPE_CHECKING` block above avoids — by the time this function runs, every router has
    # already imported `canon/labels.py` in full, so this is safe.
    from app.services.internalization_room.canon.labels import ElementLabelsBroken

    app.add_exception_handler(StarletteHTTPException, handle_http_exception)  # type: ignore[arg-type]
    app.add_exception_handler(AuthenticationError, handle_authentication_error)  # type: ignore[arg-type]
    app.add_exception_handler(AuthorizationError, handle_authorization_error)  # type: ignore[arg-type]
    # Same MRO rule as SessionLockChanged below: the subclass wins over AuthenticationError.
    app.add_exception_handler(DeviceRevoked, handle_device_revoked)  # type: ignore[arg-type]
    app.add_exception_handler(ConflictError, handle_conflict_error)  # type: ignore[arg-type]
    # Starlette walks the raised class's MRO, so the subclass wins over ConflictError
    # above regardless of the order these are registered in.
    app.add_exception_handler(SessionLockChanged, handle_session_lock_changed)  # type: ignore[arg-type]
    app.add_exception_handler(ProjectGranularityLocked, handle_project_granularity_locked)  # type: ignore[arg-type]
    app.add_exception_handler(ReleaseWithoutProject, handle_release_without_project)  # type: ignore[arg-type]
    app.add_exception_handler(NothingToForce, handle_nothing_to_force)  # type: ignore[arg-type]
    app.add_exception_handler(ReplyMovedOn, handle_reply_moved_on)  # type: ignore[arg-type]
    app.add_exception_handler(NothingToHear, handle_nothing_to_hear)  # type: ignore[arg-type]
    app.add_exception_handler(PassageClosed, handle_passage_closed)  # type: ignore[arg-type]
    app.add_exception_handler(RoleError, handle_role_error)  # type: ignore[arg-type]
    app.add_exception_handler(InvalidTokenError, handle_invalid_token)  # type: ignore[arg-type]
    app.add_exception_handler(NotFoundError, handle_not_found_error)  # type: ignore[arg-type]
    app.add_exception_handler(UnknownReferenceError, handle_unknown_reference)  # type: ignore[arg-type]
    app.add_exception_handler(StretchNoLongerCounts, handle_stretch_no_longer_counts)  # type: ignore[arg-type]
    app.add_exception_handler(WordlessTelling, handle_wordless_telling)  # type: ignore[arg-type]
    app.add_exception_handler(IdempotencyKeyInFlight, handle_idempotency_key_in_flight)  # type: ignore[arg-type]
    app.add_exception_handler(IdempotencyKeyReused, handle_idempotency_key_reused)  # type: ignore[arg-type]
    app.add_exception_handler(StoredAnswer, handle_stored_answer)  # type: ignore[arg-type]
    app.add_exception_handler(ValidationError, handle_validation_error)  # type: ignore[arg-type]
    app.add_exception_handler(UpstreamServiceError, handle_upstream_service_error)  # type: ignore[arg-type]
    app.add_exception_handler(UnreadableReply, handle_unreadable_reply)  # type: ignore[arg-type]
    app.add_exception_handler(ElementLabelsBroken, handle_element_labels_broken)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, handle_unexpected)
