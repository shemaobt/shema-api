"""Nothing leaves the room as a stretch with no words in it.

A stretch legitimately has no words for a while: the team re-records the mother tongue under
one, or divides one in two, and what they said about the audio that moved does not carry over.
Inside the room that state is visible and the tablet asks them to tell it again.

In a release it is not visible. A stretch whose text is null does not read downstream as
unfinished — it reads as though the team stood in front of that passage and said nothing, which
is a different claim and a worse one. So the release waits for the words instead of shipping
the silence.

These cases ask only what the room decides: the release is built, or it is refused naming a
blocker. None of them asks which function did the deciding.
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSegment, IRSession, IRTake, IRTakeKind
from app.services.internalization_room.back_translation import BackTranslationState
from app.services.internalization_room.canon.elements import element_keys
from app.services.internalization_room.comprehension.checkpoints import (
    checkpoints_for,
    scene_ids_for,
)
from app.services.internalization_room.comprehension.evidence import (
    EvidenceMethod,
    EvidenceObservation,
    EvidenceResult,
)
from app.services.internalization_room.comprehension.state import ComprehensionState
from app.services.internalization_room.coverage import initial_state, merge
from app.services.internalization_room.release import (
    InternalizationReleaseBlocked,
    build_internalization_release,
)
from app.services.internalization_room.segments import (
    capture_segment,
    divide_segment,
    final_segments,
)
from app.services.internalization_room.sessions import (
    create_session,
    report_playback,
    save_comprehension,
)

P = "P03"
CLIP_MS = 61000
UNTOLD = "untold_stretch"


def _supported_comprehension(pericope: str) -> ComprehensionState:
    return ComprehensionState(
        ledger=[
            EvidenceObservation(
                id=f"ev-{index}",
                unit_id=checkpoint.id,
                probe_id=f"probe-{index}",
                method=EvidenceMethod.MICRO_TELLBACK,
                result=EvidenceResult.DEMONSTRATED,
            )
            for index, checkpoint in enumerate(checkpoints_for(pericope))
        ],
        practiced_scene_ids=scene_ids_for(pericope),
        recording_consent_given=True,
    )


def _rehearsal_take(session_id: str, *, sha256: str) -> IRTake:
    return IRTake(
        session_id=session_id,
        device_id="tablet-1",
        pericope=P,
        kind=IRTakeKind.ENSAIO,
        scope="passagem-inteira",
        storage_key=f"takes/{session_id}/ensaio/{sha256}",
        size_bytes=2048,
        sha256=sha256,
        crc32c="AAAAAAA=",
        content_type="audio/mp4",
    )


async def _told_back_and_read(db: AsyncSession) -> tuple[IRSession, IRTake]:
    """A session standing exactly on the edge of a release, and entitled to one.

    Comprehension supported, consent given, coverage met, the passage rehearsed and told back
    whole, the analyst run over it, the clip played through. Every case below starts here and
    changes one thing.
    """
    session = await create_session(db, pericope=P, bridge_mode="guided_microchecks", language="pt")
    session.coverage_state = merge(initial_state(P), pericope_num=P, engaged=element_keys(P))
    await save_comprehension(db, session, _supported_comprehension(P))
    take = _rehearsal_take(session.id, sha256="a" * 64)
    db.add(take)
    await db.commit()
    told = await capture_segment(
        db,
        session,
        take_id=take.id,
        starts_ms=0,
        ends_ms=CLIP_MS,
        bridge_take_id="retro-1",
        transcript="Noemi voltou com Rute",
    )
    await _the_analyst_has_read(db, session, [told])
    return session, take


async def _the_analyst_has_read(
    db: AsyncSession, session: IRSession, stretches: list[IRSegment]
) -> None:
    """The verdict the team already has, and the report of the clip they already played."""
    await report_playback(
        db,
        session,
        BackTranslationState(
            scope=P,
            checked=True,
            analysed_segment_ids=[stretch.id for stretch in stretches],
        ),
        played_ranges=[[0, CLIP_MS]],
        clip_duration_ms=CLIP_MS,
    )


async def _re_record_the_mother_tongue(
    db: AsyncSession, session: IRSession, stretch: IRSegment
) -> IRSegment:
    """Record the passage again under one stretch, which leaves it waiting to be told.

    The recording moves, so the explanation of the audio nobody will hear again does not come
    with it — `capture_segment` refuses to carry one across, which is the state this is about.
    """
    again = _rehearsal_take(session.id, sha256="b" * 64)
    db.add(again)
    await db.commit()
    return await capture_segment(
        db,
        session,
        take_id=again.id,
        starts_ms=0,
        ends_ms=CLIP_MS,
        replaces=stretch,
    )


async def _tell_it_back(
    db: AsyncSession, session: IRSession, stretch: IRSegment, words: str
) -> IRSegment:
    """Give a waiting stretch its words, over a recording that did not move."""
    return await capture_segment(
        db,
        session,
        take_id=stretch.take_id,
        starts_ms=stretch.starts_ms,
        ends_ms=stretch.ends_ms,
        bridge_take_id="retro-novo",
        transcript=words,
        replaces=stretch,
    )


async def _blockers(db: AsyncSession, session: IRSession) -> list[str]:
    with pytest.raises(InternalizationReleaseBlocked) as refused:
        await build_internalization_release(db, session)
    return refused.value.blockers


@pytest.mark.asyncio
async def test_a_release_is_refused_while_a_stretch_has_no_words(
    db_session: AsyncSession,
) -> None:
    """Case 1. The team re-recorded the mother tongue under a stretch and has not told it back.

    That stretch is current, it is a unit, and it carries nothing the team said. Sent as it is,
    it reaches Refine with null where their words belong.
    """
    session, _ = await _told_back_and_read(db_session)
    standing = (await final_segments(db_session, session.id))[0]

    await _re_record_the_mother_tongue(db_session, session, standing)

    assert await _blockers(db_session, session) == [UNTOLD, "playback_did_not_cover_the_clip"], (
        "duas coisas ficaram por fazer, e nomear só uma manda a equipe voltar duas vezes"
    )


@pytest.mark.asyncio
async def test_dividing_a_stretch_leaves_the_release_waiting_for_both_halves(
    db_session: AsyncSession,
) -> None:
    """The same defect by the route that shows it on its own.

    Hearing two ideas in one stretch and cutting it is the team working. Both pieces are born
    without words, over the same recording as the stretch they came from — so nothing else in
    the list has anything to object to, and the release used to go out carrying two nulls.
    """
    session, _ = await _told_back_and_read(db_session)
    whole = (await final_segments(db_session, session.id))[0]

    await divide_segment(db_session, session, whole, at_ms=30000)

    assert await _blockers(db_session, session) == [UNTOLD]


@pytest.mark.asyncio
async def test_the_refusal_outlives_the_verdict_the_analyst_already_gave(
    db_session: AsyncSession,
) -> None:
    """Case 2. Asking whether the analyst ever ran is not asking about these stretches.

    It ran, on the passage as it stood before the team cut it, and that answer is true forever
    after — so the gate that reads it is satisfied while stretches nobody has explained sit in
    the release. The question that matters is about the words in *this* package.
    """
    session, _ = await _told_back_and_read(db_session)
    whole = (await final_segments(db_session, session.id))[0]

    await divide_segment(db_session, session, whole, at_ms=30000)

    refused = await _blockers(db_session, session)
    assert UNTOLD in refused
    assert "telling_back_never_analysed" not in refused, (
        "a análise já correu uma vez, então esse portão está satisfeito para sempre"
    )
    assert "no_telling_back" not in refused, "e a lista não está vazia, então esse também"


@pytest.mark.asyncio
async def test_a_passage_told_back_whole_still_releases_with_all_its_stretches(
    db_session: AsyncSession,
) -> None:
    """Case 3. Control: every current stretch has words, and the package travels with them."""
    session, take = await _told_back_and_read(db_session)
    await capture_segment(
        db_session,
        session,
        take_id=take.id,
        starts_ms=CLIP_MS,
        ends_ms=CLIP_MS + 9000,
        bridge_take_id="retro-2",
        transcript="e Noemi não disse mais nada",
    )
    await _the_analyst_has_read(db_session, session, await final_segments(db_session, session.id))

    artifact = await build_internalization_release(db_session, session)

    carried = artifact["back_translation"]["segments"]
    assert [one["text"] for one in carried] == [
        "Noemi voltou com Rute",
        "e Noemi não disse mais nada",
    ]


@pytest.mark.asyncio
async def test_a_stretch_told_back_after_its_recording_moved_releases(
    db_session: AsyncSession,
) -> None:
    """Control: a stretch that had no words and now has them is not held against the team.

    It is also what says the refusal is about the stretches that count and not about history —
    the wordless version is still on the session, superseded, and the package carries it as
    such.
    """
    session, _ = await _told_back_and_read(db_session)
    whole = (await final_segments(db_session, session.id))[0]
    head, tail = await divide_segment(db_session, session, whole, at_ms=30000)
    await _tell_it_back(db_session, session, head, "Noemi voltou")
    await _tell_it_back(db_session, session, tail, "e Rute veio com ela")
    await _the_analyst_has_read(db_session, session, await final_segments(db_session, session.id))

    artifact = await build_internalization_release(db_session, session)

    assert artifact["readiness"] == "ready_for_refine"
    assert [one["text"] for one in artifact["back_translation"]["segments"]] == [
        "Noemi voltou",
        "e Rute veio com ela",
    ]


@pytest.mark.asyncio
async def test_several_wordless_stretches_are_one_errand(
    db_session: AsyncSession,
) -> None:
    """Every stretch wordless is one thing wrong, not one thing wrong per stretch.

    A blocker is what the facilitator is handed to act on, so a list that repeats itself is a
    list that reads like several problems and sends them looking for several answers.
    """
    session, _ = await _told_back_and_read(db_session)
    whole = (await final_segments(db_session, session.id))[0]
    head, _tail = await divide_segment(db_session, session, whole, at_ms=30000)
    await divide_segment(db_session, session, head, at_ms=15000)

    refused = await _blockers(db_session, session)

    assert refused.count(UNTOLD) == 1
