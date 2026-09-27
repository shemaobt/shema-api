"""Concession of the privileged roles — the client's answer of 28/08, as code.

Two ways in ("os dois"): naming a user that exists, and a link for an e-mail
that may not have an account yet. One asymmetric rule for both: **Admin and
Gestor concede, only Admin revokes** — and the asymmetry is the answer, not an
oversight.

This package is a gate built *beside* ``assert_can_manage_roles``, not a change
to it. That predicate is shared by eight applications and admits exactly
"platform admin or the app's ``admin`` role": it is symmetric (one yes/no for
grant and revoke alike), and this app seeded no ``admin`` role when the gate
was written. Expressing "Gestor grants but cannot revoke" there would either
complicate every other app's path or invent a role. Since OBT-523 the app does
seed one — OBT-522's Admin, one role for both apps — and nobody holds it until
OBT-543 grants it; whoever does passes that shared predicate for this app, which
is why these two doors refuse to name an ``admin`` for anyone but the
installation admin (``_rules.assert_role_grantable``). Domain policy for the
resource-request-form lives with its domain instead; the shared file stays
untouched and the other eight apps keep the behaviour they were tested with.

"Admin" throughout means the platform admin (``User.is_platform_admin``) — the
only Admin this gate knows until OBT-543, and the account that already bypasses
its guards.

The grant rules shared by both doors: ``mesa`` and ``gestor`` are mutually
exclusive (holding one blocks receiving the other until it is revoked);
``equipe`` is the floor and accumulates freely; and granting or revoking your
own access is refused on both verbs.
"""

from app.services.resource_request_access.accept_invite import accept_invite
from app.services.resource_request_access.create_invite import create_invite
from app.services.resource_request_access.describe_invite import describe_invite
from app.services.resource_request_access.grant_access import grant_access
from app.services.resource_request_access.list_access import list_access
from app.services.resource_request_access.revoke_access import revoke_access
from app.services.resource_request_access.revoke_invite import revoke_invite

__all__ = [
    "accept_invite",
    "create_invite",
    "describe_invite",
    "grant_access",
    "list_access",
    "revoke_access",
    "revoke_invite",
]
