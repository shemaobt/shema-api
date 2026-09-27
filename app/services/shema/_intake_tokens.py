"""The leader link's whole guard — minted here, checked here, and nowhere else.

**The token is the guard, so the guard is a service function.** ``docs/shema.md`` §6.6 states
it and gives the reason this file takes seriously: a router condition holds for the route it
is written on, and a service function holds for every caller of it, including the ones nobody
has written yet. It is the same argument the consent gate makes, at the one seam in this module
that has no ``Authorization`` header to fall back on.

**What the link is, in one line each — and each is a column or a check here, never a comment.**

* **Project-scoped.** ``shema_intake_links.project_id`` is ``NOT NULL`` and the request shape
  requires it (``app/models/shema_forms.py``), against FE-44 §9.9's own optional spelling. A
  link with no project is a link to every project, and *project-scoped* is the first word of
  the line this credential is judged by.
* **Expiring.** Not *"it has an expiry column"*: it has a default, so a coordinator who states
  nothing still mints something that dies, and a ceiling, so one who states something cannot
  mint something that does not.
* **Revocable.** ``revoked_at``, checked here, ahead of the expiry — a link taken back stays
  taken back after its clock runs out, which is the precedent
  ``app/services/resource_request_access/_invite_status.py`` records in the same words: *the
  door a person walked through must not later present itself as merely expired*.
* **Write-mostly.** Not this file's to enforce — it is what the route serves, and
  ``app/models/shema_forms.py``'s ``IntakeForm`` is where it is decided and
  ``tests/test_shema/test_intake_link.py`` is where it is proved.

**Multi-use until it expires or is revoked**, and ``used_at`` records the **first** answer
rather than spending the link, which is the column BE-02 wrote and the docstring it wrote it
with. Single use reads as tighter and is not: the Pulse is monthly, the leader is the person
who is offline, and a link that has to be re-minted and re-sent through WhatsApp before every
cycle is a link that gets replaced by a coordinator typing the answers in themselves. What
bounds the abuse instead is the expiry, the revocation and the rate limit on the route —
three things that hold whether or not anyone remembers to re-send anything.

**What is every link's and what is this link's.** Since BE-20 (OBT-525) the token, its digest
and the order its states are read in belong to ``app/services/common/tokens/``, shared with
every other link this server issues. What stays in this file is what only the leader link
decides: the default life and the ceiling, the calendar-day expiry, the guard that composes
the checks, and the URL.

**The refusal names the state.** A hash that matches nothing, an expired link and a revoked one
are three different messages, all 404. Telling them apart is not an oracle: the caller already
holds a 256-bit token, so there is nothing to guess and nothing to enumerate — what the
distinction buys is a leader who learns that their link died rather than that the product is
broken, and a coordinator who can be asked for a new one.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import NotFoundError, ValidationError
from app.db.models.shema_form import ShemaIntakeLink
from app.services.common import tokens
from app.utils.stored_time import as_utc

#: How long a link lives when the coordinator states nothing.
#:
#: Longer than one Pulse cycle and shorter than two. A month exactly would expire on the week
#: the next form is due, which is when a link is least likely to be re-minted and most likely
#: to be worked around. A ceiling configured below it shortens it rather than refusing the
#: coordinator who stated nothing.
DEFAULT_LINK_DAYS: Final = 45

#: The longest life a coordinator may ask for — ``shema_intake_link_max_days``, the leader
#: link's key in the block of token ceilings in ``app/core/config.py``, where the argument for
#: the number is. Read once, so the guard and whoever reads the ceiling see one value.
MAX_LINK_DAYS: Final = get_settings().shema_intake_link_max_days


def mint_token() -> tokens.Minted:
    """A fresh leader-link token and its digest — ``tokens.mint``, under this link's name.

    The raw value leaves once and is never stored, as every link token's does, and this one
    has the strongest case for it: its holder has no account, so a database dump is the only
    place it could ever be read from.
    """
    return tokens.mint()


def expiry_from(requested: date | None, *, today: date) -> datetime:
    """When a link asked to live until ``requested`` actually dies.

    The stated day is a **calendar day the link still works on**, so the moment is midnight
    UTC at the end of it. A day is what FE-44 §9.0 puts on this wire and it is what a
    coordinator can reason about; turning it into an instant is the server's job and is done
    once, here, rather than by each caller picking an hour.

    A day in the past is refused rather than clamped: minting a dead link silently is the kind
    of success that is discovered by a leader in a village.
    """
    if requested is None:
        requested = today + timedelta(days=min(DEFAULT_LINK_DAYS, MAX_LINK_DAYS))
    if requested < today:
        raise ValidationError(f"expiresAt: {requested.isoformat()} has already passed")
    if (requested - today).days > MAX_LINK_DAYS:
        raise ValidationError(
            f"expiresAt: {requested.isoformat()} is more than {MAX_LINK_DAYS} days out, and a "
            "leader link may not live that long"
        )
    return datetime.combine(requested + timedelta(days=1), time.min, tzinfo=UTC)


def expires_on(link: ShemaIntakeLink) -> date:
    """The last day the link works — :func:`expiry_from` read back the way it was stated."""
    return (as_utc(link.expires_at) - timedelta(days=1)).date()


def link_status(link: ShemaIntakeLink, *, now: datetime | None = None) -> tokens.TokenStatus:
    """One reading of a link's state, shared by the listing, the creation and the guard.

    ``tokens.status``'s order — revoked, expired, used, pending — with the clock read here
    when the caller brings none.
    """
    return tokens.status(link, now or datetime.now(UTC))


async def verify_intake_token(db: AsyncSession, raw_token: str) -> ShemaIntakeLink:
    """The link this token opens, or a refusal — the module's one unauthenticated guard.

    Composes all three checks, which is the reason it is one function: a caller that could ask
    *which link is this* without asking *is it still good* is a caller that eventually will,
    and the check it skips will be the revocation.

    The lookup is by hash, so the raw token is never compared against a stored value and never
    appears in a query the database logs.
    """
    link = (
        await db.execute(
            select(ShemaIntakeLink).where(ShemaIntakeLink.token_hash == tokens.digest(raw_token))
        )
    ).scalar_one_or_none()
    if link is None:
        raise NotFoundError("This link is not one this server issued.")

    status = link_status(link)
    if status == "revoked":
        raise NotFoundError("This link has been revoked. Ask your coordinator for a new one.")
    if status == "expired":
        raise NotFoundError("This link has expired. Ask your coordinator for a new one.")
    return link


def intake_url(base_url: str | None, raw_token: str) -> str:
    """Where the leader is sent — the console's own intake page, carrying the token.

    ``app_url`` is the seeded row's, read through ``authorization_service.get_app_by_key`` by
    the caller rather than typed here. ``scripts/seed_apps_roles.py``'s docstring records that
    this column is not decoration, and the fallback is the sibling's: a local dev server, so a
    machine with an unseeded registry still hands back something a developer can click.
    """
    root = (base_url or "http://localhost:5173").rstrip("/")
    return f"{root}/intake/{raw_token}"
