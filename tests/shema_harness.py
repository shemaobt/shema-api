"""What the Shemá module's cases lend one another, and none of them owns.

Every audit that reads the built application's route table asks a route one question — does
this dependency appear anywhere in its resolved chain — whether it is the guard
(``test_shema/test_access.py``), the no-store header (``test_cache_control.py``), the Admin's
guard (``test_admin_gate.py``) or the caller's reader (``test_privacy_owners.py``). The walker
that answers it is written once, beside the module's deliberate holes: the guard's audit
exempts them, and the no-store audit calls them with no bearer token.

The prayer cases' account and need builders are the export's too (``test_transfer.py``): the
wall, the Prayer Pulse and the export read one assembly of what a team authorized
(``authorized_requests``), so their cases build the same rows.

Builders and constants only: a fixture cannot travel by import, so each module keeps its own
fixtures and calls what is here.
"""

from __future__ import annotations

from app.db.models.shema import ShemaProject
from app.db.models.shema_enums import ShemaNeedUrgency, ShemaRegionKey
from app.db.models.shema_need import ShemaNeed
from tests.test_shema.conftest import PREFIX, auth_header, make_scoped_user

# --- the route audits -----------------------------------------------------------------

#: Paths under ``/api/shema`` that are allowed to carry no authentication.
#:
#: **Two paths and two methods each, which are the module's whole hole.** BE-04 expected this
#: list to stay empty until BE-12 and BE-12 added exactly the entry it predicted: ``GET`` and
#: ``POST /api/shema/intake/{token}``, by FE-44 §9.0 and ``docs/shema.md`` §6.6, where the token
#: *is* the guard and the guard is a service function (``verify_intake_token``) so the rule
#: holds for any future caller of it rather than for the two routes it was written under.
#:
#: **The second is OBT-531's exit link**, ``GET`` and ``POST
#: /api/shema/intercessors/leave/{token}``: a person in the prayer network has no account, and
#: this is how they leave. Same shape — the token is the guard and ``leave_intercessor.py`` is
#: the guard — and ``tests/test_shema/test_intercessor_exit.py`` is where each method is held to
#: what it may do: the ``GET`` changes nothing, the ``POST`` erases.
#:
#: A route that arrives without a line added here fails
#: ``test_access.py::test_every_shema_route_is_guarded``, which is what makes forgetting a guard
#: a red build rather than an open endpoint. Keyed by path because that is what the audit
#: compares; the two methods on it are both exempt and ``tests/test_shema/test_intake_link.py``
#: is where each is held to what it may actually serve — the guard being absent is the premise
#: of that file, not a gap in the audit.
UNAUTHENTICATED_PATHS: frozenset[str] = frozenset(
    {f"{PREFIX}/intake/{{token}}", f"{PREFIX}/intercessors/leave/{{token}}"}
)


def reaches(dependant, target, depth: int = 0) -> bool:
    """Whether ``target`` appears anywhere in ``dependant``'s tree.

    Depth-limited because FastAPI's dependency graph is a tree of arbitrary depth and a
    cycle would hang the suite rather than fail it.
    """
    if depth > 8:
        return False
    for sub in dependant.dependencies:
        if sub.call is target or reaches(sub, target, depth + 1):
            return True
    return False


# --- the prayer network's rows --------------------------------------------------------

#: The region an invented place derives to (``FALLBACK_REGION``). A record written through the
#: API is re-derived on every save, so the accounts that write are scoped here.
HOME = ShemaRegionKey.OTHER


async def need(
    db_session, project: ShemaProject, description: str, *, shared: bool, answered: bool = False
) -> ShemaNeed:
    """One need on ``project``, shared with the prayer network or kept, answered or not."""
    row = ShemaNeed(
        project_id=project.id,
        category="financial",
        urgency=ShemaNeedUrgency.LOW,
        description=description,
        prayer_shared=shared,
        prayer_answered=answered,
    )
    db_session.add(row)
    await db_session.commit()
    return row


async def person(db_session, shema_app, role_key: str, regions=(HOME,)):
    """The headers of a non-admin account holding ``role_key``, scoped to ``regions``."""
    user = await make_scoped_user(
        db_session,
        shema_app,
        email=f"{role_key.lower()}-{'-'.join(regions)}@oracao.test",
        role_key=role_key,
        regions=list(regions),
    )
    return await auth_header(db_session, user)
