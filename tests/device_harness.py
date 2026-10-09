"""A linked tablet: claimed from the Desk to a team, and holding the credential it collected.

Every team door opens only to a device credential, so every case that calls one needs a
device behind it. Built through the services the field goes through: the device is minted,
a facilitator of the team spends its claim code, and the tablet collects its own credential,
which is what kills the copy the claim handed the Desk.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room._deps import DEVICE_CREDENTIAL_HEADER
from app.core.enums import ProjectRole
from app.db.models.auth import User
from app.db.models.language import Language
from app.db.models.project import Project
from app.services.device import claim_device_as_facilitator, create_device
from app.services.device.collect_device_credential import collect_device_credential
from tests.baker import make_language, make_project_user_access, make_user

#: The header the shared room key travelled in, named only by the cases proving it opens nothing.
RETIRED_ROOM_KEY_HEADER = "X-Room-Key"

#: The team a module's tablet belongs to, so the sessions a case writes can be written in it.
TABLET_TEAM = "equipe-do-tablet"


@dataclass(frozen=True)
class LinkedTablet:
    device_id: str
    project_id: str
    credential: str
    desk_copy: str

    @property
    def headers(self) -> dict[str, str]:
        """What the tablet calls the room's team doors with."""
        return {DEVICE_CREDENTIAL_HEADER: self.credential, "X-Room-Device": self.device_id}


async def a_linked_tablet(
    db: AsyncSession,
    *,
    team_id: str | None = None,
    facilitator: User | None = None,
    label: str | None = None,
) -> LinkedTablet:
    """A tablet claimed to the team `team_id` names, made when it does not exist yet."""
    project = await db.get(Project, team_id) if team_id is not None else None
    if project is None:
        project = Project(
            id=team_id or str(uuid.uuid4()),
            name=f"Equipe {uuid.uuid4().hex[:6]}",
            language_id=(await _a_language(db)).id,
        )
        db.add(project)
        await db.commit()
    if facilitator is None:
        facilitator = await make_user(db, email=f"facilitador-{uuid.uuid4().hex[:8]}@example.com")
        await make_project_user_access(db, project.id, facilitator.id, role=ProjectRole.FACILITATOR)

    minted = await create_device(db)
    claimed = await claim_device_as_facilitator(
        db, user=facilitator, code=minted.claim_code, project_id=project.id, label=label
    )
    return LinkedTablet(
        device_id=claimed.device.id,
        project_id=project.id,
        credential=await collect_device_credential(db, claimed.device.id),
        desk_copy=claimed.credential,
    )


async def _a_language(db: AsyncSession) -> Language:
    taken = set((await db.execute(select(Language.code))).scalars())
    code = next(code for code in (uuid.uuid4().hex[:3] for _ in range(1000)) if code not in taken)
    return await make_language(db, name=f"Lingua {code}", code=code)
