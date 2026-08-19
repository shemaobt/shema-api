"""Spending a claim code, and saying nothing about why one was refused.

Every rejection below raises the same exception with the same message, and writes a
different ``reason`` to the log. That asymmetry is the point of the module: the operator
debugging an installation needs four answers, and the caller gets one.
"""

import logging
from enum import StrEnum
from typing import Final, NoReturn

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.device import Device
from app.db.models.project import Project
from app.services.device import claim_code as claim_codes

logger = logging.getLogger(__name__)


class InvalidClaimCodeError(Exception):
    """A device claim code was refused, and the caller is not told which refusal it was.

    Wrong, already spent, expired, and naming a project that does not exist are four
    different events to an operator and must be one event to whoever is holding the
    tablet. A caller who can tell them apart has an oracle: they can enumerate codes and
    learn which ones exist, and a code that exists is a device someone else can capture.

    So the message is fixed and carries nothing about the attempt. Which of the four it
    was is written to the log by this module, where an operator debugging a failed
    installation can read it and an attacker cannot.

    Raise it with no argument. It takes none deliberately — an argument is exactly the
    thing that would vary between the four.

    **The opt-in exception, added by ENG-443.** ``reason`` carries which of the four it
    was. The exception's *value* is untouched — type, message and ``args`` are still one
    thing across all four, so any caller that merely propagates it leaks nothing, and a
    caller has to reach for ``reason`` deliberately to see more.

    Exactly one caller does: ``claim_device_as_facilitator``, because its caller is an
    authenticated facilitator with a team watching them type, and telling a typo apart
    from an expired code is the difference between retyping and walking to the tablet.
    The oracle ENG-437 closed is one for an anonymous caller, and authentication is what
    removes that caller. A caller who cannot name a reason to read ``reason`` should not
    read it.

    It lives here rather than in ``app/core/exceptions.py`` because nothing in this slice
    reaches HTTP, and ``register_exception_handlers`` registers every top-level class in
    that module. A service-local exception the router maps itself is the shape CLAUDE.md
    §3 asks for, and the shape ``GenerationError`` already uses. **The route that spends a
    code (ENG-443) has to map this to a status of its own** — left unmapped it reaches
    ``handle_unexpected`` and answers 500.
    """

    MESSAGE: Final = "That claim code is not valid."

    #: Which of the four refusals this was. Never part of the exception's value.
    reason: "ClaimRefusal | None" = None

    def __init__(self) -> None:
        super().__init__(self.MESSAGE)


class ClaimRefusal(StrEnum):
    """Why a claim was refused. Closed set of four; the route switches on it."""

    UNKNOWN_CODE = "unknown_code"
    ALREADY_SPENT = "code_already_spent"
    EXPIRED = "code_expired"
    UNKNOWN_PROJECT = "unknown_project"


def _refuse(reason: ClaimRefusal, *, device_id: str | None = None) -> NoReturn:
    logger.warning(
        "device claim refused",
        extra={"reason": reason, "device_id": device_id},
    )
    error = InvalidClaimCodeError()
    error.reason = reason
    raise error


async def _project_exists(db: AsyncSession, project_id: str) -> bool:
    """Whether ``project_id`` names a real project."""
    found = (
        await db.execute(select(Project.id).where(Project.id == project_id))
    ).scalar_one_or_none()
    return found is not None


async def claim_device(
    db: AsyncSession, *, code: str, project_id: str, commit: bool = True
) -> Device:
    """Spend ``code`` to attach its device to ``project_id``.

    Returns the claimed device. Raises ``InvalidClaimCodeError`` — indistinguishably —
    if the code is unknown, already spent, past its life, or names a project that does
    not exist.

    The checks above the write are what produce a precise ``reason`` for the log. They are
    not what makes the code single-use: between reading the row and writing it, another
    claim can spend the same code, and both callers would pass a check made on a stale
    read. The write itself carries the guard — ``WHERE claimed_at IS NULL`` — and a row
    count of zero means the other claim won. That is atomic on any engine, which matters
    because the suite runs on SQLite and ``SELECT ... FOR UPDATE`` is a no-op there: a
    lock would leave this untested exactly where the defect lives.

    Spending the code is all this does. It does not issue the long-lived credential the
    device will authenticate with afterwards; that exchange is ENG-443, and the seam is
    here, at the return.

    ``commit=False`` leaves the transaction open so a caller can write more in it. That
    exists for one reason: whatever a spent code *buys* has to land or not land together
    with the spend. A caller that commits the spend on its own and then fails leaves a row
    that is claimed and paid for with nothing — refused as already used on the next
    attempt, and with no other way to be paid. The device would be permanently unusable
    because one later write failed.
    """
    now = claim_codes.utcnow()

    device = (
        await db.execute(
            select(Device).where(Device.claim_code_hash == claim_codes.hash_claim_code(code))
        )
    ).scalar_one_or_none()

    if device is None:
        _refuse(ClaimRefusal.UNKNOWN_CODE)
    if device.claimed_at is not None:
        _refuse(ClaimRefusal.ALREADY_SPENT, device_id=device.id)
    if claim_codes.has_expired(device.claim_code_expires_at, at=now):
        _refuse(ClaimRefusal.EXPIRED, device_id=device.id)
    if not await _project_exists(db, project_id):
        _refuse(ClaimRefusal.UNKNOWN_PROJECT, device_id=device.id)

    spent = await db.execute(
        update(Device)
        .where(Device.id == device.id, Device.claimed_at.is_(None))
        .values(project_id=project_id, claimed_at=now)
    )
    if spent.rowcount != 1:
        _refuse(ClaimRefusal.ALREADY_SPENT, device_id=device.id)

    if commit:
        await db.commit()
    await db.refresh(device)
    return device
