"""The forms surface, and the module's two unauthenticated routes.

**The hole is here and it is two lines in a diff.** ``app/api/shema/__init__.py`` puts
``require_app_access`` on an inner router so that a route added by a later issue is refused
whether or not its author wired a guard; the two intake routes below are the one exception in
the module, by FE-44 §9.0 and ``docs/shema.md`` §6.6, and they are included into the **outer**
router — a named, deliberate line somebody has to write, rather than a dependency somebody has
to notice is missing. ``tests/test_shema/test_access.py`` reads the built application's route
table and fails on any ``/api/shema`` route not in ``UNAUTHENTICATED_PATHS``, so the exemption
is an edit in a file a reviewer reads.

**The token is the guard and the guard is not here.** ``verify_intake_token`` is a service
function (``app/services/shema/_intake_tokens.py``), which is what makes the rule hold for
every future caller of it rather than for the two routes it was written under — the same
argument the consent gate makes, at the seam that has no ``Authorization`` header to fall back
on. Nothing in this file decides who may pass; it decides only what is asked and what is
answered.

**Rate-limited on two keys, and both are needed.** The intake routes are unauthenticated by
design and are therefore the ones that will be found. A limit keyed on the caller's address
alone leaves a spread-out caller untouched; a limit keyed on the token alone leaves
enumeration untouched. Stacked, one link cannot be hammered from many places and many links
cannot be probed from one — and the numbers are chosen by what a leader on a bad connection
does (open the form, fill it, tap send, tap send again because nothing seemed to happen),
which is small, not by what the arithmetic prefers.

**Everything else on this router is a signed-in coordinator**, and ``PULSE_LOOP`` in the
console's own ``src/constants/forms.ts`` is why it is that role rather than any member:
generate, send and import are the coordinator's three steps of the five, and issuing a bearer
credential to somebody with no account is a different act from writing a record yourself.

``POST /api/shema/forms/pulse/{projectId}`` — the generated artifact — is **not here**, and its
absence is the only honest answer today: GATE-03 owns the format, which of two formats is
authoritative when they disagree, the distribution model and withdrawal from an
already-distributed file (``docs/shema.md`` §9.3). The prototype emits one thing and takes back
another and that pairing has never been confirmed with the client. What is *not* open is built:
the definitions, the validation, the archive, the idempotency and the link.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Header, Request, Response, status
from slowapi.util import get_remote_address

from app.api.shema._deps import APP_KEY, CoordinatorUser, CurrentUser, Db, Scope
from app.api.shema.projects import LOCAL_DAY_HEADER, _expected_version, _local_day
from app.core.rate_limit import limiter
from app.models.shema_forms import (
    IntakeForm,
    IntakeLink,
    IntakeLinkCreate,
    IntakeLinkCreated,
    IntakeSubmission,
    ReceivedSubmission,
    ReceivedSubmissionDetail,
    SubmissionImport,
)
from app.services.shema import (
    apply_submission,
    create_intake_link,
    import_submission,
    list_intake_links,
    list_submissions,
    read_intake_form,
    read_submission,
    receive_submission,
    revoke_intake_link,
)

router = APIRouter()

#: The unauthenticated routes, kept on their own router so the one line that mounts them
#: outside the module's guard is the line a reviewer is looking for.
intake = APIRouter()

#: What ``If-Match`` is for on an import. Quoted from the record's own ``PATCH`` because it is
#: the same guard: an import writes the record, and a write that cannot say which version it
#: is replacing has no basis for replacing one.
_IF_MATCH = (
    "The version the record was read at, from the ETag of the read. Required: an import is a "
    "write of the record and is guarded exactly as a typed save is."
)

#: How often one address may ask for a form. Generous against a leader reloading a page on a
#: connection that keeps dropping; small against a crawler that found the route.
INTAKE_READ_RATE_LIMIT = "30/minute"

#: How often one address may submit. A person fills this form once a month and taps send
#: twice; ten is the shape of that with room, and the second tap is a no-op anyway because the
#: archive is idempotent on the bytes.
INTAKE_WRITE_RATE_LIMIT = "10/minute"

#: What one **link** may do, whoever is holding it and from wherever. This is the half a
#: per-address limit cannot buy: a forwarded link being worked by many phones is one token, and
#: the bucket that notices is the token's.
INTAKE_LINK_RATE_LIMIT = "20/minute"


def intake_token_key(request: Request) -> str:
    """The rate-limit bucket for one link — the token's SHA-256, never the token.

    ``bearer_token_key`` in ``app/core/rate_limit.py`` buckets an authenticated caller the same
    way and for the same reason: the key function sees only the ``Request``, and a limiter's
    store is a place a credential should not be readable from. Defined in this module rather
    than beside that one because it has exactly one caller and reads a path parameter only this
    module has.

    Falls back to the address when there is no token in the path, so a misrouted request is
    still bucketed rather than sharing one global bucket with every other.
    """
    token = request.path_params.get("token")
    if not token:
        return get_remote_address(request)
    return hashlib.sha256(str(token).encode("utf-8")).hexdigest()


# --- the leader link -----------------------------------------------------------------


@router.post("/intake-links", response_model=IntakeLinkCreated, status_code=status.HTTP_201_CREATED)
async def mint_intake_link(
    payload: IntakeLinkCreate, db: Db, scope: Scope, user: CoordinatorUser
) -> IntakeLinkCreated:
    """Issue one project-scoped, expiring link, and hand back the only copy of its token.

    The response is the one place the raw token appears — not the row, not a later listing, not
    a log. A coordinator who loses it mints another and revokes this one, which is cheaper than
    any design in which the credential can be read back.
    """
    return await create_intake_link(
        db, scope, payload, user=user, app_key=APP_KEY, today=datetime.now(UTC).date()
    )


@router.get("/intake-links", response_model=list[IntakeLink])
async def list_links(
    db: Db, scope: Scope, user: CoordinatorUser, project_id: str | None = None
) -> list[IntakeLink]:
    """The links out on the projects this coordinator reaches — without their tokens.

    Here because *revocable* is only true if there is a way to find what to revoke. A
    revocation endpoint whose ids come only from the creation response is one that is used
    once, by whoever still has that response open.
    """
    return await list_intake_links(db, scope, project_id=project_id)


@router.post("/intake-links/{link_id}/revoke", response_model=IntakeLink)
async def revoke_link(link_id: str, db: Db, scope: Scope, user: CoordinatorUser) -> IntakeLink:
    """Close one link now, whatever its clock says. Revoking twice is not an error."""
    return await revoke_intake_link(db, scope, link_id, user=user)


# --- the submissions a coordinator reads and files ------------------------------------


@router.get("/forms/submissions", response_model=list[ReceivedSubmission])
async def received(
    db: Db, scope: Scope, user: CurrentUser, project_id: str | None = None
) -> list[ReceivedSubmission]:
    """FE-44 §9.9's inbox: everything received for the projects the caller reaches."""
    return await list_submissions(db, scope, project_id=project_id)


@router.get("/forms/submissions/{submission_id}", response_model=ReceivedSubmissionDetail)
async def received_detail(
    submission_id: str, db: Db, scope: Scope, user: CurrentUser
) -> ReceivedSubmissionDetail:
    """One submission opened — the answers as they arrived, beside the form they answered.

    Not in FE-44 §9.9's list and declared in the PR. Without it the archive is write-only and
    the free-text answers the import deliberately does not apply to the record are kept where
    nobody can read them, which is the failure the issue names in its own words.
    """
    return await read_submission(db, scope, submission_id, user=user)


@router.post(
    "/forms/submissions", response_model=ReceivedSubmission, status_code=status.HTTP_201_CREATED
)
async def file_submission(
    payload: SubmissionImport,
    request: Request,
    db: Db,
    scope: Scope,
    user: CoordinatorUser,
    if_match: Annotated[str, Header(alias="If-Match", description=_IF_MATCH)],
    local_day: Annotated[str | None, Header(alias=LOCAL_DAY_HEADER)] = None,
) -> ReceivedSubmission:
    """File an answer that reached the coordinator some other way, and apply it in one call.

    ``request.body()`` is read for the archive and not for the parsing: *the submission is
    archived byte-identically*, so what is kept is what arrived rather than this server's
    re-serialisation of what it understood. FastAPI has already buffered and parsed it, so the
    second read costs nothing and cannot disagree with the first.
    """
    today = datetime.now(UTC).date()
    return await import_submission(
        db,
        scope,
        payload,
        payload_bytes=await request.body(),
        user=user,
        app_key=APP_KEY,
        expected_version=_expected_version(if_match),
        day=_local_day(local_day, utc_today=today),
    )


@router.post("/forms/submissions/{submission_id}/import", response_model=ReceivedSubmission)
async def import_received(
    submission_id: str,
    db: Db,
    scope: Scope,
    user: CoordinatorUser,
    if_match: Annotated[str, Header(alias="If-Match", description=_IF_MATCH)],
    local_day: Annotated[str | None, Header(alias=LOCAL_DAY_HEADER)] = None,
) -> ReceivedSubmission:
    """Apply a submission that arrived through a link — ``PULSE_LOOP``'s ``import`` step.

    Not in FE-44 §9.9's list and declared in the PR. That list was written when the link's
    answer and the file's answer were assumed to come through one door; they do not, because
    only one of the two has a person behind it who can be named in the record's audit trail.
    """
    today = datetime.now(UTC).date()
    return await apply_submission(
        db,
        scope,
        submission_id,
        user=user,
        expected_version=_expected_version(if_match),
        day=_local_day(local_day, utc_today=today),
    )


# --- the two unauthenticated routes ---------------------------------------------------


@intake.get("/intake/{token}", response_model=IntakeForm)
@limiter.limit(INTAKE_READ_RATE_LIMIT, key_func=get_remote_address)
@limiter.limit(INTAKE_LINK_RATE_LIMIT, key_func=intake_token_key)
async def open_intake_form(token: str, request: Request, db: Db) -> IntakeForm:
    """The form behind one live link — the whole of what the link grants.

    It carries the definition, the language name and the day the link dies. It does not carry
    the location, the country, the base, a contact, a count, a need, a note or a prayer
    request, and the query underneath reads one column so there is nothing else to carry.
    ``tests/test_shema/test_intake_link.py`` proves the negative directly, against a project
    whose every column holds a distinct sentinel.
    """
    return await read_intake_form(db, token)


@intake.post("/intake/{token}", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit(INTAKE_WRITE_RATE_LIMIT, key_func=get_remote_address)
@limiter.limit(INTAKE_LINK_RATE_LIMIT, key_func=intake_token_key)
async def submit_intake_form(
    token: str, payload: IntakeSubmission, request: Request, db: Db
) -> Response:
    """Take one answer. **202, and the 202 is the design** — accepted, not applied.

    The submission is validated whole against the version the link was minted with, archived
    byte-identically, and announced to the coordinators and mentors whose region it is in. What
    it does not do is write the record: that is a coordinator's act, through
    ``POST /forms/submissions/{id}/import``, for the reasons
    ``app/services/shema/receive_submission.py`` sets out.

    The body is empty. There is nothing to answer an anonymous caller with that they did not
    send, and *your submission has been recorded against project X, version Y* is a sentence
    that tells a forwarded link more than it told the leader.
    """
    await receive_submission(
        db, token, payload, payload_bytes=await request.body(), app_key=APP_KEY
    )
    return Response(status_code=status.HTTP_202_ACCEPTED)
