"""Media, materials and notes against an audience — ``docs/shema.md`` §6.4's third row.

``can_share_media`` composes and **the most restrictive wins**: an authorized item reaches
``coordenacao``; the same item on a sensitive project never reaches ``publico`` (FE-44 §8.3).
Two rules meeting in one predicate is the reason this is a file and not a line in a query —
the composition is where a per-surface implementation gets it right for one audience and
wrong for the other.

**The default is not authorized, and the column is written so it can stay that way.**
``authorization_granted`` is nullable and only an explicit ``True`` counts: an item with no
recorded decision behaves exactly as a refused one. ``docs/shema.md`` §7.4 files this beside
its two absences as the third of the same shape — a ``False``/NULL default rather than an
absent one, but it fails the same way if it is inverted for convenience, and the convenient
inversion here publishes every photo nobody has looked at yet.

**This file is the only reader of the three authorization columns** in
``app/services/shema/`` and ``app/api/shema/``, and
``tests/test_shema/test_privacy_owners.py`` fails on a second one. The flag it composes with
is read through ``_redaction.is_withheld`` rather than off the column, which is the same
glob saying that the sensitive-country column has one reader too.

**What is deliberately not here.** Signed or expiring URLs. FE-44 §3.1 records that this
repository's existing upload returns a **public bucket URL**, and a per-item authorization
that ends in a public URL enforces nothing — so the predicate is necessary and not
sufficient. The storage half needs an endpoint that applies this predicate per request, or a
signed URL with an expiry, and it belongs to the issue that first serves media (BE-09/BE-14).
Building the adapter here, with no caller and no bucket decision, would freeze a guess; the
PR records it as the one part of §6.4's third row that is named rather than built.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from app.db.models.shema import ShemaProject
from app.models.shema_privacy import ShemaAudience
from app.models.shema_record import ShemaMediaAuthorization
from app.services.shema._redaction import is_withheld


class Authorizable(Protocol):
    """Anything carrying a per-item sharing decision.

    A protocol and not a base class: ``ShemaMediaItem`` and ``ShemaMaterial`` are two tables
    with two lifecycles that happen to record the same decision, and giving them a common
    parent to satisfy a type checker would put a mapped inheritance in the schema to express
    a fact about a predicate.
    """

    authorization_granted: bool | None
    #: The evidence beside the decision — who decided and when, as a snapshot. Declared here
    #: rather than read with ``getattr`` so the type checker sees what this file reads, which
    #: is also what the column glob sees.
    authorized_by: str | None
    authorized_at: datetime | None


def is_authorized(item: Authorizable) -> bool:
    """Whether a decision was recorded **and** it was yes.

    ``is True`` and not truthiness, because the three states are *granted*, *refused* and
    *nobody has looked*, and only the first one counts. The distinction is invisible in a
    boolean context and is the whole of the rule.
    """
    return item.authorization_granted is True


def can_share_media(project: ShemaProject, item: Authorizable, audience: ShemaAudience) -> bool:
    """The composed answer: authorization, then audience, then the sensitive-country flag.

    Read it in the order it is written. An unauthorized item reaches nobody, whatever the
    project. An authorized item reaches ``coordenacao``. The same authorized item on a project
    whose place is withheld never reaches ``publico`` — because a photograph of a team is not
    covered by withholding the name of the country it was taken in, and ``publico`` is the
    audience the product cannot take the file back from.

    Every sharing surface calls this and none re-derives it: the export, the prayer wall, the
    ETEN report, the Pulse and the notification bodies each have one line to write here, and
    a surface that composes the two rules itself will compose them slightly differently.
    """
    if not is_authorized(item):
        return False
    return not (audience == ShemaAudience.PUBLICO and is_withheld(project))


def can_export_notes(audience: ShemaAudience) -> bool:
    """Whether free-text notes may go to ``audience`` — FE-44 §8.4's ``canExportNotes``.

    ``coordenacao`` yes, ``publico`` never, **and nothing recorded on the project changes
    that**: notes carry the most sensitive human context in the record, written by someone
    who was not thinking about a file being forwarded. It takes no project argument for that
    reason — a signature that accepted one would invite a per-record exception, which is the
    shape of the decision this answer refuses to have.

    It lives beside the media rule rather than in a fourth file because it is the same
    question — *what may this audience receive* — and the audience vocabulary has one owner
    (``app/models/shema_privacy.py``). A file per predicate would be three files agreeing
    about an enum.
    """
    return audience == ShemaAudience.COORDENACAO


def recorded_decision(item: Authorizable) -> ShemaMediaAuthorization | None:
    """The decision on an item, as the record's shape carries it — or ``None``, undecided.

    **The shape is built here because the columns are read here.** ``MediaAuthorization`` is a
    response shape and ``app/models/`` is deliberately outside the glob that watches these
    three columns (``tests/test_shema/test_privacy_owners.py``'s own note says why: a request
    model legitimately carries the names a client writes). So a model that read the columns
    itself would be a second reader the glob *cannot* see, which is worse than one it can. The
    owner assembles and hands over; the shape declares and knows nothing.

    ``None`` for a row nobody has decided, rather than ``{granted: false}``: FE-44 §5.2 makes
    *undecided* and *refused* behave identically and keeps them distinguishable, and a shape
    asserting a ``false`` nobody recorded is the server inventing a refusal.

    It is a read of the decision and **not** permission to share it — that is
    :func:`can_share_media`, which takes the project and the audience this one deliberately
    does not.
    """
    if item.authorization_granted is None:
        return None
    return ShemaMediaAuthorization(
        granted=is_authorized(item),
        by=item.authorized_by or "",
        at=item.authorized_at,
    )
