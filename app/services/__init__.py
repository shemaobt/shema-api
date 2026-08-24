from app.services import (
    access_request,
    app,
    auth,
    authorization,
    language,
    meaning_map,
    notifications,
    org,
    phase,
    platform,
    project,
    project_health,
    public_request,
    rag,
    sound_necklace,
    translation_helper,
    user,
)

access_request_service = access_request
app_service = app
auth_service = auth
authorization_service = authorization
language_service = language
meaning_map_service = meaning_map
notification_service = notifications
organization_service = org
phase_service = phase
platform_service = platform
project_service = project
project_health_service = project_health
public_request_service = public_request
rag_service = rag
sound_necklace_service = sound_necklace
translation_helper_service = translation_helper
user_service = user

__all__ = [
    "access_request",
    "access_request_service",
    "app",
    "app_service",
    "auth",
    "auth_service",
    "authorization",
    "authorization_service",
    "language",
    "language_service",
    "meaning_map",
    "meaning_map_service",
    "notification_service",
    "notifications",
    "org",
    "organization_service",
    "phase",
    "phase_service",
    "platform",
    "platform_service",
    "project",
    "project_health",
    "project_health_service",
    "project_service",
    "public_request",
    "public_request_service",
    "rag",
    "rag_service",
    "sound_necklace",
    "sound_necklace_service",
    "translation_helper",
    "translation_helper_service",
    "user",
    "user_service",
]
