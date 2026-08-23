import asyncio

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.db.models.auth import App, Role

SEED_APPS = [
    ("tripod-studio", "Tripod Studio", "https://tripodstudio.shemaywam.com"),
    ("meaning-map-generator", "Meaning Map Generator", "https://meaningmaps.shemaywam.com"),
    ("oral-bridge", "Oral Bridge", "https://oralbridge.shemaywam.com"),
    ("oral-collector", "Oral Collector", "https://oralcollector.shemaywam.com"),
    ("avita", "AViTA", "https://avita.shemaywam.com"),
    ("annotation-studio", "Annotation Studio", "https://annotationstudio.shemaywam.com"),
    ("sound-necklace", "Sound Necklace", "https://soundnecklace.shemaywam.com"),
    (
        "resource-request-form",
        "Resource Request Form",
        # Provisional: the frontend's Cloud Run URL, until resourceform.shemaywam.com exists.
        # The deterministic form (SERVICE-PROJECTNUMBER.REGION.run.app), not the hash one —
        # the hash is assigned at service creation and would not survive a recreate.
        # Swapping it is an UPDATE on the row, not a re-run: the seed below only fills an
        # empty app_url, and request_password_reset builds the FE-25 email from this value.
        "https://resource-request-form-718681737495.us-central1.run.app",
    ),
]

DEFAULT_ROLES = [
    "admin",
    "analyst",
    "reviewer",
    "annotator",
    "viewer",
    "exegete",
    "biblical_language_specialist",
    "translation_specialist",
]

APP_ROLES_OVERRIDE: dict[str, list[str]] = {
    "oral-collector": ["member", "manager"],
    "annotation-studio": ["admin", "facilitator"],
    "sound-necklace": ["facilitator", "project_admin"],
    # The role ids of resource-request-form's capabilities.ts verbatim, not a translation.
    "resource-request-form": ["equipe", "mesa", "gestor"],
}


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        for app_key, app_name, app_url in SEED_APPS:
            result = await db.execute(select(App).where(App.app_key == app_key))
            app = result.scalar_one_or_none()
            if not app:
                app = App(app_key=app_key, name=app_name, app_url=app_url)
                db.add(app)
                await db.flush()
            elif not app.app_url:
                app.app_url = app_url
                await db.flush()

            roles = APP_ROLES_OVERRIDE.get(app_key, DEFAULT_ROLES)
            for role_key in roles:
                role_result = await db.execute(
                    select(Role).where(Role.app_id == app.id, Role.role_key == role_key)
                )
                role = role_result.scalar_one_or_none()
                if not role:
                    db.add(
                        Role(
                            app_id=app.id,
                            role_key=role_key,
                            label=role_key.replace("-", " ").replace("_", " ").title(),
                            is_system=True,
                        )
                    )

        await db.commit()


if __name__ == "__main__":
    asyncio.run(seed())
