"""The region scope grant — the one thing this module owns about identity.

``docs/shema.md`` §6.1 is the whole argument and this table is its conclusion. The problem it
answers: ``require_role(app_key, role_key)`` gives a global yes/no per application, while
Shemá's authorization is by role **and** by region — a regional coordinator sees and edits
their region. The platform's grant, ``user_app_roles``, has no region column.

Three shapes were available and two were refused. **A ``region`` column on ``user_app_roles``**
would be a platform migration touching the grant shape for eight applications, both guards,
the role cache key, four services and a router — to serve one product's dimension; a module
does not migrate the platform's identity table. **Seven ``organizations`` rows with
``organization_members``** reuses ``app/core/org_scope.py`` and nothing else fits: that table
carries ``manager_id``, which would be a *second owner of who leads a region* beside the org
chart FE-44 §5.3 freezes as the single source, and its ``role`` column is a second role
vocabulary beside the module's four keys. And a region is not a tenant — nobody joins one, it
is computed from a country string.

So: **a module-owned scope table, read by one service.** One small table, one service
function, zero platform change. The split is the same one the sibling already made — the
platform answers *who are you and in what role*, and the module answers *how far does that
reach*.

**No rows means global.** That is the ``globalStrategist``, and any account the client wants
unscoped; a platform admin is global too, short-circuiting before the query as they do at
every other guard in this repository. ``app/services/shema/_scope.py`` computes one
``RegionScope`` value from one read, and **every list query takes it as a parameter** — a
scope applied per endpoint is a rule the next endpoint forgets.
"""

from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base
from app.db.models.shema_enums import REGION_KEY, ShemaRegionKey
from app.db.types import UtcDateTime


class ShemaUserRegion(Base):
    """One region this account's scope includes.

    The primary key is the pair, which is the uniqueness the design asks for written as the
    key rather than as a constraint beside a surrogate id — there is nothing to have two of.

    ``docs/shema.md`` §5.13 gives this table to BE-03 and §5's preamble gives **every** table
    in the module to BE-02. It is created here on the preamble's reading: BE-03 runs in the
    wave above this one and would otherwise open a migration against this head for one small
    table, which is the outcome the wave's migration rule exists to avoid. Nothing else about
    the aggregate is taken from BE-03 — the scope service, the session endpoint and the
    granting path are all still its own.

    The grant of the *role* is not here and never will be: it stays ``(user, app, role)`` in
    ``user_app_roles``, written through ``app/services/authorization/grant_app_role.py`` and
    never through ``scripts/grant_app_role.py``, which matches on ``(user_id, app_id)`` and
    overwrites ``role_id`` (OBT-484) — and a Shemá account legitimately holds more than one
    role.
    """

    __tablename__ = "shema_user_regions"

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    region_key: Mapped[ShemaRegionKey] = mapped_column(REGION_KEY, primary_key=True)
    #: Who granted the scope. Nullable because a scope may be seeded rather than granted by a
    #: person, and it restricts on delete nowhere — this is a convenience for an audit
    #: question, not the audit itself.
    granted_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    granted_at: Mapped[datetime] = mapped_column(
        UtcDateTime(timezone=True), server_default=func.now()
    )
