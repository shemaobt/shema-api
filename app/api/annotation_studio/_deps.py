"""Shared dependencies for annotation-studio routers.

``CurrentUser`` requires any annotation-studio role (or platform admin);
``AdminUser`` requires the ``admin`` role. Both resolve the authenticated
tripod ``User`` via the shared per-app RBAC guards.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access_control import require_app_access, require_role
from app.core.database import get_db
from app.db.models.auth import User

APP_KEY = "annotation-studio"

Db = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, require_app_access(APP_KEY)]
AdminUser = Annotated[User, require_role(APP_KEY, "admin")]
