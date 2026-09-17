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

**The refusal names the state.** A hash that matches nothing, an expired link and a revoked one
are three different messages, all 404. Telling them apart is not an oracle: the caller already
holds a 256-bit token, so there is nothing to guess and nothing to enumerate — what the
distinction buys is a leader who learns that their link died rather than that the product is
broken, and a coordinator who can be asked for a new one.
"""

from __future__ import annotations

import secrets
from datetime import UTC, date, datetime, time, timedelta
from typing import Final

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.db.models.shema_form import ShemaIntakeLink
from app.services.auth.hash_refresh_token import hash_refresh_token
from app.utils.stored_time import as_utc

#: How long a link lives when the coordinator states nothing.
#:
#: Longer than one Pulse cycle and shorter than two. A month exactly would expire on the week
#: the next form is due, which is when a link is least likely to be re-minted and most likely
#: to be worked around.
DEFAULT_LINK_DAYS: Final = 45

#: The longest life a coordinator may ask for. Three cycles, and the ceiling exists because
#: *expiring* is a property of the credential rather than of the coordinator's intention: a
#: link that can be minted for a year is a link that will be.
MAX_LINK_DAYS: Final = 90

#: 256 bits, URL-safe. Shorter than the repository's ``token_hex(32)`` siblings for the same
#: entropy, which matters for exactly one reason and it is not aesthetics: this token travels
#: as a link in a chat message to a phone, and a token that wraps is a token somebody retypes.
_TOKEN_BYTES: Final = 32


def mint_token() -> tuple[str, str]:
    """A fresh token and its SHA-256 — the raw value leaves once and is never stored.

    Every token in this repository is kept this way (``refresh_tokens``,
    ``password_reset_tokens``, ``access_invites``) and this one has the strongest case for it:
    it is the one credential whose holder has no account, so a database dump is the only place
    it could ever be read from.
    """
    raw = secrets.token_urlsafe(_TOKEN_BYTES)
    return raw, hash_refresh_token(raw)


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
        requested = today + timedelta(days=DEFAULT_LINK_DAYS)
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


def link_status(link: ShemaIntakeLink, *, now: datetime | None = None) -> str:
    """One reading of a link's state, shared by the listing, the creation and the guard.

    Precedence is the sibling's and is deliberate: revoked beats expired and expired beats
    used, so a link somebody took back never reads as one that merely ran out.
    """
    moment = now or datetime.now(UTC)
    if link.revoked_at is not None:
        return "revoked"
    if as_utc(link.expires_at) <= moment:
        return "expired"
    if link.used_at is not None:
        return "used"
    return "pending"


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
            select(ShemaIntakeLink).where(
                ShemaIntakeLink.token_hash == hash_refresh_token(raw_token)
            )
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
