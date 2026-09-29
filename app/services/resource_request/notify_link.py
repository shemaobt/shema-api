"""What a request link's holder is told, and how — BE-26 (OBT-537).

**By e-mail, and only by e-mail.** The holder has no account (GATE-04 D4), so there is no
in-app notice to write and no bell to ring: the issue's own sentence, *"não há in-app"*. Three
letters, each to the link's address:

* **the link itself** (``link_letter``), when the Admin issues it — the URL and the code, which
  this is the only place they travel after the Admin's own answer;
* **the receipt** (``receipt_letter``), when the holder submits — GATE-03's *"data e hora"*,
  here as the date the request arrived;
* **the decision** (``decision_letter``), from ``notify_decision``, on all four decisions, as a
  team with an account is told.

The later two cannot carry the link again: only its digest is stored. They say to open the link
the holder already has, which is also the one the first letter asked them to keep.
"""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import App
from app.db.models.resource_request import RRRequest, RRRequestLink
from app.services.notifications.get_rr_app_id import get_rr_app_id
from app.services.resource_request._notices import Letter, letter, product_name, request_name

RECEIPT_TITLE = "Your resource request was received"
RECEIPT_SENTENCE = "was received and is waiting for the Resource Circle."
LINK_TITLE = "Your request link to the Resource Circle"


async def link_letter(
    db: AsyncSession, link: RRRequestLink, token: str, code: str
) -> Letter | None:
    """The letter that delivers a link and its code, or ``None`` with nowhere to point it.

    The URL is the form's ``app_url`` from the app registry plus ``/link/{token}``. An
    installation with no ``app_url`` sends nothing rather than a letter with no link in it —
    the Admin's answer still carries both secrets, and handing them over is then theirs.
    """
    app_id = await get_rr_app_id(db)
    app = await db.get(App, app_id)
    if app is None or not app.app_url:
        return None
    return letter(
        to=link.email,
        subject=LINK_TITLE,
        template="rr_link.html.jinja",
        app_name=app.name,
        url=f"{app.app_url.rstrip('/')}/link/{token}",
        code=code,
        project_hint=link.project_hint,
        expires=_day(link.expires_at),
    )


async def receipt_letter(db: AsyncSession, request: RRRequest, link: RRRequestLink) -> Letter:
    return await _to_holder(db, link, request, RECEIPT_TITLE, RECEIPT_SENTENCE)


async def decision_letter(
    db: AsyncSession,
    request: RRRequest,
    link: RRRequestLink,
    title: str,
    sentence: str,
    team_note: str | None,
) -> Letter:
    return await _to_holder(db, link, request, title, sentence, team_note)


async def _to_holder(
    db: AsyncSession,
    link: RRRequestLink,
    request: RRRequest,
    title: str,
    sentence: str,
    team_note: str | None = None,
) -> Letter:
    return letter(
        to=link.email,
        subject=title,
        template="rr_decision.html.jinja",
        app_name=await product_name(db, await get_rr_app_id(db)),
        greeting=link.email,
        request_name=request_name(request),
        sentence=sentence,
        team_note=team_note,
        link_holder=True,
    )


def _day(moment: datetime) -> str:
    return moment.strftime("%d/%m/%Y")
