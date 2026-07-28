"""Bind an acousteme collection's audios to a Sound Necklace project.

Acousteme artifacts are standalone by design: no project, no recording, a caller-minted
slug for an id. That is what lets a pilot collection exist without project scaffolding —
and it is also why the Sound Necklace cannot list them behind a project gate until
something says which project may see them. ``sn_audio_refs`` is that something, and this
writes it.

    uv run python scripts/seed_sn_audio_refs.py --project-id <uuid>

Consent is the collection consent of PRD §12/O6 — the one the storyteller gave when the
audio was recorded. A pilot audio has no storyteller row to carry it, so it is asserted
here, by a human who knows, with ``--consent``. A new binding made without that flag
starts with consent absent, which is the honest default: the setup screen will say so
rather than the API inventing an agreement nobody gave.

Re-running is safe. It never duplicates a binding, never rebinds an audio another
project already owns, and — with no ``--consent``/``--no-consent`` — never touches the
consent already recorded on a binding. Re-seeding to pick up one new audio must not
silently revoke the consent a human recorded for the others.
"""

from __future__ import annotations

import argparse
import asyncio
import logging

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.db.models.project import Project
from app.db.models.sound_necklace import SnAudioRef
from app.services.oral_collector import acousteme_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
logger = logging.getLogger("seed_sn_audio_refs")

COLLECTION = "terena-ruth"


async def seed(project_id: str, collection: str, consent: bool | None, dry_run: bool) -> None:
    async with AsyncSessionLocal() as db:
        project = (
            await db.execute(select(Project).where(Project.id == project_id))
        ).scalar_one_or_none()
        if project is None:
            raise SystemExit(f"No project {project_id}")

        # Bind only artifacts that record where their source audio went: the listing
        # will not show an audio it cannot play, so binding one would be a silent no-op.
        artifacts = [
            a
            for a in await acousteme_service.list_by_collection(db, collection)
            if a.audio_bucket and a.audio_object
        ]
        if not artifacts:
            raise SystemExit(f"No servable READY acoustemes in collection {collection!r}")

        for artifact in artifacts:
            existing = (
                await db.execute(select(SnAudioRef).where(SnAudioRef.audio_id == artifact.audio_id))
            ).scalar_one_or_none()

            if existing is not None and existing.project_id != project_id:
                logger.warning(
                    "%s is already bound to project %s — leaving it alone",
                    artifact.audio_id,
                    existing.project_id,
                )
                continue

            logger.info(
                "%s %s -> %s (consent=%s)",
                "would bind" if dry_run else "binding",
                artifact.audio_id,
                project.name,
                "unchanged" if existing is not None and consent is None else bool(consent),
            )
            if dry_run:
                continue

            if existing is None:
                db.add(
                    SnAudioRef(
                        audio_id=artifact.audio_id,
                        project_id=project_id,
                        consent_present=bool(consent),
                    )
                )
            elif consent is not None:
                existing.consent_present = consent

        if not dry_run:
            await db.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-id", required=True, help="The project that may see the audios")
    parser.add_argument("--collection", default=COLLECTION, help="Acousteme collection to bind")
    # Tri-state on purpose. A consent flag is not a default to be re-applied on every
    # run: re-seeding to pick up one new audio must not silently revoke the consent a
    # human recorded for the other forty-one. Absent means "leave what is there alone";
    # a new binding with no flag starts at absent, which is the honest starting point.
    parser.add_argument(
        "--consent",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Assert (--consent) or withdraw (--no-consent) collection consent (§12/O6). "
        "Omit to leave existing bindings untouched; new ones start without consent.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Log only; no DB writes")
    args = parser.parse_args()
    asyncio.run(seed(args.project_id, args.collection, args.consent, args.dry_run))


if __name__ == "__main__":
    main()
