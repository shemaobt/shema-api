from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRRelease, IRSegment, IRSession
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
    unheard_parts,
)
from app.services.internalization_room.check_block import check_status, standing_state
from app.services.internalization_room.forced import was_forced
from app.services.internalization_room.re_recorded_sentences import the_awaited_sentence
from app.services.internalization_room.segments import (
    final_segments,
    retired_segments,
    stale_segments,
    told_back,
)
from app.services.internalization_room.sessions import back_translation_of
from app.services.internalization_room.stretch_numbers import stretch_numbers
from app.services.internalization_room.take_downloads import keys_of_the_takes
from app.services.internalization_room.takes import current_parts, takes_of


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
    numbers = await stretch_numbers(db, session)
    stretches = await final_segments(db, session.id, takes)
    stale = await stale_segments(db, session.id, takes)
    retired = await retired_segments(db, session.id)
    told = told_back(stretches)
    said = nuances_said(telling_back.checks)
    parts = current_parts(takes)
    keys = keys_of_the_takes(takes)
    take_of = {row.id: row.take_id for row in (*stretches, *stale, *retired)}
    retold = {row.superseded_by_id for row in retired if row.superseded_by_id and row.transcript}
    awaited = await the_awaited_sentence(db, session)

    def _part_of(segment_id: str | None) -> str | None:
        take_id = take_of.get(segment_id) if segment_id else None
        return keys.get(take_id) if take_id else None

    def _frase(stretch: IRSegment, transcript: str, *, is_stale: bool) -> SessionRetroFrase:
        number = numbers.get(stretch.id)
        return SessionRetroFrase(
            frase=number,
            segment_id=stretch.id,
            take_id=stretch.take_id,
            scene=keys.get(stretch.take_id),
            starts_ms=stretch.starts_ms,
            ends_ms=stretch.ends_ms,
            pass_number=stretch.pass_number,
            transcript=transcript,
            stale=is_stale,
            bridge_take_id=stretch.bridge_take_id,
            awaiting_sentence_id=(
                awaited.sentence_id if awaited and awaited.segment_id == stretch.id else None
            ),
            supersedes=number if stretch.id in retold else None,
        )

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
        heard_complete=not unheard_parts(telling_back, parts, stretches),
        findings=[
            SessionRetroFinding(
                kind=_her_kind(finding),
                frase=finding_frase(
                    finding,
                    telling_back.analysed_segment_ids,
                    telling_back.analysed_frases,
                    numbers,
                ),
                scene=_part_of(finding.segment_id),
            )
            for finding in telling_back.findings
        ],
        nuances=[
            SessionRetroNuance(
                frase=numbers.get(nuance.segment_id),
                said=said_before(nuance, said, told),
                scene=keys.get(nuance.take_id),
            )
            for nuance in telling_back.nuances
        ],
        release_check=approved.release_check if approved else None,
        frases=[
            *(
                _frase(row, row.transcript, is_stale=False)
                for row in stretches
                if row.transcript is not None
            ),
            *(
                _frase(row, row.transcript, is_stale=True)
                for row in stale
                if row.transcript is not None
            ),
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
