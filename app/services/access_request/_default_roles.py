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
"""

DEFAULT_ROLE_BY_APP_KEY: dict[str, str] = {
    "translation-helper": "user",
    "meaning-map-generator": "analyst",
    "annotation-studio": "facilitator",
    "resource-request-form": "equipe",
}

LEGACY_DEFAULT_ROLE = "analyst"


def default_role_for(app_key: str) -> str:
    return DEFAULT_ROLE_BY_APP_KEY.get(app_key, LEGACY_DEFAULT_ROLE)
