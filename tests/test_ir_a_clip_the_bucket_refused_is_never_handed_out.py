from __future__ import annotations

from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSession, IRSessionStatus
from app.services.internalization_room import prepare_opening as prepare_opening_module
from app.services.internalization_room.prepare_opening import prepare_opening
from app.services.internalization_room.run_turn import TurnOutcome
from app.services.internalization_room.sessions import get_session
from tests.clip_flight_harness import Elevenlabs, WriteOnceBucket, voice_room_client
from tests.release_harness import PREFIX
from tests.room_harness import (
    played_every_part,
    press_terminei,
    rehearsed_in_parts,
    the_analyst_reads,
)


@pytest.fixture()
def bucket() -> WriteOnceBucket:
    refusing = WriteOnceBucket()
    refusing.refusals = 100
    return refusing


@pytest.fixture()
async def client(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, bucket: WriteOnceBucket
):
    the_analyst_reads(monkeypatch)
    async with voice_room_client(
        db_session, monkeypatch, elevenlabs=Elevenlabs(b"never kept"), bucket=bucket
    ) as c:
        yield c


async def test_the_wheel_is_an_outage_when_the_bucket_keeps_none_of_its_names(
    client: httpx.AsyncClient,
) -> None:
    wheel = await client.get(f"{PREFIX}/books/Ruth/passages", params={"language": "pt"})

    assert wheel.status_code == 502, (
        "a roda entregava endereços de nomes que o bucket nunca guardou, e cada um dava 404"
    )


async def test_a_retro_line_the_bucket_did_not_keep_is_an_outage_not_an_address(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session, (first, _) = await rehearsed_in_parts(db_session, 2)

    answered = await press_terminei(client, session.id, report=played_every_part([first.id]))

    assert answered.status_code == 502, (
        "a fala do retro saía com o endereço de um clipe que não existia em lugar nenhum"
    )


async def test_an_opening_whose_clip_was_not_kept_is_never_prepared(
    client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_session.add(
        IRSession(
            id="panorama-1",
            pericope="OV-Ruth",
            status=IRSessionStatus.IN_PROGRESS,
            messages=[],
            coverage_state={},
            kept_takes={},
            back_translation={},
            language="pt",
        )
    )
    await db_session.commit()

    async def _written(**_: Any) -> TurnOutcome:
        return TurnOutcome(speech="Uma família sai de Belém por falta de comida.", transcript="")

    monkeypatch.setattr(prepare_opening_module, "run_turn", _written)

    await prepare_opening("panorama-1", pericope="P01")

    refreshed = await get_session(db_session, "panorama-1")
    await db_session.refresh(refreshed)
    assert refreshed.prepared_audio_key is None, (
        "a abertura preparada guardava a chave de um clipe que o bucket recusou, e a sessão "
        "abria com um endereço que só daria 404"
    )
