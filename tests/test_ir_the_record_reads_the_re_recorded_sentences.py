from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room import segments as segments_api
from app.core.config import get_settings
from app.db.models.auth import App
from app.db.models.project import Project
from app.services.internalization_room import takes as takes_service
from tests.baker import make_app, make_role
from tests.device_harness import TABLET_TEAM
from tests.hard_stretch_harness import MemoryStore
from tests.release_harness import APP_KEY, PREFIX, at_the_desk
from tests.room_harness import room_client, the_bucket_is_in_memory
from tests.sentence_harness import part_audio, re_record, rehearsed_in_wav, spoken

SCENE_TWO = [[(0, 1000)], [(0, 42000), (42000, 49000), (49000, 50000)]]
STORAGE = "https://storage.example/balde-de-teste/"


@pytest.fixture()
def store(monkeypatch: pytest.MonkeyPatch) -> MemoryStore:
    return the_bucket_is_in_memory(monkeypatch)


@pytest.fixture()
def signed(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _signed_download(bucket: str, key: str, **_: Any) -> str:
        return f"https://storage.example/{bucket}/{key}"

    monkeypatch.setattr(get_settings(), "gcs_platform_bucket", "balde-de-teste", raising=False)
    monkeypatch.setattr(takes_service, "generate_signed_download_url", _signed_download)


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, store: MemoryStore):
    async with room_client(db_session, monkeypatch) as door:
        yield door


@pytest.fixture()
async def room_app(db_session: AsyncSession) -> App:
    app = await make_app(db_session, app_key=APP_KEY, name="Internalization Room")
    await make_role(db_session, app.id, role_key="facilitator", label="Facilitator", is_system=True)
    return app


def desk_re_recorded(session_id: str) -> str:
    return f"{PREFIX}/facilitator/sessions/{session_id}/re-recorded-sentences"


def desk_take_audio(take_id: str) -> str:
    return f"{PREFIX}/facilitator/takes/{take_id}/audio"


def desk_sentence_audio(session_id: str, sentence_id: str) -> str:
    return f"{desk_re_recorded(session_id)}/{sentence_id}/audio"


async def _what_plays(
    client: httpx.AsyncClient, store: MemoryStore, url: str, desk: dict[str, str]
) -> bytes:
    answered = await client.get(url, headers=desk, follow_redirects=False)
    assert answered.status_code == 307, answered.text
    location = answered.headers["location"]
    assert location.startswith(STORAGE), location
    return store.objects.get(location.removeprefix(STORAGE), b"")


async def _the_desk(db: AsyncSession, room_app: App) -> dict[str, str]:
    team = await db.get(Project, TABLET_TEAM)
    assert team is not None
    desk, _facilitator = await at_the_desk(db, room_app, team)
    return desk


async def _the_sentences(
    client: httpx.AsyncClient, session_id: str, desk: dict[str, str]
) -> list[dict[str, Any]]:
    answered = await client.get(desk_re_recorded(session_id), headers=desk)
    assert answered.status_code == 200, answered.text
    return answered.json()["sentences"]


async def test_a_sentence_of_scene_two_recorded_again_reads_with_where_it_was_and_where_it_went(
    client: httpx.AsyncClient, db_session: AsyncSession, store: MemoryStore, room_app: App
) -> None:
    session, (_, part_two), (_, (_, middle, _)) = await rehearsed_in_wav(
        db_session, store, SCENE_TWO
    )
    desk = await _the_desk(db_session, room_app)

    before = datetime.now(UTC)
    laid = await re_record(client, session.id, middle.id, spoken(8.6))
    after = datetime.now(UTC)
    assert laid.status_code == 200, laid.text

    (sentence,) = await _the_sentences(client, session.id, desk)
    assert {
        key: sentence[key]
        for key in (
            "sentence_id",
            "segment_id",
            "scene",
            "starts_ms",
            "replaced_ends_ms",
            "ends_ms",
            "previous_take_id",
        )
    } == {
        "sentence_id": "sentence-0001",
        "segment_id": middle.id,
        "scene": "S2",
        "starts_ms": 42000,
        "replaced_ends_ms": 49000,
        "ends_ms": 51000,
        "previous_take_id": part_two.id,
    }, "a frase regravada não chegava ao registro com o trecho de antes e o de depois"
    assert before <= datetime.fromisoformat(sentence["at"]) <= after, (
        "o registro não dizia quando a frase foi regravada"
    )


async def test_the_sentence_as_the_team_recorded_it_plays_the_very_audio_they_sent(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    store: MemoryStore,
    room_app: App,
    signed: None,
) -> None:
    session, _, (_, (_, middle, _)) = await rehearsed_in_wav(db_session, store, SCENE_TWO)
    desk = await _the_desk(db_session, room_app)
    sent = spoken(8.6)
    await re_record(client, session.id, middle.id, sent, sentence_id="sentence-0042")

    (sentence,) = await _the_sentences(client, session.id, desk)
    played = await _what_plays(
        client, store, desk_sentence_audio(session.id, sentence["sentence_id"]), desk
    )

    assert played == sent, "o botão tocava outra coisa que não a frase como a equipe gravou"


async def test_how_it_was_before_plays_the_part_as_the_team_first_recorded_it(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    store: MemoryStore,
    room_app: App,
    signed: None,
) -> None:
    session, _, (_, (_, middle, _)) = await rehearsed_in_wav(db_session, store, SCENE_TWO)
    desk = await _the_desk(db_session, room_app)
    await re_record(client, session.id, middle.id, spoken(8.6))

    (sentence,) = await _the_sentences(client, session.id, desk)
    played = await _what_plays(client, store, desk_take_audio(sentence["previous_take_id"]), desk)

    assert played == part_audio(2, 50000), (
        "«como era antes» tocava a parte já com a frase nova, ou nada"
    )


async def test_a_sentence_still_awaiting_its_translation_names_its_frase_until_it_is_told_again(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    store: MemoryStore,
    room_app: App,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _heard(*_: Any, **__: Any) -> str:
        return "a frase nova traduzida"

    monkeypatch.setattr(segments_api, "heard", _heard)
    session, _, (_, (_, middle, _)) = await rehearsed_in_wav(db_session, store, SCENE_TWO)
    desk = await _the_desk(db_session, room_app)
    laid = await re_record(client, session.id, middle.id, spoken(8.6))
    (where,) = [one for one in laid.json()["segments"] if one["segment_id"] == middle.id]

    (awaiting,) = await _the_sentences(client, session.id, desk)
    told = await client.post(
        f"{PREFIX}/sessions/{session.id}/segments/{middle.id}/replace",
        data={
            "take_id": where["take_id"],
            "starts_ms": str(where["starts_ms"]),
            "ends_ms": str(where["ends_ms"]),
        },
        files={"file": ("trecho.m4a", b"a equipe traduziu a frase nova", "audio/mp4")},
    )
    assert told.status_code == 200, told.text
    (translated,) = await _the_sentences(client, session.id, desk)

    assert awaiting["awaiting_frase"] == 3, "o registro não dizia que a frase 3 aguarda tradução"
    assert translated["awaiting_frase"] is None, (
        "a frase traduzida de novo continuava aguardando no registro"
    )


async def test_a_frase_recorded_again_twice_awaits_only_under_its_latest_sentence(
    client: httpx.AsyncClient, db_session: AsyncSession, store: MemoryStore, room_app: App
) -> None:
    session, _, (_, (_, middle, _)) = await rehearsed_in_wav(db_session, store, SCENE_TWO)
    desk = await _the_desk(db_session, room_app)
    await re_record(client, session.id, middle.id, spoken(8.6), sentence_id="sentence-0001")
    again = await re_record(client, session.id, middle.id, spoken(1.6), sentence_id="sentence-0002")
    assert again.status_code == 200, again.text

    sentences = await _the_sentences(client, session.id, desk)

    assert [(one["sentence_id"], one["awaiting_frase"]) for one in sentences] == [
        ("sentence-0001", None),
        ("sentence-0002", 3),
    ], "a primeira frase regravada também dizia que aguarda tradução"
