from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRRelease, IRSession
from app.models.internalization_room import (
    RetroKind,
    SessionRetroCheck,
    SessionRetroCheckFinding,
    SessionRetroFinding,
    SessionRetroFrase,
    SessionRetroNuance,
    SessionRetroReopened,
    SessionRetroReopenedFrase,
    SessionRetroResponse,
)
from app.services.internalization_room.approved_draft import approved_draft, stands_on
from app.services.internalization_room.back_translation import (
    Finding,
    finding_frase,
    nuances_said,
    said_before,
)
from app.services.internalization_room.check_block import check_status, standing_state
from app.services.internalization_room.forced import was_forced
from app.services.internalization_room.retroverification import retroverification_file
from app.services.internalization_room.segments import final_segments, told_back
from app.services.internalization_room.sessions import back_translation_of
from app.services.internalization_room.takes import current_parts, part_keys, takes_of


def _her_kind(finding: Finding) -> RetroKind:
    return "silence" if finding.fills_silence else finding.kind.value


def _reopened(release: IRRelease) -> SessionRetroReopened:
    return SessionRetroReopened(
        version=release.version,
        approved_at=release.approved_at.isoformat(),
        frases=[
            SessionRetroReopenedFrase(
                frase=one.get("frase"),
                take_id=one["take_id"],
                scene=one.get("scene"),
                starts_ms=one["starts_ms"],
                ends_ms=one["ends_ms"],
            )
            for one in (release.packet.get("back_translation") or {}).get("segments", [])
        ],
    )


async def retro_of(db: AsyncSession, session: IRSession) -> SessionRetroResponse:
    takes = await takes_of(db, session.id)
    telling_back = await standing_state(db, session.id, back_translation_of(session), takes)
    approved = await approved_draft(db, session)
    forced = approved is not None and was_forced(approved.forced_by, approved.forced_blockers)
    forced_at = approved.forced_at if approved is not None and forced else None
    record = await retroverification_file(db, session)
    numbers = {one.segment_id: one.frase for one in record.stretches if one.frase is not None}
    told = told_back(await final_segments(db, session.id, takes))
    said = nuances_said(telling_back.checks)
    parts = current_parts(takes)
    keys = part_keys(parts)
    own = await db.scalar(
        select(IRRelease)
        .where(IRRelease.session_id == session.id)
        .order_by(IRRelease.version.desc())
        .limit(1)
    )
    return SessionRetroResponse(
        session_id=session.id,
        status=check_status(telling_back.checked, forced),
        forced_at=forced_at.isoformat() if forced_at else None,
        version=approved.version if approved else None,
        approved_at=approved.approved_at.isoformat() if approved else None,
        heard_complete=all(part.heard for part in record.listening),
        findings=[
            SessionRetroFinding(
                kind=_her_kind(finding),
                frase=finding_frase(finding, telling_back.analysed_segment_ids, numbers),
            )
            for finding in telling_back.findings
        ],
        nuances=[
            SessionRetroNuance(
                frase=numbers.get(nuance.segment_id), said=said_before(nuance, said, told)
            )
            for nuance in telling_back.nuances
        ],
        frases=[
            SessionRetroFrase(
                frase=stretch.frase,
                segment_id=stretch.segment_id,
                take_id=stretch.take_id,
                scene=keys.get(stretch.take_id),
                starts_ms=stretch.starts_ms,
                ends_ms=stretch.ends_ms,
                pass_number=stretch.pass_number,
                transcript=stretch.transcript,
            )
            for stretch in record.stretches
            if stretch.transcript is not None
        ],
        reopened=_reopened(own) if own is not None and not stands_on(own, parts) else None,
        checks=[
            SessionRetroCheck(
                at=check.at.isoformat(),
                outcome=check.outcome,
                conferida=check.conferida,
                spoken=check.spoken,
                findings=[
                    SessionRetroCheckFinding(kind=_her_kind(finding), frase=finding.chunk)
                    for finding in check.findings
                ],
            )
            for check in telling_back.checks
        ],
    )
