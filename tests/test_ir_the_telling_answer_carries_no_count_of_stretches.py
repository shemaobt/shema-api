from __future__ import annotations

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.internalization_room.segments import final_segments
from tests.release_harness import PREFIX, TABLET
from tests.room_harness import (
    a_piece_still_to_be_told,
    nothing_is_read_ahead,
    rehearsed_in_parts,
    room_client,
    the_bucket_is_in_memory,
    the_transcriber_says,
)


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    async with room_client(db_session, monkeypatch) as door:
        yield door


async def test_the_telling_answer_counts_no_stretches_while_an_untold_piece_stands(
    client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.main import app

    the_bucket_is_in_memory(monkeypatch)
    nothing_is_read_ahead(monkeypatch)
    the_transcriber_says(monkeypatch, ["a segunda parte, contada de volta"])
    session, _parts = await rehearsed_in_parts(db_session, 2)
    first, second = await final_segments(db_session, session.id)
    await a_piece_still_to_be_told(db_session, session, first)

    told = await client.post(
        f"{PREFIX}/sessions/{session.id}/back-translation/chunks",
        headers={"X-Room-Device": TABLET},
        data={
            "take_id": second.take_id,
            "starts_ms": str(second.starts_ms),
            "ends_ms": str(second.ends_ms),
        },
        files={"file": ("trecho.m4a", b"um trecho traduzido", "audio/mp4")},
    )

    assert told.status_code == 200, told.text
    assert "chunks" not in told.json(), (
        "a resposta contava os trechos de pé, os por contar também, e ninguém lia o número"
    )
    reference = app.openapi()["components"]["schemas"]["BackTranslationChunkResponse"]
    assert "chunks" not in reference["properties"], (
        "as referências da API diziam «quantos trechos a passagem tem» sobre um número que"
        " não era o das frases contadas"
    )
