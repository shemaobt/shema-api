"""The Prayer Pulse — the wall, rendered into the file that goes to the intercessor network.

**The highest-risk operation in the module, so it has no path of its own to get wrong.** It
assembles the most sensitive data into a file built to be forwarded, and the issue's rule is one
code path, reusing the filter every read uses, never assembling from rows. So the Pulse **is**
:func:`~app.services.shema.list_prayer_requests.list_prayer_requests` handed to
:func:`~app.models.shema_prayer.render_prayer_pulse`: whatever the wall would not show, the file
cannot carry, and the sensitive-country reduction has already happened in the entries before the
first character of the file is written.

**Generating is not sending** (the issue's *out of scope*). Nothing is written: not the
intercessors' ``last_sent_at``, not an exit link — both belong to the send, which happens however
the organisation sends today. What is kept is a log line: who generated a Pulse, when, over which
scope and with how many requests — the after-the-fact question *was my request in that file* is
answerable from it — and never a word of what the file said.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import NamedTuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.models.shema_prayer import PulseLanguage, pulse_filename, render_prayer_pulse
from app.services.shema._scope import RegionScope
from app.services.shema.list_prayer_requests import list_prayer_requests

logger = logging.getLogger(__name__)


class PrayerPulse(NamedTuple):
    """The file and its name, and how many requests went into it."""

    filename: str
    text: str
    requests: int


async def generate_prayer_pulse(
    db: AsyncSession,
    scope: RegionScope,
    *,
    user: User,
    language: PulseLanguage,
    day: date,
) -> PrayerPulse:
    """The Pulse for ``scope`` on ``day``, in ``language`` — the wall, rendered.

    ``day`` is injected for the reason every read here injects it: the file is a pure function of
    the data and a day the caller names.
    """
    entries = await list_prayer_requests(db, scope)
    logger.info(
        "shema prayer pulse generated",
        extra={
            "shema_operation": "generate_prayer_pulse",
            "shema_user_id": user.id,
            "shema_scope_global": scope.global_,
            "shema_scope_regions": sorted(scope.regions),
            "shema_requests": len(entries),
        },
    )
    return PrayerPulse(
        filename=pulse_filename(day, language),
        text=render_prayer_pulse(entries, day=day, language=language),
        requests=len(entries),
    )
