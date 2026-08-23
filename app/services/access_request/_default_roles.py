DEFAULT_ROLE_BY_APP_KEY: dict[str, str] = {
    "translation-helper": "user",
    "meaning-map-generator": "analyst",
    "annotation-studio": "facilitator",
    # The frontend's own DEFAULT_ROLE in capabilities.ts, and the least-privileged of the
    # three. Without this line an approval would try to grant LEGACY_DEFAULT_ROLE, which
    # this app does not have — the same RoleError translation-helper once raised.
    # Whether approval is automatic at all is apps.auto_approve, which GATE-02 owns.
    "resource-request-form": "equipe",
}

LEGACY_DEFAULT_ROLE = "analyst"


def default_role_for(app_key: str) -> str:
    return DEFAULT_ROLE_BY_APP_KEY.get(app_key, LEGACY_DEFAULT_ROLE)
