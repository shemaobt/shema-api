"""What is left of the form's access package after FE-56 (OBT-549, 30/sep/2026).

The form granted and revoked its own roles from FE-30 (OBT-482) until the 22/sep meeting moved
every role of both apps to one screen in the PME, granted by the Admin alone (OBT-522). The
form's doors — naming, revoking, issuing and withdrawing an invite, and the overview — left
with its screen, and so did their gate (``_gate.py``, *"Admin and Gestor concede"*).

**What stays is what the PME still reads here**: the two invite doors its ``/convite`` page
calls (``describe_invite``, ``accept_invite``), and the pieces the Shemá module composes —
``invite_store``, ``_invite_status`` and ``_rules.assert_role_compatible``. The note this
package carried said OBT-549 would move them into the Shemá module; it did not, by the owner's
decision of 30/sep (option A): moving them rewrites imports across Levi's module and the PME's
``endpoints.ts``, which is his surface under the 25/sep split. It is a follow-up, named on the
PR.
"""

from app.services.resource_request_access.accept_invite import accept_invite
from app.services.resource_request_access.describe_invite import describe_invite

__all__ = [
    "accept_invite",
    "describe_invite",
]
