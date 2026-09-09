"""The budget attachment on the wire: one file per request, private end to end.

Thin by the house rule: the two handlers parse, call one service and shape the answer.
The one piece of logic that *must* live here is the 10 MB ceiling, because 413 is an HTTP
answer about an HTTP body and the service never sees a request object.

**The upload takes a raw body, not multipart, and the ceiling is why.** FastAPI parses a
multipart body before any handler code runs, so an ``UploadFile`` route can only measure
what it has already read — which is exactly the mistake ``app/services/storage/upload.py``
makes (``await file.read()`` first, compare after) and this issue names as the one not to
repeat. With the file as the body itself, ``Content-Length`` *is* the file's size, the
header is checked before a byte of body is read, and a liar (or a chunked sender) is
caught by the capped read that follows. The declared type rides where HTTP puts it — the
``Content-Type`` header — and the display filename in a query parameter.

The guard is ``CanEditRequests`` on both routes, the same capability the request's own
lifecycle wears, and the row scope lives in the service (``get_request``): whoever may
read the request may read its file, out of scope answers 404, and the download is a
signed URL that expires in minutes — no public URL exists on any path here.
"""

from fastapi import APIRouter, HTTPException, Request, status

from app.api.resource_requests._deps import APP_KEY, CanEditRequests, Db
from app.models.resource_request import AttachmentDownloadOut, AttachmentOut
from app.services import resource_request as service
from app.services.resource_request._attachment_rules import MAX_ATTACHMENT_BYTES

router = APIRouter(tags=["resource requests"])

_TOO_LARGE = HTTPException(
    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
    detail=f"The attachment exceeds the {MAX_ATTACHMENT_BYTES // (1024 * 1024)} MB limit.",
)


async def _capped_body(request: Request) -> bytes:
    """The request body, refused at the ceiling — by header first, then by count.

    The header check is the cheap refusal (nothing has been read); the counted read is
    the honest one, since a Content-Length is a claim and a chunked request carries none.
    Refusing mid-stream leaves the connection to the server to close, which is what a 413
    costs everywhere.
    """
    declared = request.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > MAX_ATTACHMENT_BYTES:
        raise _TOO_LARGE

    received = bytearray()
    async for chunk in request.stream():
        received.extend(chunk)
        if len(received) > MAX_ATTACHMENT_BYTES:
            raise _TOO_LARGE
    return bytes(received)


@router.put("/requests/{request_id}/attachment", status_code=status.HTTP_201_CREATED)
async def put_attachment(
    request_id: str,
    request: Request,
    user: CanEditRequests,
    db: Db,
    filename: str | None = None,
) -> AttachmentOut:
    """Attach the budget file, replacing the current one; the replaced row survives.

    Always 201: even a replacement creates a new attachment in the history, and the
    previous one is superseded rather than gone.
    """
    data = await _capped_body(request)
    attachment = await service.store_attachment(
        db,
        request_id,
        user,
        APP_KEY,
        data=data,
        content_type=request.headers.get("content-type"),
        filename=filename,
    )
    return AttachmentOut.of(attachment)


@router.get("/requests/{request_id}/attachment")
async def read_attachment(request_id: str, user: CanEditRequests, db: Db) -> AttachmentDownloadOut:
    """The current attachment's metadata plus a short-lived signed download URL."""
    link = await service.attachment_download_url(db, request_id, user, APP_KEY)
    return AttachmentDownloadOut.of(
        link.attachment, download_url=link.url, expires_in_minutes=link.expires_in_minutes
    )
