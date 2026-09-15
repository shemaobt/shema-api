"""Seed the application registry — one row per app, with its roles.

Idempotent by design: every entry is looked up before it is written, so this runs safely
against a database that already holds some or all of it.

``app_url`` is not decoration. ``request_password_reset`` looks the row up by ``app_key``
and builds the reset email as ``{app_url}/reset-password?token=…``, so a wrong value
breaks password recovery and nothing else, silently. The loop below only fills an
``app_url`` that is empty, which means correcting one already written is an UPDATE on the
row rather than a re-run of this script.

``APP_ROLES_OVERRIDE`` carries the apps whose roles are not ``DEFAULT_ROLES``. For
``resource-request-form`` the four keys are the role ids of the frontend's
``capabilities.ts`` verbatim, not a translation of them, and ``shema``'s four are the
``SessionRole`` union of its own ``src/types/role.ts`` on the same rule — camelCase against
this repository's mostly snake_case habit, because ``GET /api/shema/session`` answers one of
them and a translation table between two spellings of one vocabulary is a second place to be
wrong (``docs/shema.md`` §2.3). ``roles.role_key`` is ``String(100)`` scoped per app, so
nothing in the platform objects.

**The Shemá ``app_url`` is the convention and not a reading**, and it is the one entry here
that says so. ``docs/shema.md`` §10 item 3 asked BE-03 to read the console's hostname off the
deployment; there is no deployment to read — the console is wave 1, it has no deploy
workflow, no environment file beyond ``VITE_API_PROXY_TARGET``, and neither repository names
a host. So this follows the eight rows above it, every one of which is the product's name
lowercased with no separators under ``shemaywam.com``. Leaving it empty was the alternative
and is worse: ``request_password_reset`` then builds the reset link from
``http://localhost:5173`` in production, which is the silent failure this docstring opens
with, while a hostname that is wrong but conventional fails visibly on the first click and is
a one-row UPDATE to correct — which is exactly what the "only fills an empty ``app_url``"
rule below already anticipates.
"""

import asyncio

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.db.models.auth import App, Role
from app.services.shema._scope import ROLE_KEYS as SHEMA_ROLE_KEYS

SEED_APPS = [
    ("tripod-studio", "Tripod Studio", "https://tripodstudio.shemaywam.com"),
    ("meaning-map-generator", "Meaning Map Generator", "https://meaningmaps.shemaywam.com"),
    ("oral-bridge", "Oral Bridge", "https://oralbridge.shemaywam.com"),
    ("oral-collector", "Oral Collector", "https://oralcollector.shemaywam.com"),
    ("avita", "AViTA", "https://avita.shemaywam.com"),
    ("annotation-studio", "Annotation Studio", "https://annotationstudio.shemaywam.com"),
    ("sound-necklace", "Sound Necklace", "https://soundnecklace.shemaywam.com"),
    ("resource-request-form", "Resource Request Form", "https://resourceform.shemaywam.com"),
    ("shema", "Shemá", "https://shema.shemaywam.com"),
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
    "resource-request-form": ["equipe", "mesa", "gestor", "lider"],
    "shema": list(SHEMA_ROLE_KEYS),
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
