"""Which role an approved access request grants, per application.

Approval assigns a role by key, so an app missing from this map falls through to
``LEGACY_DEFAULT_ROLE`` — and an app that does not define that role gets a ``RoleError``
at approval time instead of a grant. Every app whose roles do not include ``analyst``
therefore needs its own entry here.

``resource-request-form`` maps to ``equipe``, the least-privileged of its three roles.
It justified itself by the frontend's ``DEFAULT_ROLE`` in ``capabilities.ts`` until
FE-24 (OBT-466) removed that constant: the mocked session was its last reader, and a
*papel default* sitting beside the capability table is what the next person reaches for
when nobody has signed in. The mapping did not move — ``equipe`` is still the floor — only
the reason it pointed at. It now stands on this app's own capability table
(``app/services/resource_request/capabilities.py``), where ``equipe`` holds
``edit_requests`` and nothing else.

Whether approval happens automatically at all is ``apps.auto_approve``, and for this app
it is true since ``20260828_rr02`` — GATE-02 D1, *"quem tiver uma conta"*. The two are one
decision read in two places: the column says an account is granted without review, and the
map here says which role it is granted.

``project-health`` maps to ``user``, the least-privileged of the two roles its launch
migration creates. It was missing here from launch, so every approval for it resolved the
``analyst`` fallback and raised ``RoleError`` instead of granting anything.

``shema`` maps to ``resourceCircle``, the narrowest of its four: the Intercessor, whose
whole relationship to the product is prayer. It needs an entry for the mechanical reason
below — the app is in ``APP_ROLES_OVERRIDE`` and so defines no ``analyst`` — and the choice
of *which* role is safe for a second reason worth writing down. The role carries no region:
``app/services/shema/_scope.py`` grants reach from ``shema_user_regions``, and an account
that holds a **regional** role with no row there reaches nothing. So an approval hands out a
role and no data, and somebody still has to name a region before the account sees a project.
That is the half of deny-by-default this file could have broken, and the reason the floor is
not ``globalStrategist``: that key *is* the unscoped one, and defaulting to it would make
every approval global. ``apps.auto_approve`` stays off for this app — Shemá access is
granted, not registered for — so the approval this map serves is a human one either way.

Which apps need an entry follows from how they were registered. An app taking
``DEFAULT_ROLES`` from ``scripts/seed_apps_roles.py`` already defines ``analyst`` and so
survives on the fallback; an app listed in that script's ``APP_ROLES_OVERRIDE`` never does,
because an override replaces the default set rather than extending it. An app registered by
its own migration defines only what that migration inserts, and so needs an entry unless it
happens to include ``analyst`` — none do. ``project-health``, ``oral-collector``,
``sound-necklace`` and ``internalization-room`` were each missing for one of those two
reasons.
"""

DEFAULT_ROLE_BY_APP_KEY: dict[str, str] = {
    "translation-helper": "user",
    "project-health": "user",
    "meaning-map-generator": "analyst",
    "annotation-studio": "facilitator",
    "resource-request-form": "equipe",
    "oral-collector": "member",
    "sound-necklace": "facilitator",
    "internalization-room": "facilitator",
    "shema": "resourceCircle",
}

LEGACY_DEFAULT_ROLE = "analyst"


def default_role_for(app_key: str) -> str:
    return DEFAULT_ROLE_BY_APP_KEY.get(app_key, LEGACY_DEFAULT_ROLE)
