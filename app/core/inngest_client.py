import inngest

from app.core.config import Settings, get_settings


def build_inngest_client(settings: Settings) -> inngest.Inngest:
    return inngest.Inngest(
        app_id=settings.inngest_app_id,
        event_key=settings.inngest_event_key or None,
        signing_key=settings.inngest_signing_key or None,
    )


settings = get_settings()

inngest_client = build_inngest_client(settings)
