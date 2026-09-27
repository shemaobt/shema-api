"""Leaving the network without an account — the exit link, minted, opened and spent here.

The client's answer on 22/sep to *how does somebody outside the platform ask to be removed when
they cannot log in* was *"ainda não existe caminho"*. This is the path. Every send to the
network (BE-09, OBT-398) carries a link — *para sair da rede, abra este link* — and the person
who opens it sees a confirmation page in the console (``/leave/{token}``) that says nothing
about them; confirming erases them exactly as the Resource Circle's own removal does.

**This is the only file where a raw exit token exists.** :func:`issue_exit_link` mints it with
``app/services/common/tokens/`` and hands back the only copy, for the one message it goes in;
the table's owner, ``_directory``, is given the digest and nothing else, and so is every lookup.

**Each send mints its own link, and none is revoked.** The hash is what makes that necessary —
a raw value that cannot be read back cannot be sent twice — and it is also the reading of the
issue's *rotated, never reused*: every message carries a fresh token and no token is ever sent
again or revived. What is *not* done is revoking the previous link on each send, because that
strands the person holding an older message; a link that leaks can only remove somebody, which
is the safe direction. Each link lives ``shema_intercessor_exit_link_days``.

**Opening changes nothing; confirming erases.** A link previewer — WhatsApp's, a mail
scanner's — fetches every URL it is given, so :func:`open_exit_link` only reads, and the act is
the confirmation's ``POST``.

**What is left behind is a log line with no person in it** — the operation and the id of the
row that no longer exists, like ``remove_intercessor.py``'s, and never a name, a contact or a
token. There is no actor to name: the person is the actor, and they have no account.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Final

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.services.common import tokens
from app.services.shema._directory import (
    check_exit_link,
    leave_through_exit_link,
    store_exit_link,
)

logger = logging.getLogger(__name__)

#: How long an exit link lives — the purpose's key in the block of token lifetimes in
#: ``app/core/config.py``, where the argument for the number is. Read once.
EXIT_LINK_DAYS: Final = get_settings().shema_intercessor_exit_link_days


async def issue_exit_link(
    db: AsyncSession,
    intercessor_id: str,
    *,
    now: datetime | None = None,
    commit: bool = True,
) -> str:
    """Mint one exit link for one send to one person, and hand back the only copy of the token.

    **BE-09 is the caller**, once per person per send; nothing in this issue sends anything, so
    this is the entry point it will use rather than code with a caller today. ``commit=False``
    lets a whole send be minted in one transaction; whoever passes it owns the commit.
    """
    moment = now or datetime.now(UTC)
    minted = tokens.mint()
    await store_exit_link(
        db,
        intercessor_id,
        token_hash=minted.digest,
        expires_at=tokens.expiry(moment, days=EXIT_LINK_DAYS),
        now=moment,
        commit=commit,
    )
    return minted.raw


def exit_url(base_url: str | None, raw_token: str) -> str:
    """Where the person is sent — the console's own exit page, carrying the token.

    ``app_url`` is the seeded row's, read by the caller, and the fallback is the leader link's:
    a local dev server, so an unseeded registry still hands back something clickable.
    """
    root = (base_url or "http://localhost:5173").rstrip("/")
    return f"{root}/leave/{raw_token}"


async def open_exit_link(db: AsyncSession, raw_token: str) -> None:
    """Whether this link still lets somebody leave — the confirmation page's read, and no act."""
    await check_exit_link(db, tokens.digest(raw_token), now=datetime.now(UTC))


async def leave_network(db: AsyncSession, raw_token: str) -> None:
    """Erase the person this link was minted for — their row, consents and every link.

    Every link that opens nothing gets one answer, from ``_directory``: a second confirmation, an
    expired link and an unknown one read the same, so a forwarded link tells nobody whether the
    person is still in the network.
    """
    intercessor_id = await leave_through_exit_link(
        db, tokens.digest(raw_token), now=datetime.now(UTC)
    )
    logger.info(
        "shema intercessor left through an exit link",
        extra={
            "shema_operation": "leave_intercessor",
            "shema_intercessor_id": intercessor_id,
        },
    )
