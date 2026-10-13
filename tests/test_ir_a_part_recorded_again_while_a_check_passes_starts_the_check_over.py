"""ENG-1412 — a part recorded again while a check passes still starts the check over.

The takes door reads the session, stores the new recording, and only then retires the part it
replaces: the check starts over and the findings about the old audio leave. It did so on the
telling-back state it read before storing, so a check that landed while the bytes were being
kept was, to the retirement's redo, a `checked` it had not touched and findings it had never
seen — the passage stood checked over a recording nobody will hear again, carrying a finding
about it.

The check lands from a session of its own right after the recording is stored, the way a
`terminei` from the other tablet would.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.internalization_room import takes as takes_api
from app.db.models.internalization_room import IRSegment
from app.services.internalization_room.back_translation import (
    Finding,
    FindingKind,
    Nuance,
    VoicedVerdict,
)
from app.services.internalization_room.segments import current_segments
from app.services.internalization_room.sessions import (
    back_translation_of,
    get_session,
    save_back_translation,
)
from tests.room_harness import (
    rehearsed_in_parts,
    room_client,
    stored_telling_back,
    the_bucket_is_in_memory,
    the_room_speaks,
    upload_a_part,
)


def _nuance_on(stretch: IRSegment, story: str) -> Nuance:
    return Nuance(
        note=story,
        chunk=1,
        segment_id=stretch.id,
        quote="Rute",
        story=story,
        take_id=stretch.take_id,
        starts_ms=stretch.starts_ms,
        ends_ms=stretch.ends_ms,
    )


@pytest.fixture(autouse=True)
def voice(monkeypatch: pytest.MonkeyPatch) -> None:
    the_room_speaks(monkeypatch)


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    the_bucket_is_in_memory(monkeypatch)
    async with room_client(db_session, monkeypatch) as room:
        yield room


async def test_a_part_recorded_again_while_a_check_passes_starts_the_check_over_not_checked(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    rival_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session, (one, two, _three) = await rehearsed_in_parts(db_session, 3)
    standing = {
        stretch.take_id: stretch for stretch in await current_segments(db_session, session.id)
    }
    on_part_one = Finding(kind=FindingKind.UNCLEAR, note="parte um", segment_id=standing[one.id].id)
    on_part_two = Finding(
        kind=FindingKind.ADDITION, note="parte dois", segment_id=standing[two.id].id
    )
    kept = takes_api.store_take

    async def kept_while_a_check_passes(*args: Any, **kwargs: Any) -> Any:
        take = await kept(*args, **kwargs)
        async with rival_factory() as checking_db:
            checking = await get_session(checking_db, session.id)
            state = back_translation_of(checking)
            state.findings = [on_part_one, on_part_two]
            state.checked = True
            state.verdict = VoicedVerdict(clip_key="clipe-1", fixed_line="", used_fail_safe=False)
            await save_back_translation(checking_db, checking, state)
        return take

    monkeypatch.setattr(takes_api, "store_take", kept_while_a_check_passes)

    answered = await upload_a_part(
        client, session.id, part=2, audio=b"a equipe gravou a parte dois outra vez"
    )
    assert answered.status_code == 200, answered.text

    after = await stored_telling_back(db_session, session)
    assert (after.checked, after.verdict) == (False, None), (
        "a retirada refeita sobre a conferência que passou mantinha o checked, e a passagem "
        "ficava conferida sobre uma gravação que ninguém vai ouvir de novo"
    )
    assert [finding.note for finding in after.findings] == ["parte um"], (
        "o achado sobre a parte gravada por cima ficava na lista"
    )


async def test_a_part_recorded_again_while_a_check_passes_takes_that_parts_nuances_with_it(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    rival_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session, (one, two, _three) = await rehearsed_in_parts(db_session, 3)
    standing = {
        stretch.take_id: stretch for stretch in await current_segments(db_session, session.id)
    }
    kept = takes_api.store_take

    async def kept_while_a_check_passes(*args: Any, **kwargs: Any) -> Any:
        take = await kept(*args, **kwargs)
        async with rival_factory() as checking_db:
            checking = await get_session(checking_db, session.id)
            state = back_translation_of(checking)
            state.nuances = [
                _nuance_on(standing[one.id], "um detalhe da parte um"),
                _nuance_on(standing[two.id], "um detalhe da parte dois"),
            ]
            await save_back_translation(checking_db, checking, state)
        return take

    monkeypatch.setattr(takes_api, "store_take", kept_while_a_check_passes)

    answered = await upload_a_part(
        client, session.id, part=2, audio=b"a equipe gravou a parte dois outra vez"
    )
    assert answered.status_code == 200, answered.text

    after = await stored_telling_back(db_session, session)
    assert [nuance.story for nuance in after.nuances] == ["um detalhe da parte um"], (
        "o detalhe sobre a parte gravada por cima ficava na lista, e o arquivo do consultor o "
        "dava como ainda não dito"
    )
