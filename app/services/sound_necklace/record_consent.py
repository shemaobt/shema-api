from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.sound_necklace import AuditEvent, ConsentType, SnConsent, SnSession
from app.services.sound_necklace.record_audit_event import record_audit_event


async def record_consent(
    db: AsyncSession, session_id: str, consent_type: ConsentType, confirmed_by: str
) -> SnConsent:
    """Record a consent as evidence of a lawful basis (§12), or re-confirm one.

    Idempotent per (session, type): a second confirmation updates the record rather
    than stacking another one, and names whoever confirmed it this time. Note what that
    means, because it is the record's one weakness: re-confirming REPLACES the previous
    attester and timestamp. The key is idempotent, the value is not.

    ``confirmed_at`` is assigned here rather than left to ``onupdate=func.now()``. A
    re-confirmation of an unchanged record changes no other column, and the ORM emits
    no UPDATE at all when nothing is dirty — the timestamp would silently stay at the
    first confirmation. The one thing this record must never get wrong is when it was
    confirmed.

    It commits, and that is not a free choice: routers in this repo may not, so the
    explicit ``POST /consent`` route needs the write persisted here — every other
    write-service in the module commits for the same reason. Called mid-transaction from
    ``create_session`` the same commit closes that transaction too, so the session, its
    state row and the consent land together.
    """
    record = await db.get(SnConsent, (session_id, consent_type))
    if record is None:
        record = SnConsent(session_id=session_id, type=consent_type)
        db.add(record)
    record.confirmed_by = confirmed_by
    record.confirmed_at = datetime.now(UTC)

    session = await db.get(SnSession, session_id)
    if session is None:
        # Unreachable: the route 404s on get_session first, create_session just flushed
        # it, and the consent's own FK is NOT NULL. Raise rather than skip — a silent skip
        # would drop the boolean sync and the audit trail this function promises, and the
        # audit below reads session.project_id anyway.
        raise NotFoundError("Session not found")

    if consent_type is ConsentType.PIPELINE_USE:
        # Keep the session's write-only boolean from contradicting the record — two
        # columns claiming the same fact must not disagree. (The SPA reads its own copy
        # out of the state document; no response carries this one.)
        session.pipeline_consent = True

    # Filing a consent is a facilitator action on protected material, so it leaves a trail
    # of its own (§12) — the record says what was agreed, this says who filed it.
    await record_audit_event(
        db,
        event=AuditEvent.CONSENT_RECORDED,
        user_id=confirmed_by,
        project_id=session.project_id,
        resource_ref=consent_type.value,
        session_id=session_id,
    )

    await db.commit()
    return record
