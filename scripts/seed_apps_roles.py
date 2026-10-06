"""Seed the application registry — one row per app, with its roles.

Idempotent by design: every entry is looked up before it is written, so this runs safely
against a database that already holds some or all of it.

``app_url`` is not decoration. ``request_password_reset`` looks the row up by ``app_key``
and builds the reset email as ``{app_url}/reset-password?token=…``; the PME's invites
(``/convite?token=…``), leave links (``/leave/<token>``) and intake links read the same
``shema`` row, and the form's endorsement and request links read its own. A wrong value
breaks every one of those letters, silently. The loop below only fills an ``app_url`` that
is empty, which means correcting one already written is an UPDATE on the row rather than a
re-run of this script.

``APP_ROLES_OVERRIDE`` carries the apps whose roles are not ``DEFAULT_ROLES``. For
``resource-request-form`` the keys are the role ids of the frontend's ``capabilities.ts``
verbatim, not a translation of them, **plus the roles it retired** — ``lider`` since FE-49
(OBT-517), a row installations have and ``20260930_rr12`` stripped of every grant
(``RETIRED_ROLES`` in ``capabilities.py``); and ``shema``'s four are the
``SessionRole`` union of its own ``src/types/role.ts`` on the same rule — camelCase against
this repository's mostly snake_case habit, because ``GET /api/shema/session`` answers one of
them and a translation table between two spellings of one vocabulary is a second place to be
wrong (``docs/shema.md`` §2.3). ``roles.role_key`` is ``String(100)`` scoped per app, so
nothing in the platform objects.

**The Admin of OBT-522 is one role applied to two apps, and not a fifth key in two
overrides.** ``PLATFORM_ADMIN_APPS`` seeds ``admin`` — labelled *"Admin da plataforma"* — in
``shema`` and ``resource-request-form``, beside each app's own roles. It stays out of
``APP_ROLES_OVERRIDE`` on purpose: the form's list there is its frontend's role ids plus the
retired ones, pinned by ``tests/test_resource_requests/`` against ``capabilities.ts``, and the
Admin is neither.
The label applies only to those two apps; every other app's ``admin`` keeps its own. Existing
installations get the same row from ``20260927_shema08``, which writes the same key and label;
``tests/test_shema/test_admin_role.py`` holds the two to each other.

**The Shemá ``app_url`` is read off the deployment, since 6/oct/2026.** BE-03 wrote
``https://shema.shemaywam.com`` here as a convention — there was no deployment to read, so it
followed the eight rows above it, the product's name lowercased under ``shemaywam.com`` — and
its own docstring said a wrong value would fail on the first click and cost a one-row UPDATE.
It did: the hostname never got a DNS record, and every letter the PME builds from the row —
invites, leave links, intake links, the password reset — led nowhere (OBT-567). The value is
now the Cloud Run address the PME answers on, by the user's decision of 6/oct/2026 that no
``shema.shemaywam.com`` is planned; ``20261006_shema567`` is the UPDATE
for installations that already hold the old row. ``resource-request-form``'s row was checked
in the same pass and stays: ``resourceform.shemaywam.com`` answers, mapped onto its Cloud Run
service. The invite, leave and intake links land on routes the PME has (``convite``,
``leave/:token``); what the corrected value does not do yet is finish password recovery: the
PME has no ``/reset-password`` route as of 6/oct/2026, so that one link reaches a real host and
no page until the screen exists over there.
"""

import asyncio

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.db.models.auth import App, Role
from app.services.shema._scope import ADMIN_ROLE
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
    ("shema", "Shemá", "https://project-management-ecosystem-f7ssqjozfq-uc.a.run.app"),
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

#: The apps the Admin of OBT-522 is seeded in, under one label.
PLATFORM_ADMIN_APPS = ("resource-request-form", "shema")
PLATFORM_ADMIN_LABEL = "Admin da plataforma"


def _label(role_key: str) -> str:
    return role_key.replace("-", " ").replace("_", " ").title()


def seeded_roles(app_key: str) -> list[tuple[str, str]]:
    """The ``(role_key, label)`` pairs ``app_key`` is seeded with, in seeding order."""
    roles = [(key, _label(key)) for key in APP_ROLES_OVERRIDE.get(app_key, DEFAULT_ROLES)]
    if app_key in PLATFORM_ADMIN_APPS:
        roles = [(key, label) for key, label in roles if key != ADMIN_ROLE]
        roles.append((ADMIN_ROLE, PLATFORM_ADMIN_LABEL))
    return roles


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

            for role_key, label in seeded_roles(app_key):
                role_result = await db.execute(
                    select(Role).where(Role.app_id == app.id, Role.role_key == role_key)
                )
                role = role_result.scalar_one_or_none()
                if not role:
                    db.add(
                        Role(
                            app_id=app.id,
                            role_key=role_key,
                            label=label,
                            is_system=True,
                        )
                    )

        await db.commit()


if __name__ == "__main__":
    asyncio.run(seed())
