"""What ``GET /api/shema/session`` answers — the signed-in persona, and where the form lives.

FE-44 §9.13 froze three fields, OBT-523 added the fourth and OBT-544 the fifth::

    { role: SessionRole, roles: SessionRole[], regionScope: RegionKey[] | null,
      name: string | null, apps: { resourceRequestForm: string | null } }

**``apps`` is the registry's answer, not the console's.** The PME opens the resource-request
form in a new tab — *Solicitar recurso*, the *Resource Circle* entry, the external request
link's address — and the form's address is ``apps.app_url``, the same row the form's own
letters read. Serving it here is what keeps it out of a constant in the console.

``GET /api/auth/my-roles`` cannot answer it because the platform's grant has no region
(FE-44 §3.1); the region is this module's own axis and ``app/services/shema/_scope.py``
computes it. What the endpoint adds over the platform's session is exactly that — and, since
OBT-523, the roles an account holds across the two apps the PME serves.

**``roles`` is the answer and ``role`` is the transition.** ``roles`` is every role the
account holds, highest precedence first; ``role`` is its first entry, kept only so no screen
that still reads one role breaks while the console moves to the list. Consumers that are new
read ``roles``; the day none reads ``role``, it goes.

**The wire spelling here is camelCase, and this is not the record's decision.**
``app/models/shema.py`` deliberately leaves the project record's spelling to whoever writes
its first endpoint (BE-05 for the read, BE-06 for the write). This model does not
pre-empt that: it is a **frozen contract** with a name the frontend already
reads as ``session.regionScope``, so there is nothing here to decide. The mechanism is a
Pydantic alias rather than a camelCase attribute — the Python side stays the house's
snake_case, FastAPI serialises by alias by default, and whichever way BE-05 goes for the
record, the shape of the choice is already visible.

**``role`` and ``roles`` are typed ``str`` and not a ``Literal`` of the keys**, deliberately.
The vocabulary's owner is ``app/services/shema/_scope.py`` (``ROLE_PRECEDENCE``), and
``tests/test_app_boots.py::test_no_dto_module_reaches_up_into_the_service_layer`` forbids
this package from importing that one — the inversion that closed an import cycle once.
Re-typing the keys here to get a ``Literal`` would be a second copy of a vocabulary whose
whole value is that there is one, and the two would first disagree on the day somebody
renames a role. The endpoint can only ever emit keys of that tuple, because ``roles_from``
picks from it and from nowhere else.

``None`` for ``role`` — and an empty ``roles`` — reach the wire only for an installation
admin with no grant, whom the door admits as every guard does: everybody else holding
nothing is refused before the handler runs.
"""

from pydantic import BaseModel, ConfigDict, Field


class SessionApps(BaseModel):
    """The addresses of the apps the PME opens, read off the registry (OBT-544).

    ``None`` when the registry has no row or no ``app_url`` for the app: the console then
    draws nothing that would open it, rather than a button that leads nowhere. No trailing
    slash, so the console appends a path without guessing.
    """

    model_config = ConfigDict(populate_by_name=True)

    resource_request_form: str | None = Field(default=None, alias="resourceRequestForm")


class ShemaSession(BaseModel):
    """The persona the console renders its whole authorization *display* from.

    Display, and not enforcement: FE-44 §8.7 is explicit that hiding a control in the UI is
    presentation, and every rule this shape describes is applied again in
    ``app/services/shema/`` on the path that actually returns data. A client that lies about
    its own session reaches nothing it could not reach by asking without one.
    """

    model_config = ConfigDict(populate_by_name=True)

    #: **Transitional**: the first of ``roles``, so a screen that reads one role keeps working.
    role: str | None = None
    #: Every role the account holds, highest precedence first — never ``null``; empty only for
    #: an installation admin holding no grant.
    roles: list[str] = Field(default_factory=list)
    #: The regions the caller reaches. **``null`` means global** — the frozen spelling, and
    #: the reason an empty list is a different answer: it is an account with a regional role
    #: and no region granted, which reaches nothing.
    region_scope: list[str] | None = Field(default=None, alias="regionScope")
    #: Resolved from the org chart, falling back to the account's own ``display_name``.
    #: ``app/services/shema/get_session.py`` carries the rule and the argument for it.
    name: str | None = None
    #: Where the apps the PME opens live — the registry's ``app_url`` (OBT-544).
    apps: SessionApps = Field(default_factory=SessionApps)
