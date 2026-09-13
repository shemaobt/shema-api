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

**BE-13 landed the people.** Two aggregates that are both directories of human beings and
are deliberately not one model: the org chart (``list_regions``, ``get_region_team``,
``save_region_team``, ``list_role_changes``) and the intercessor network. ``docs/shema.md``
§5.7 forbids a reference between them in either direction, so there is none — not a foreign
key, not a shared row, not a shared service. ``_directory.py`` is the sole owner of the
network's contact column, of its sensitive-country flag and of every read and write of
``shema_intercessor_consents``, and ``tests/test_shema/test_people_privacy.py`` globs this
package and ``app/api/shema/`` to keep it sole.

Four files in here are sole owners, because a second reader of what they guard is the defect:
``_scope.py`` (which projects a caller reaches, from role **and** region — **built, BE-03**),
``_directory.py`` (a person's contact, consent and country — **built, BE-13**), ``_consent.py``
(the only reader of the three prayer columns) and ``_redaction.py`` (the sensitive-country rule
on a project). ``docs/shema.md`` §6 is why each is one file, and §3.3 is where every other
concern lands under the layering rules.
"""

from __future__ import annotations

from app.services.shema._directory import (
    LeavingPerson,
    leaving_directory,
    leaving_person,
)
from app.services.shema._scope import (
    RegionScope,
    reaches,
    region_scope,
    visible_projects,
    within_scope,
)
from app.services.shema.add_intercessor import add_intercessor
from app.services.shema.count_projects import count_projects, count_projects_by_region
from app.services.shema.get_project import get_project
from app.services.shema.get_region_team import get_region_team
from app.services.shema.get_session import get_session
from app.services.shema.list_intercessors import list_intercessors
from app.services.shema.list_projects import list_projects
from app.services.shema.list_regions import list_regions
from app.services.shema.list_role_changes import list_role_changes
from app.services.shema.remove_intercessor import remove_intercessor
from app.services.shema.reveal_intercessor_contact import reveal_intercessor_contact
from app.services.shema.save_region_team import save_region_team
from app.services.shema.set_intercessor_consent import (
    set_intercessor_consent,
    withdraw_intercessor_consent,
)
from app.services.shema.set_region_scope import set_region_scope
from app.services.shema.update_intercessor import update_intercessor

__all__ = [
    "LeavingPerson",
    "RegionScope",
    "add_intercessor",
    "count_projects",
    "count_projects_by_region",
    "get_project",
    "get_region_team",
    "get_session",
    "leaving_directory",
    "leaving_person",
    "list_intercessors",
    "list_projects",
    "list_regions",
    "list_role_changes",
    "reaches",
    "region_scope",
    "remove_intercessor",
    "reveal_intercessor_contact",
    "save_region_team",
    "set_intercessor_consent",
    "set_region_scope",
    "update_intercessor",
    "visible_projects",
    "withdraw_intercessor_consent",
    "within_scope",
]
