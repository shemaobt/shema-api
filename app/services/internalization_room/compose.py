"""Rebuilding the recording of the passage when one stretch of it was recorded again.

The room's long correction already worked: the team records the stretch again, that recording
is kept like any other, and the stretch comes to be a slice of it. What it left behind was a
passage nobody could play — the corrected minute in one file, everything around it in another,
so hearing the whole thing meant resolving stretch by stretch and stitching by hand. Every
reader downstream had to know how, and the app had to know first.

So the passage is rebuilt: the recording the stretch lived in, with the corrected audio put
where the old stretch was, kept as a rehearsal recording of its own. Every stretch that still
counts becomes a slice of *that* file — the ones before the correction where they were, the
ones after it moved by however much the passage grew or shrank.

**This does not weaken the rule the segment exists for.** A stretch is still a slice of one
immutable file, never a position over a concatenated passage. What changes is which file, and
it changes for every stretch at once, in one place, on the one occasion the audio underneath
them all was rebuilt.

The rebuilding needs an encoder in a subprocess and two round trips to a bucket, and neither
is allowed to cost the team their correction — see `recompose_passage`.
"""

from __future__ import annotations

import asyncio
import logging
import tempfile
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.internalization_room import IRSegment, IRSession, IRTake, IRTakeKind
from app.services.internalization_room.segments import current_segments
from app.services.internalization_room.takes import (
    AUDIO_MIME,
    store_take,
    take_bytes,
    take_in_session,
)

logger = logging.getLogger(__name__)

#: What a rebuilt passage is called among a session's recordings, so a reader of the packet can
#: tell a recording the team made from one the room assembled out of them.
COMPOSED_SCOPE = "composed"

#: One sample rate and one channel layout imposed on both sides. The corrected stretch is
#: recorded on another day and sometimes another device, and concatenating two streams that
#: disagree about either gives a file that decodes to noise from the join onwards.
SAMPLE_RATE = 44100
CHANNEL_LAYOUT = "mono"

#: Long enough for a passage of several minutes on the smallest machine that runs this, short
#: enough that a wedged encoder does not hold the request open until the client gives up.
FFMPEG_SECONDS = 120


async def compose_passage(
    original: bytes,
    corrected: bytes,
    *,
    starts_ms: int,
    ends_ms: int,
    corrected_starts_ms: int = 0,
    corrected_ends_ms: int | None = None,
) -> bytes:
    """``original`` with ``[starts_ms, ends_ms)`` taken out and ``corrected`` put in its place.

    Both sides are addressed the way every stretch in this room is addressed — a slice of a
    file, never a file. The correction defaults to the whole of its own recording because that
    is what the tablet records for it, but it does not have to be: an app that trims the
    silence off its own recording sends a stretch shorter than the file holding it, and what
    goes into the passage has to be that stretch. Splicing the whole recording while the
    addresses move by the stretch would misaddress everything after it by the difference, in
    silence, and compound it on the correction after that.

    Three pieces concatenated: what came before the stretch, the whole of the new recording,
    and what came after. Half-open on the same reading the stretches themselves use, so the
    millisecond at ``ends_ms`` is the first one kept on the far side and no audio is counted
    twice or dropped.

    Re-encoded rather than copied. The recordings are AAC, and a cut in AAC almost never lands
    on a frame boundary — copying the stream would move the join by up to a frame in each
    direction and leave the click there for the team to hear. Re-encoding costs a pass over
    audio nobody is waiting on and is the only way the arithmetic above is the arithmetic that
    comes out.

    An empty head or an empty tail needs no special case: correcting the first stretch or the
    last one is the common thing, and ``concat`` takes a piece of no duration in its stride.
    Measured on the encoder in the image rather than assumed.

    The bytes go through files. `mp4` cannot be written to a pipe — the container's index is
    written after the audio and then seeked back over — so an encoder pointed at stdout answers
    with a refusal rather than a file.
    """
    with tempfile.TemporaryDirectory(prefix="ir-passagem-") as workspace:
        room = Path(workspace)
        passage = room / "passagem.m4a"
        mend = room / "correcao.m4a"
        rebuilt = room / "refeita.m4a"
        passage.write_bytes(original)
        mend.write_bytes(corrected)

        shaped = f"aformat=sample_rates={SAMPLE_RATE}:channel_layouts={CHANNEL_LAYOUT}"
        await _ffmpeg(
            "-i",
            str(passage),
            "-i",
            str(mend),
            "-filter_complex",
            (
                f"[0:a]{_atrim(0, starts_ms)},asetpts=PTS-STARTPTS,{shaped}[a0];"
                f"[1:a]{_atrim(corrected_starts_ms, corrected_ends_ms)},"
                f"asetpts=PTS-STARTPTS,{shaped}[a1];"
                f"[0:a]{_atrim(ends_ms, None)},asetpts=PTS-STARTPTS,{shaped}[a2];"
                "[a0][a1][a2]concat=n=3:v=0:a=1[out]"
            ),
            "-map",
            "[out]",
            "-c:a",
            "aac",
            "-f",
            "mp4",
            str(rebuilt),
        )
        return rebuilt.read_bytes()


def _atrim(starts_ms: int, ends_ms: int | None) -> str:
    """``atrim`` over milliseconds, which the filter itself counts in seconds."""
    if ends_ms is None:
        return f"atrim=start={starts_ms / 1000:.3f}"
    return f"atrim=start={starts_ms / 1000:.3f}:end={ends_ms / 1000:.3f}"


async def _ffmpeg(*arguments: str) -> None:
    process = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        *arguments,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        _, complaint = await asyncio.wait_for(process.communicate(), timeout=FFMPEG_SECONDS)
    except TimeoutError:
        process.kill()
        await process.wait()
        raise
    if process.returncode != 0:
        raise RuntimeError(f"ffmpeg refused to rebuild the passage: {complaint.decode()}")


async def recompose_passage(
    db: AsyncSession,
    session: IRSession,
    *,
    device_id: str,
    replaced: IRSegment,
    corrected: IRTake,
    version: IRSegment,
) -> IRTake | None:
    """Rebuild the passage under a stretch just re-recorded, or answer that it was not rebuilt.

    Only when the mother tongue actually moved to another recording. A new version pointing at
    the same file is the team explaining the same audio again, and there is nothing to rebuild:
    the encoder would be spent to hand them a second copy of the file they already have.

    **A rebuilding that cannot be done is not a failed correction.** The encoder is a
    subprocess and the recordings live in a bucket, so the ways this can go wrong are somebody
    else's outage and a machine without a tool. The correction itself is already written and
    already the team's; losing it to either would ask a team who cannot read to record the
    stretch a third time, over a screen that could not tell them why. So everything below the
    correction is caught here, at the boundary where the outside world is, and the answer says
    the passage was not rebuilt — which is the app's cue to go on playing stretch by stretch,
    the way it did before any of this. The warning names the session and the stretch, because
    a rebuilding nobody notices failing is a passage that quietly stops being one file.

    Broad on purpose. A defect of ours here costs the team exactly what an absent encoder does,
    and the stack trace goes to the log rather than into the room.

    A database that failed part-way is the one that needs more than catching. It leaves the
    session refusing every statement until somebody rolls it back, and the very next thing the
    caller does is read the stretches to answer the team — so without the rollback the fail-open
    is a 500, and the retry after it is refused as a stretch that no longer counts, because the
    correction was committed before any of this began. The refresh is the other half: rolling
    back expires everything the session was holding, and the caller is still holding the session
    row. Only on that branch — an unconditional rollback would expire the caller's world on the
    ordinary failure, which is a missing encoder, and turn the rare defect into a certain one.
    """
    if replaced.take_id == corrected.id:
        return None

    where = (session.id, replaced.id)
    try:
        rebuilt = await _rebuild(
            db,
            session,
            device_id=device_id,
            replaced=replaced,
            corrected=corrected,
            version=version,
        )
    except SQLAlchemyError:
        await db.rollback()
        await db.refresh(session)
        _not_rebuilt(*where)
        return None
    except Exception:
        _not_rebuilt(*where)
        return None

    await _readdress(db, session, rebuilt=rebuilt, replaced=replaced, version=version)
    return rebuilt


def _not_rebuilt(session_id: str, segment_id: str) -> None:
    """Say which session and which stretch, because nobody in the room can.

    A rebuilding that fails quietly is a passage that stops being one recording with nothing
    saying so: the team is answered, the correction is theirs, and the only sign left is here.
    """
    logger.warning(
        "The passage of session %s could not be rebuilt after stretch %s was re-recorded; "
        "the correction stands on its own recording",
        session_id,
        segment_id,
        exc_info=True,
    )


async def _rebuild(
    db: AsyncSession,
    session: IRSession,
    *,
    device_id: str,
    replaced: IRSegment,
    corrected: IRTake,
    version: IRSegment,
) -> IRTake:
    """Fetch both recordings, rebuild the passage out of them, and keep it as a take.

    It takes the placement of the recording it was built from rather than none at all.
    `takes_of` orders the packet on those two columns and reads an absent one as the earliest
    thing in its group, so a rebuilt passage carrying neither would be listed ahead of the
    rehearsal it replaced — the very inversion that ordering exists to prevent.
    """
    original = await take_in_session(db, session.id, replaced.take_id)
    was = await take_bytes(original)
    mend = await take_bytes(corrected)
    if was is None or mend is None:
        raise NotFoundError(
            f"The audio of internalization room take "
            f"{original.id if was is None else corrected.id} is not in storage"
        )

    return await store_take(
        db,
        session_id=session.id,
        device_id=device_id,
        project_id=session.project_id,
        pericope=session.pericope,
        kind=IRTakeKind.ENSAIO,
        scope=COMPOSED_SCOPE,
        audio=await compose_passage(
            was,
            mend,
            starts_ms=replaced.starts_ms,
            ends_ms=replaced.ends_ms,
            corrected_starts_ms=version.starts_ms,
            corrected_ends_ms=version.ends_ms,
        ),
        pass_number=original.pass_number,
        chunk_index=original.chunk_index,
        content_type=AUDIO_MIME,
    )


async def _readdress(
    db: AsyncSession,
    session: IRSession,
    *,
    rebuilt: IRTake,
    replaced: IRSegment,
    version: IRSegment,
) -> None:
    """Point every stretch that still counts at the rebuilt passage, at the time it now sits.

    Not a new version of any of them. A version is what the team does — telling a stretch back
    again, recording it again — and every one of those is a row of its own precisely so the
    earlier one survives. Nothing here is the team doing anything: the same sound, unchanged,
    is at a different offset in a different file because the file was rebuilt around it. Made
    into versions, every neighbour of a correction would stop counting for a reason that has
    nothing to do with the neighbour, the tellings-back would have to be carried across by
    hand — which `capture_segment` refuses outright when the slice moves, and rightly — and
    every address the app is holding would go stale on a correction elsewhere in the passage.

    One rule, applied to all of them: a boundary at or before the start of the corrected
    stretch stays where it is, and one past it moves by the difference the correction made.
    That covers the three positions without naming them — a stretch before the correction does
    not move, one after it moves whole, and one the correction sits inside (a stretch the team
    divided, which is current and is not a leaf) keeps its start and gains the difference.
    """
    started = replaced.starts_ms
    grew = (version.ends_ms - version.starts_ms) - (replaced.ends_ms - replaced.starts_ms)

    def moved(at: int) -> int:
        return at if at <= started else at + grew

    for row in await current_segments(db, session.id):
        if row.id == version.id:
            row.take_id = rebuilt.id
            row.starts_ms = started
            row.ends_ms = moved(replaced.ends_ms)
        elif row.take_id == replaced.take_id:
            row.take_id = rebuilt.id
            row.starts_ms = moved(row.starts_ms)
            row.ends_ms = moved(row.ends_ms)
    await db.commit()
