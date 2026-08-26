"""Which role an approved access request grants, per application.

Approval assigns a role by key, so an app missing from this map falls through to
``LEGACY_DEFAULT_ROLE`` — and an app that does not define that role gets a ``RoleError``
at approval time instead of a grant. Every app whose roles do not include ``analyst``
therefore needs its own entry here.

``resource-request-form`` maps to ``equipe``: the frontend's own ``DEFAULT_ROLE`` in
``capabilities.ts``, and the least-privileged of its three. Whether approval happens
automatically at all is ``apps.auto_approve``, which is a separate decision.

``project-health`` maps to ``user``, the least-privileged of the two roles its launch
migration creates. It was missing here from launch, so every approval for it resolved the
``analyst`` fallback and raised ``RoleError`` instead of granting anything.

Which apps need an entry follows from how they were seeded. An app taking ``DEFAULT_ROLES``
from ``scripts/seed_apps_roles.py`` already defines ``analyst`` and so works on the
fallback; an app listed in that script's ``APP_ROLES_OVERRIDE`` never does, because an
override replaces the default set rather than extending it. Every override app therefore
belongs here, and ``oral-collector`` and ``sound-necklace`` were missing for the same
reason ``project-health`` was.
"""

DEFAULT_ROLE_BY_APP_KEY: dict[str, str] = {
    "translation-helper": "user",
    "project-health": "user",
    "meaning-map-generator": "analyst",
    "annotation-studio": "facilitator",
    "resource-request-form": "equipe",
    "oral-collector": "member",
    "sound-necklace": "facilitator",
}

LEGACY_DEFAULT_ROLE = "analyst"


def default_role_for(app_key: str) -> str:
    return DEFAULT_ROLE_BY_APP_KEY.get(app_key, LEGACY_DEFAULT_ROLE)
