"""ENG-1166 — a redone verdict never names a stretch that no longer counts.

A **Finding** addresses a stretch, and a stretch stops counting when a **Correction** replaces
it or when its **Part** is recorded again (ADR 0023). A verdict saved after either has to
address only stretches that count, whichever of the three readings produced it and whichever
reading carried a finding forward: the team is sent to the row on their screen, and a finding
on a stretch that is no longer on the row sends them to nothing.

These cases press `terminei` through the route with a scripted analyst and read the findings
the tablet would be handed back. None of them names how a finding is filtered.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSegment, IRSession
from app.services.internalization_room.segments import capture_segment, final_segments
from tests.hard_stretch_harness import FROM_THE_DATABASE
from tests.room_harness import (
    ScriptedAnalyst,
    heard_every_part,
    nothing_is_read_ahead,
    press_terminei,
    record_the_part_again,
    rehearsed_in_parts,
    room_client,
    stored_telling_back,
    tell_back_about,
    the_analyst_is_scripted,
    the_room_speaks,
)

THE_ADDITION = "Rute foi junto"
THE_UNCLEAR = "não deu para ouvir o começo"
THE_RETOLD = "a frase 2, contada de novo"
THE_TOLD_AGAIN = "a parte 2, gravada de novo e contada de volta"


@pytest.fixture(autouse=True)
def _voice(monkeypatch: pytest.MonkeyPatch) -> None:
    the_room_speaks(monkeypatch)
    nothing_is_read_ahead(monkeypatch)


@pytest.fixture()
def analyst(monkeypatch: pytest.MonkeyPatch) -> ScriptedAnalyst:
    return the_analyst_is_scripted(monkeypatch)


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    async with room_client(db_session, monkeypatch) as door:
        yield door


def _addition(chunk: int, note: str = THE_ADDITION) -> dict[str, Any]:
    return {"kind": "addition", "note": note, "chunk": chunk}


def _unclear(chunk: int, note: str = THE_UNCLEAR) -> dict[str, Any]:
    return {"kind": "unclear", "note": note, "chunk": chunk}


async def _finish(client: httpx.AsyncClient, db: AsyncSession, session_id: str) -> dict[str, Any]:
    answered = await press_terminei(
        client, session_id, report=await heard_every_part(db, session_id)
    )
    assert answered.status_code == 200, answered.text
    return dict(answered.json())


async def _standing(db: AsyncSession, session_id: str) -> list[IRSegment]:
    await db.execute(
        select(IRSegment)
        .where(IRSegment.session_id == session_id)
        .execution_options(**FROM_THE_DATABASE)
    )
    return await final_segments(db, session_id)


async def _addressed(db: AsyncSession, session: IRSession) -> list[str | None]:
    return [finding.segment_id for finding in (await stored_telling_back(db, session)).findings]


async def _retell(db: AsyncSession, session: IRSession, stretch: IRSegment) -> IRSegment:
    return await capture_segment(
        db,
        session,
        take_id=stretch.take_id,
        starts_ms=stretch.starts_ms,
        ends_ms=stretch.ends_ms,
        bridge_take_id="retro-de-novo",
        transcript=THE_RETOLD,
        pass_number=stretch.pass_number,
        replaces=stretch,
    )


async def _rerecorded_and_told_again(db: AsyncSession, session: IRSession, part) -> IRSegment:
    fresh = await record_the_part_again(db, session, part, sha256="f" * 64)
    return await tell_back_about(db, session, fresh, transcript=THE_TOLD_AGAIN)


async def test_a_part_recorded_again_leaves_no_finding_on_the_stretch_it_retired(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: ScriptedAnalyst
) -> None:
    """T1, the ticket's sequence: raise on frase 2, record its Part again, tell it back, finish.

    The second reading raises an addition on the new telling, so the case holds a finding that
    has to survive and land on the stretch that counts, not only an empty list.
    """
    session, parts = await rehearsed_in_parts(db_session, 3)
    analyst.readings = [{"findings": [_addition(2)]}]
    await _finish(client, db_session, session.id)
    retired = (await _standing(db_session, session.id))[1]
    assert await _addressed(db_session, session) == [retired.id]

    told_again = await _rerecorded_and_told_again(db_session, session, parts[1])
    analyst.readings = [{"findings": [_addition(2)]}]
    await _finish(client, db_session, session.id)

    assert await _addressed(db_session, session) == [told_again.id]


@pytest.mark.parametrize("resolved", [True, False], ids=["resolved", "unresolved"])
async def test_a_correction_leaves_no_finding_on_the_stretch_it_replaced(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    analyst: ScriptedAnalyst,
    resolved: bool,
) -> None:
    """T2. Two findings on frase 2 that are not a swap; frase 2 is retold; finish.

    Whether the check accepts the retelling or not, the finding that was not the one asked
    about is on a stretch that was replaced, and the verdict must not carry it. The one the
    retelling answered is either gone (resolved) or now on the new stretch (unresolved).
    """
    session, _parts = await rehearsed_in_parts(db_session, 3)
    analyst.readings = [{"findings": [_addition(2), _unclear(2)]}]
    analyst.verification = {"resolved": resolved, "findings": []}
    await _finish(client, db_session, session.id)
    replaced = (await _standing(db_session, session.id))[1]

    retold = await _retell(db_session, session, replaced)
    verdict = await _finish(client, db_session, session.id)

    assert verdict["finding_segment_id"] != replaced.id
    assert replaced.id not in await _addressed(db_session, session)
    assert await _addressed(db_session, session) == ([] if resolved else [retold.id])


async def test_a_list_the_replacement_emptied_still_gets_the_closing_reading(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: ScriptedAnalyst
) -> None:
    """The retelling answers the leading finding; the one left stood on the replaced stretch.

    Empty by a verification, it is not measured until the closing reading has looked at the
    whole passage: the verdict carries what that reading raises and does not bless the passage.
    """
    session, _parts = await rehearsed_in_parts(db_session, 3)
    analyst.readings = [{"findings": [_addition(2), _unclear(2)]}, {"findings": [_addition(3)]}]
    await _finish(client, db_session, session.id)
    await _retell(db_session, session, (await _standing(db_session, session.id))[1])

    verdict = await _finish(client, db_session, session.id)

    assert verdict["checked"] is False
    assert verdict["finding_kind"] == "addition"


@pytest.mark.parametrize("reading", ["whole", "closing", "correction check"])
async def test_whichever_reading_ran_every_saved_finding_addresses_a_stretch_that_counts(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: ScriptedAnalyst, reading: str
) -> None:
    """T3. The Whole reading, the Closing reading and the Correction check each save findings
    that resolve to the stretches standing at that moment — and do save them.
    """
    session, _parts = await rehearsed_in_parts(db_session, 3)
    if reading == "whole":
        analyst.readings = [{"findings": [_addition(1), _unclear(3)]}]
        await _finish(client, db_session, session.id)
    else:
        analyst.readings = [{"findings": [_addition(2)]}]
        if reading == "closing":
            analyst.readings.append({"findings": [_unclear(2)]})
        else:
            analyst.verification = {
                "resolved": True,
                "findings": [{"kind": "unclear", "note": THE_UNCLEAR}],
            }
        await _finish(client, db_session, session.id)
        await _retell(db_session, session, (await _standing(db_session, session.id))[1])
        await _finish(client, db_session, session.id)

    standing = {stretch.id for stretch in await _standing(db_session, session.id)}
    addressed = await _addressed(db_session, session)
    assert addressed
    assert set(addressed) <= standing


async def test_the_analyst_is_shown_only_stretches_that_count(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: ScriptedAnalyst
) -> None:
    """T4. After a Correction and after a Part recorded again, the list it reads holds no
    stretch that was replaced.
    """
    session, parts = await rehearsed_in_parts(db_session, 3)
    analyst.readings = [{"findings": [_addition(2)]}, {"findings": []}]
    await _finish(client, db_session, session.id)
    replaced = (await _standing(db_session, session.id))[1]
    await _retell(db_session, session, replaced)
    await _finish(client, db_session, session.id)
    assert THE_RETOLD in analyst.shown[-1]
    assert replaced.transcript not in analyst.shown[-1]

    again = (await _standing(db_session, session.id))[1]
    await _rerecorded_and_told_again(db_session, session, parts[1])
    await _finish(client, db_session, session.id)
    assert THE_TOLD_AGAIN in analyst.shown[-1]
    assert again.transcript not in analyst.shown[-1]
    assert THE_RETOLD not in analyst.shown[-1]


async def test_a_part_recorded_again_while_the_analyst_reads_is_not_left_a_finding(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: ScriptedAnalyst
) -> None:
    """T5. The upload lands between the analyst's call and the save of what it said.

    The double performs the product's own verb when it is called, so the finding the analyst
    then returns is on a stretch that stopped counting before the verdict was saved.
    """
    session, parts = await rehearsed_in_parts(db_session, 3)
    analyst.readings = [{"findings": [_addition(2)]}]

    async def _the_team_records_part_2_again() -> None:
        await record_the_part_again(db_session, session, parts[1], sha256="f" * 64)

    analyst.on_reading = _the_team_records_part_2_again
    await _finish(client, db_session, session.id)

    standing = {stretch.id for stretch in await _standing(db_session, session.id)}
    assert set(await _addressed(db_session, session)) <= standing
