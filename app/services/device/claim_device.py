"""Spending a claim code, and saying nothing about why one was refused.

Every rejection below raises the same exception with the same message, and writes a
different ``reason`` to the log. That asymmetry is the point of the module: the operator
debugging an installation needs four answers, and the caller gets one. See
``app.core.exceptions.InvalidClaimCodeError`` for why.
"""

import logging
from typing import NoReturn

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidClaimCodeError
from app.db.models.device import Device
from app.db.models.project import Project
from app.services.device import claim_code as claim_codes

logger = logging.getLogger(__name__)


def _refuse(reason: str, *, device_id: str | None = None) -> NoReturn:
    logger.warning(
        "device claim refused",
        extra={"reason": reason, "device_id": device_id},
    )
    raise InvalidClaimCodeError()


async def claim_device(db: AsyncSession, *, code: str, project_id: str) -> Device:
    """Spend ``code`` to attach its device to ``project_id``.

    Returns the claimed device. Raises ``InvalidClaimCodeError`` — indistinguishably —
    if the code is unknown, already spent, past its life, or names a project that does
    not exist.

    Spending the code is all this does. It does not issue the long-lived credential the
    device will authenticate with afterwards; that exchange is ENG-443, and the seam is
    here, at the return.
    """
    now = claim_codes.utcnow()

    device = (
        await db.execute(
            select(Device).where(Device.claim_code_hash == claim_codes.hash_claim_code(code))
        )
    ).scalar_one_or_none()

    if device is None:
        _refuse("unknown_code")
    if device.claimed_at is not None:
        _refuse("code_already_spent", device_id=device.id)
    if claim_codes.has_expired(device.claim_code_expires_at, at=now):
        _refuse("code_expired", device_id=device.id)

    project = (
        await db.execute(select(Project.id).where(Project.id == project_id))
    ).scalar_one_or_none()
    if project is None:
        _refuse("unknown_project", device_id=device.id)

    device.project_id = project_id
    device.claimed_at = now
    await db.commit()
    await db.refresh(device)
    return device
