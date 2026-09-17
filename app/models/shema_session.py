"""What ``GET /api/shema/session`` answers — the signed-in persona, three fields.

FE-44 §9.13 froze the shape verbatim::

    { role: SessionRole, regionScope: RegionKey[] | null, name: string | null }

``GET /api/auth/my-roles`` cannot answer it because the platform's grant has no region
(FE-44 §3.1); the region is this module's own axis and ``app/services/shema/_scope.py``
computes it. What the endpoint adds over the platform's session is exactly that.

**The wire spelling here is camelCase, and this is not the record's decision.**
``app/models/shema.py`` deliberately leaves the project record's spelling to whoever writes
its first endpoint (BE-05 for the read, BE-06 for the write). This model does not
pre-empt that: it is a **frozen three-field contract** with a name the frontend already
reads as ``session.regionScope``, so there is nothing here to decide. The mechanism is a
Pydantic alias rather than a camelCase attribute — the Python side stays the house's
snake_case, FastAPI serialises by alias by default, and whichever way BE-05 goes for the
record, the shape of the choice is already visible.

**``role`` is typed ``str`` and not a ``Literal`` of the four keys**, deliberately. The
vocabulary's owner is ``app/services/shema/_scope.py`` (``ROLE_PRECEDENCE``), and
``tests/test_app_boots.py::test_no_dto_module_reaches_up_into_the_service_layer`` forbids
this package from importing that one — the inversion that closed an import cycle once.
Re-typing the four keys here to get a ``Literal`` would be a second copy of a four-key
vocabulary whose whole value is that there is one, and the two would first disagree on the
day somebody renames a role. The endpoint can only ever emit one of the four, because
``role_from`` picks from that tuple and from nowhere else.

``None`` for ``role`` is unreachable through the endpoint — ``require_app_access`` refuses
an account with no Shemá role before the handler runs — and is in the type because the
service can be called from somewhere that guard has not run, and answering a role nobody
granted is the wrong half to guess on.
"""

from pydantic import BaseModel, ConfigDict, Field


class ShemaSession(BaseModel):
    """The persona the console renders its whole authorization *display* from.

    Display, and not enforcement: FE-44 §8.7 is explicit that hiding a control in the UI is
    presentation, and every rule this shape describes is applied again in
    ``app/services/shema/`` on the path that actually returns data. A client that lies about
    its own session reaches nothing it could not reach by asking without one.
    """

    model_config = ConfigDict(populate_by_name=True)

    #: One of ``globalStrategist``, ``coordinator``, ``obtLab``, ``resourceCircle``.
    role: str | None = None
    #: The regions the caller reaches. **``null`` means global** — the frozen spelling, and
    #: the reason an empty list is a different answer: it is an account with a regional role
    #: and no region granted, which reaches nothing.
    region_scope: list[str] | None = Field(default=None, alias="regionScope")
    #: Resolved from the org chart, falling back to the account's own ``display_name``.
    #: ``app/services/shema/get_session.py`` carries the rule and the argument for it.
    name: str | None = None
