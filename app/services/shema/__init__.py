"""Shemá's service layer — all of this module's logic and **all** of its queries.

One operation per file with a re-export here, which is the newer house style
(``app/services/access_request/``, ``project/``, ``auth/``, ``resource_request/``) rather
than the grouped ``*_service.py`` of ``annotation_studio/``.

**BE-03 landed the scope and the session.** ``_scope.py`` is the sole owner of the region
axis and of the module's only ``select(ShemaProject)``: every reader here starts from its
``visible_projects(scope)``, so a query that could return an out-of-scope row is not a
thing a later issue can write by forgetting something. The three query services beside it
— the collection, the record, the counts — exist as much to hold that property as to serve
an endpoint, because the issue's line is that such a query is a bug *even if no endpoint
calls it that way*. BE-05 and BE-06 build their endpoints on them rather than beside
them.

Three files in here are named before they exist because they are sole owners and a
second reader of what they guard is the defect: ``_scope.py`` (which projects a caller
reaches, from role **and** region — **built, BE-03**), ``_consent.py`` (the only reader
of the three prayer columns) and ``_redaction.py`` (the sensitive-country rule).
``docs/shema.md`` §6 is why each is one file, and §3.3 is where every other concern
lands under the layering rules.
"""

from __future__ import annotations

from app.services.shema._scope import (
    RegionScope,
    reaches,
    region_scope,
    visible_projects,
    within_scope,
)
from app.services.shema.count_projects import count_projects, count_projects_by_region
from app.services.shema.get_project import get_project
from app.services.shema.get_session import get_session
from app.services.shema.list_projects import list_projects
from app.services.shema.set_region_scope import set_region_scope

__all__ = [
    "RegionScope",
    "count_projects",
    "count_projects_by_region",
    "get_project",
    "get_session",
    "list_projects",
    "reaches",
    "region_scope",
    "set_region_scope",
    "visible_projects",
    "within_scope",
]
