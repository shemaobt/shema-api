"""Shared dependencies for resource-request routers.

The module has no routes yet — BE-02 brings the tables and BE-03 the capability
checks. What exists here first, and alone, is the seam every one of them will
import: ``CurrentUser`` gates on holding *any* role in the app, and the three
aliases gate on a specific one.

``APP_KEY`` is named here and nowhere else in the module. That is deliberate:
the access model is still open (GATE-02), and when it moves, this file is the
only place that has to.

The three role keys are the ids of the frontend's ``capabilities.ts`` verbatim —
``equipe``, ``mesa``, ``gestor``. BE-03 is what checks the two sides against
FE-22's contract in CI; until then the pairing is held by hand.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access_control import require_app_access, require_role
from app.core.database import get_db
from app.db.models.auth import User

APP_KEY = "resource-request-form"

Db = Annotated[AsyncSession, Depends(get_db)]

CurrentUser = Annotated[User, require_app_access(APP_KEY)]
EquipeUser = Annotated[User, require_role(APP_KEY, "equipe")]
MesaUser = Annotated[User, require_role(APP_KEY, "mesa")]
GestorUser = Annotated[User, require_role(APP_KEY, "gestor")]
