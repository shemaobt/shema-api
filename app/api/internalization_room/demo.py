"""The page a store reviewer types the tablet's claim code into (ADR 0064).

Served only while a demo team is configured, with no login: the reviewer is alone with the
app. The code is spent on the demo team by the same spend the Desk's claim makes, and every
refusal is one answer, because an anonymous caller who could tell a spent code from an unknown
one would learn which codes exist (ADR 0057).
"""

from html import escape

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.core.rate_limit import limiter
from app.services.device.claim_device import InvalidClaimCodeError, claim_device
from app.services.device.demo_team import the_demo_team

router = APIRouter()

#: One bucket for every caller, per instance: an address is whatever the caller writes in
#: ``X-Forwarded-For`` (ADR 0064).
DEMO_RATE_LIMIT_PER_MINUTE = 10
LINKED = "Linked. Go back to the tablet."

_PAGE = """<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Demo</title></head>
<body>
<p>{said}</p>
<form method="post">
<label for="code">Type the code the tablet shows</label>
<input id="code" name="code" autocomplete="off" autocapitalize="characters" required>
<button type="submit">Link</button>
</form>
</body>
</html>
"""


def _page(said: str = "", *, status_code: int = 200) -> HTMLResponse:
    return HTMLResponse(_PAGE.format(said=escape(said)), status_code=status_code)


def _the_whole_page() -> str:
    return "demo"


def _as_shown(typed: str) -> str:
    """The code as the tablet shows it, whatever the reviewer's keyboard put between its halves."""
    kept = "".join(character for character in typed if character.isalnum()).upper()
    return f"{kept[:3]}-{kept[3:]}" if len(kept) == 7 else kept


async def _demo_team_or_404(db: AsyncSession) -> str:
    team_id = await the_demo_team(db)
    if team_id is None:
        raise NotFoundError("Not Found")
    return team_id


@router.get("/demo", response_class=HTMLResponse)
async def the_demo_page(db: AsyncSession = Depends(get_db)) -> HTMLResponse:
    await _demo_team_or_404(db)
    return _page()


@router.post("/demo", response_class=HTMLResponse)
@limiter.limit(f"{DEMO_RATE_LIMIT_PER_MINUTE}/minute", key_func=_the_whole_page)
async def spend_on_the_demo_team(
    request: Request,
    code: str = Form(max_length=32),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    team_id = await _demo_team_or_404(db)
    try:
        await claim_device(db, code=_as_shown(code), project_id=team_id)
    except InvalidClaimCodeError:
        return _page(InvalidClaimCodeError.MESSAGE, status_code=400)
    return _page(LINKED)
