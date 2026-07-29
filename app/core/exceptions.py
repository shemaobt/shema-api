import logging
from typing import Final

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.enums import USER_SETTABLE_CLEANING_STATUSES

logger = logging.getLogger(__name__)

ERROR_CODE_UNAUTHORIZED = "UNAUTHORIZED"
ERROR_CODE_FORBIDDEN = "FORBIDDEN"
ERROR_CODE_CONFLICT = "CONFLICT"
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
ERROR_CODE_BAD_REQUEST = "BAD_REQUEST"
# Distinct from BAD_REQUEST: the payload parsed and every field is well formed, it just
# names a row that is not there. The client fixes it by picking a different id, not by
# reshaping the request.
ERROR_CODE_UNKNOWN_REFERENCE: Final = "UNKNOWN_REFERENCE"
ERROR_CODE_NOT_FOUND = "NOT_FOUND"
ERROR_CODE_INTERNAL = "INTERNAL_ERROR"
ERROR_CODE_UPSTREAM = "UPSTREAM_ERROR"


class AuthenticationError(Exception):
    pass


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
    """


class ValidationError(Exception):
    pass


class UpstreamServiceError(Exception):
    """A third-party provider failed on us — not a bad request from our client.

    Kept apart from ValidationError so a provider outage or rate limit does not masquerade
    as a 4xx: a client error page never pages anyone, and the right alert never fires.
    """


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


async def handle_not_found_error(_request: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content=_error_body(str(exc), ERROR_CODE_NOT_FOUND),
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
    app.add_exception_handler(StarletteHTTPException, handle_http_exception)  # type: ignore[arg-type]
    app.add_exception_handler(AuthenticationError, handle_authentication_error)  # type: ignore[arg-type]
    app.add_exception_handler(AuthorizationError, handle_authorization_error)  # type: ignore[arg-type]
    app.add_exception_handler(ConflictError, handle_conflict_error)  # type: ignore[arg-type]
    # Starlette walks the raised class's MRO, so the subclass wins over ConflictError
    # above regardless of the order these are registered in.
    app.add_exception_handler(SessionLockChanged, handle_session_lock_changed)  # type: ignore[arg-type]
    app.add_exception_handler(ProjectGranularityLocked, handle_project_granularity_locked)  # type: ignore[arg-type]
    app.add_exception_handler(RoleError, handle_role_error)  # type: ignore[arg-type]
    app.add_exception_handler(InvalidTokenError, handle_invalid_token)  # type: ignore[arg-type]
    app.add_exception_handler(NotFoundError, handle_not_found_error)  # type: ignore[arg-type]
    app.add_exception_handler(UnknownReferenceError, handle_unknown_reference)  # type: ignore[arg-type]
    app.add_exception_handler(ValidationError, handle_validation_error)  # type: ignore[arg-type]
    app.add_exception_handler(UpstreamServiceError, handle_upstream_service_error)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, handle_unexpected)
