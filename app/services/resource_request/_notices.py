"""What a notice is made of, who receives one, and when each of its two halves leaves.

GATE-03 D5/D6 asked for **both channels** — in-app and e-mail — on the decision and on the
arrival. The two halves cannot leave at the same moment, and the whole shape of this file
is that sentence:

* the **in-app** half is a row in ``notifications``, written inside the caller's own
  transaction (``create_notification(..., commit=False)``), so a decision that landed
  always carries its notice and one that rolled back leaves none;
* the **e-mail** half is a :class:`Letter` handed back to the caller, and it is posted
  **after** that commit — never before it, and never inside it.

That ordering is the requirement and not a preference. The design document says so in §6:
the existing ``request_password_reset`` sent synchronously before its commit, with
``raise_for_status``, and copied as it stood a provider outage would have made the mesa's
decision fail and revert. BE-12 (OBT-473) already fixed that call and gave ``send_email``
its best-effort contract; this file is what keeps the fix from being undone one caller
later.

**No detail table.** ``notification_meaning_map_details`` is the only detail table there
is, and it is one application's. A request's notice names its request in words instead;
FE-28's screen is a list of the team's own requests, not a deep link, so a
``notification_resource_request_details`` would be a table with no reader — and the day
one has a reader it is a migration, which is a different issue's to own.

**The copy is English, and that is a pendency rather than a decision.** Every notification
title and every e-mail template in this repository is English, including the password
reset these same people receive; the bilingual rewrite of the product's client-facing copy
is one of GATE-03's own open ends. Writing invented Portuguese here would put unapproved
client-facing wording in front of a field team on the strength of nobody's decision.
"""

from __future__ import annotations

import logging
from typing import NamedTuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import App, User
from app.db.models.resource_request import RRRequest
from app.services import authorization_service
from app.services.common.email import render_email, send_email
from app.services.resource_request.capabilities import CAPABILITY_ROLES

logger = logging.getLogger(__name__)

#: The capability whose holders watch the board. Recipients are read off the capability
#: map rather than off role literals for two reasons that agree: ``manage_funds`` is the
#: Painel's entry gate, so its holders are exactly the people an arriving request is for,
#: and GATE-03's *"o Gestor entra como destinatário e nada mais"* costs no new capability
#: this way. ``_scope.py`` stays the only place in the module that reads a role by name,
#: and BE-16's Líder de Base — who endorses and does not watch the board — does not
#: silently inherit the mesa's inbox.
BOARD_CAPABILITY = "manage_funds"


class Letter(NamedTuple):
    """One e-mail, rendered and addressed, waiting for its caller's commit.

    Rendered before the commit rather than after it, and that is deliberate: the values it
    quotes — the decision, the note, the request's name — are the ones the transaction is
    about to make true, and reading them back afterwards would mean holding rows open past
    the commit that expires them.
    """

    to: str
    subject: str
    html: str
    from_name: str


async def post(letters: list[Letter]) -> int:
    """Hand every letter to the provider; answer how many were accepted.

    Best-effort by construction, and the DoD's *"falha de e-mail não reverte a decisão"* is
    what it buys: ``send_email`` already swallows a provider failure and answers ``False``,
    and the ``except`` here covers the rest of the path — a template that fails to render,
    a provider module that raises on import. Called after the caller has committed, so
    there is no transaction left for an exception to take down; what an exception escaping
    here would cost is a 500 on a save that already succeeded, which reads to the mesa as
    a decision that did not land.
    """
    accepted = 0
    for letter in letters:
        try:
            if await send_email(
                to=letter.to,
                subject=letter.subject,
                html=letter.html,
                from_name=letter.from_name,
            ):
                accepted += 1
        except Exception:
            logger.exception("resource-request notice not sent to %s", letter.to)
    return accepted


async def app_name(db: AsyncSession, app_id: str) -> str:
    """The registry row's own name, for the e-mail chrome.

    Read rather than written down: ``scripts/seed_apps_roles.py`` owns that string, and a
    copy of it here would be a second source of the product's name in the one place a
    person actually reads it.
    """
    app = await db.get(App, app_id)
    return app.name if app is not None else "Shema"


async def board_watchers(
    db: AsyncSession, app_key: str, *, exclude: str | None = None
) -> list[User]:
    """Mesa and Gestores — whoever holds :data:`BOARD_CAPABILITY` in this app.

    ``exclude`` drops one account, which is how a person is not told about their own act.
    """
    holders = await authorization_service.list_role_holders(
        db, app_key, CAPABILITY_ROLES[BOARD_CAPABILITY]
    )
    return [user for user in holders if user.id != exclude]


#: What a notice calls a request that has no A0 name yet. A generic reference and not an
#: invented title: naming an untitled request *"Untitled"* would fabricate a field's value.
FALLBACK_NAME = "Your resource request"


def request_name(request: RRRequest) -> str:
    """How a notice refers to a request.

    ``reg_name`` is A0 and is what the mesa and the team both call it — but it defaults to
    the empty string on the spine, and a team that submitted before typing it would get a
    subject line with a hole in it.
    """
    return request.reg_name.strip() or FALLBACK_NAME


def letter(to: str, subject: str, template: str, app_name: str, **context: object) -> Letter:
    """Render one template into an addressed :class:`Letter`.

    ``app_name`` is both the template's chrome and the sender's display name, which is why
    it is a parameter of its own rather than one more key in ``context``.
    """
    return Letter(
        to=to,
        subject=subject,
        html=render_email(template, app_name=app_name, **context),
        from_name=app_name,
    )
