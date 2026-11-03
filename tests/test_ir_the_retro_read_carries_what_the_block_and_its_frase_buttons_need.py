"""ENG-2141 — the session retro read carries everything the record's «Retroverificação» block and
its frase buttons need, and a take or a re-recorded sentence answers its signed address.

The Desk draws the block from one read. A part recorded again keeps its told stretches listed
stale after the standing ones, numbered as the team's tablet draws them; each frase names its
Portuguese take, the sentence it awaits and the frase it retells; the standing version carries
its release check. Every audio the block plays answers `{url, expires_at}`, a player that sends
no headers cannot follow the 307 doors the gate stands in front of.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room import segments as segments_api
from app.core.config import get_settings
from app.db.models.auth import App
from app.db.models.internalization_room import IRSession, IRTake, IRTakeKind
from app.db.models.project import Project
from app.main import app as the_app
from app.services.auth.issue_tokens import issue_tokens
from app.services.internalization_room import takes as takes_service
from app.services.internalization_room.back_translation import (
    BackTranslationState,
    CheckRound,
    Finding,
    FindingKind,
    Nuance,
)
from app.services.internalization_room.segments import capture_segment, current_segments
from app.services.internalization_room.sessions import (
    back_translation_of,
    get_session,
    save_back_translation,
)
from tests.baker import grant_room_app_role, make_app, make_role, make_user
from tests.device_harness import TABLET_TEAM
from tests.hard_stretch_harness import MemoryStore
from tests.release_harness import (
    APP_KEY,
    PREFIX,
    TABLET,
    P,
    a_claimed_device,
    at_the_desk,
    desk_release,
    ready_session,
    releases_of,
    team_headers,
    team_release,
    the_one_part_of,
    the_part_recorded_again,
)
from tests.room_harness import (
    PART_MS,
    a_piece_still_to_be_told,
    rehearsed_in_parts,
    rehearsed_in_parts_of,
    room_client,
    the_bucket_is_in_memory,
    the_room_speaks,
    the_transcriber_says,
    upload_a_part,
)
from tests.sentence_harness import part_audio, re_record, rehearsed_in_wav, spoken

SCENE_TWO = [[(0, 1000)], [(0, 42000), (42000, 49000), (49000, 50000)]]
STORAGE = "https://storage.example/balde-de-teste/"
NEW_AUDIO = b"a equipe gravou esta parte outra vez"
RETELLING = b"a equipe contou a parte regravada"
THE_ANALYSTS_NOTE = "NOTA-DO-ANALISTA-2141"
THE_TEAMS_QUOTE = "CITACAO-DA-EQUIPE-2141"
THE_MAPS_STORY = "HISTORIA-DO-MAPA-2141"


@pytest.fixture(autouse=True)
def voice(monkeypatch: pytest.MonkeyPatch) -> None:
    the_room_speaks(monkeypatch)


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
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    async def _heard(*_: Any, **__: Any) -> str:
        return "a parte contada de novo"

    monkeypatch.setattr(segments_api, "heard", _heard)
    the_transcriber_says(monkeypatch, [])
    async with room_client(db_session, monkeypatch) as door:
        yield door


@pytest.fixture()
async def room_app(db_session: AsyncSession) -> App:
    app = await make_app(db_session, app_key=APP_KEY, name="Internalization Room")
    await make_role(db_session, app.id, role_key="facilitator", label="Facilitator", is_system=True)
    await make_role(db_session, app.id, role_key="consultant", label="Consultant", is_system=True)
    return app


@pytest.fixture()
async def consultant(db_session: AsyncSession, room_app: App) -> dict[str, str]:
    user = await make_user(db_session, email="consultora@example.com")
    await grant_room_app_role(db_session, user.id, "consultant")
    access, _refresh = await issue_tokens(db_session, user)
    return {"Authorization": f"Bearer {access}"}


def desk_retro_read(session_id: str) -> str:
    return f"{PREFIX}/facilitator/sessions/{session_id}/retro"


def take_address(take_id: str) -> str:
    return f"{PREFIX}/facilitator/takes/{take_id}/address"


def take_audio(take_id: str) -> str:
    return f"{PREFIX}/facilitator/takes/{take_id}/audio"


def sentence_address(session_id: str, sentence_id: str) -> str:
    return f"{PREFIX}/facilitator/sessions/{session_id}/re-recorded-sentences/{sentence_id}/address"


def sentence_audio(session_id: str, sentence_id: str) -> str:
    return f"{PREFIX}/facilitator/sessions/{session_id}/re-recorded-sentences/{sentence_id}/audio"


async def _the_desk(db: AsyncSession, room_app: App) -> dict[str, str]:
    team = await db.get(Project, TABLET_TEAM)
    assert team is not None
    desk, _facilitator = await at_the_desk(db, room_app, team)
    return desk


async def _retro(client: httpx.AsyncClient, session_id: str, desk: dict[str, str]) -> dict:
    answered = await client.get(desk_retro_read(session_id), headers=desk)
    assert answered.status_code == 200, answered.text
    return answered.json()


async def _frases(client: httpx.AsyncClient, session_id: str, desk: dict[str, str]) -> list[dict]:
    return (await _retro(client, session_id, desk))["frases"]


async def _read_asking_for_stale(client: httpx.AsyncClient, session_id: str) -> list[dict]:
    read = await client.get(f"{PREFIX}/sessions/{session_id}", params={"include_stale": "true"})
    assert read.status_code == 200, read.text
    return read.json()["back_translation"]["segments"]


async def _tell_again(
    client: httpx.AsyncClient,
    session_id: str,
    segment_id: str,
    *,
    take_id: str,
    starts_ms: int = 0,
    ends_ms: int = PART_MS,
    audio: bytes = RETELLING,
) -> httpx.Response:
    told = await client.post(
        f"{PREFIX}/sessions/{session_id}/segments/{segment_id}/replace",
        headers={"X-Room-Device": TABLET},
        data={"take_id": take_id, "starts_ms": str(starts_ms), "ends_ms": str(ends_ms)},
        files={"file": ("de-novo.m4a", audio, "audio/mp4")},
    )
    assert told.status_code == 200, told.text
    return told


async def _told_again(
    client: httpx.AsyncClient, session_id: str, segment_id: str, laid: httpx.Response
) -> None:
    (where,) = [one for one in laid.json()["segments"] if one["segment_id"] == segment_id]
    await _tell_again(
        client,
        session_id,
        segment_id,
        take_id=where["take_id"],
        starts_ms=where["starts_ms"],
        ends_ms=where["ends_ms"],
        audio=b"a equipe traduziu a frase nova",
    )


async def _the_sentences(
    client: httpx.AsyncClient, session_id: str, desk: dict[str, str]
) -> list[dict[str, Any]]:
    answered = await client.get(
        f"{PREFIX}/facilitator/sessions/{session_id}/re-recorded-sentences", headers=desk
    )
    assert answered.status_code == 200, answered.text
    return answered.json()["sentences"]


async def _part_recorded_again(client: httpx.AsyncClient, session_id: str, part: int) -> str:
    again = await upload_a_part(client, session_id, part=part, audio=NEW_AUDIO)
    assert again.status_code == 200, again.text
    return again.json()["take_id"]


def _stored_under(store: MemoryStore, url: str) -> bytes | None:
    assert url.startswith(STORAGE), url
    return store.objects.get(url.removeprefix(STORAGE))


async def _address(client: httpx.AsyncClient, url: str, headers: dict[str, str]) -> dict[str, Any]:
    answered = await client.get(url, headers=headers)
    assert answered.status_code == 200, answered.text
    return answered.json()


async def _retro_takes(db: AsyncSession, session_id: str) -> list[IRTake]:
    found = await db.scalars(
        select(IRTake).where(IRTake.session_id == session_id, IRTake.kind == IRTakeKind.RETRO)
    )
    return list(found)


def _blanked(body: Any, *ids: str) -> str:
    text = json.dumps(body)
    for value in ids:
        text = text.replace(value, "<id>")
    return text


async def test_a_part_recorded_again_lists_its_stale_frase_after_the_told_ones_numbered_as_the_teams_list(  # noqa: E501
    client: httpx.AsyncClient, db_session: AsyncSession, store: MemoryStore, room_app: App
) -> None:
    session, (one, two, three) = await rehearsed_in_parts(db_session, 3)
    by_part = {row.take_id: row.id for row in await current_segments(db_session, session.id)}
    desk = await _the_desk(db_session, room_app)
    await _part_recorded_again(client, session.id, 2)

    tablet = await _read_asking_for_stale(client, session.id)
    frases = await _frases(client, session.id, desk)

    served = [(f["segment_id"], f["frase"], f["stale"]) for f in frases]
    assert served == [(row["segment_id"], row["frase"], row["stale"]) for row in tablet], (
        "o retro não listava as frases como a tablet da equipe as desenha"
    )
    assert served == [
        (by_part[one.id], 1, False),
        (by_part[three.id], 3, False),
        (by_part[two.id], 2, True),
    ], "a frase da parte regravada sumia do retro, ou vinha com outro número"
    (stale,) = [f for f in frases if f["stale"]]
    assert stale["scene"] == "S2", "a frase velha da parte 2 não dizia que é da parte 2"
    assert stale["take_id"] == two.id, "a frase velha não apontava a gravação de antes da parte 2"


async def test_two_told_stale_frases_of_one_part_never_repeat_a_standing_number(
    client: httpx.AsyncClient, db_session: AsyncSession, store: MemoryStore, room_app: App
) -> None:
    session, _parts = await rehearsed_in_parts_of(db_session, [1, 4, 1])
    desk = await _the_desk(db_session, room_app)
    await _part_recorded_again(client, session.id, 2)

    frases = await _frases(client, session.id, desk)

    assert [(f["frase"], f["stale"]) for f in frases] == [
        (1, False),
        (6, False),
        (2, True),
        (3, True),
        (4, True),
        (5, True),
    ], "uma frase velha chegava sem número ou repetia o de uma que está de pé"


async def test_a_stale_piece_nobody_told_is_not_a_frase_of_the_read(
    client: httpx.AsyncClient, db_session: AsyncSession, store: MemoryStore, room_app: App
) -> None:
    session, _parts = await rehearsed_in_parts(db_session, 3)
    standing = await current_segments(db_session, session.id)
    untold = await a_piece_still_to_be_told(db_session, session, standing[1])
    desk = await _the_desk(db_session, room_app)
    await _part_recorded_again(client, session.id, 2)
    tablet_stale = [
        row["segment_id"]
        for row in await _read_asking_for_stale(client, session.id)
        if row["stale"]
    ]
    assert untold.id in tablet_stale

    frases = await _frases(client, session.id, desk)

    assert untold.id not in [f["segment_id"] for f in frases], (
        "um pedaço que ninguém contou aparecia como frase"
    )
    assert [f["segment_id"] for f in frases if f["stale"]] == [
        one for one in tablet_stale if one != untold.id
    ], "o pedaço contado da parte regravada não aparecia como frase velha"


async def test_each_frase_told_aloud_names_the_portuguese_take_it_was_told_in_and_that_take_plays_at_its_address(  # noqa: E501
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    store: MemoryStore,
    room_app: App,
    signed: None,
) -> None:
    session, (one, _two, _three) = await rehearsed_in_parts(db_session, 3)
    by_part = {row.take_id: row.id for row in await current_segments(db_session, session.id)}
    desk = await _the_desk(db_session, room_app)
    await _tell_again(client, session.id, by_part[one.id], take_id=one.id)

    frases = await _frases(client, session.id, desk)

    (retold,) = [f for f in frases if f["take_id"] == one.id]
    assert retold["bridge_take_id"] is not None, "a frase contada não dizia em que gravação"
    address = await _address(client, take_address(retold["bridge_take_id"]), desk)
    assert _stored_under(store, address["url"]) == RETELLING, (
        "o endereço da gravação em português tocava outra coisa que não a frase contada"
    )


async def test_a_frase_told_without_a_spoken_telling_names_no_portuguese_take(
    client: httpx.AsyncClient, db_session: AsyncSession, room_app: App
) -> None:
    async def _typed(db: AsyncSession, session: IRSession) -> BackTranslationState:
        part = await the_one_part_of(db, session)
        await capture_segment(
            db, session, take_id=part.id, starts_ms=0, ends_ms=1000, transcript="escrita à mão"
        )
        return BackTranslationState(scope=session.pericope)

    session = await ready_session(db_session, tell=_typed)
    desk = await _the_desk(db_session, room_app)

    (frase,) = await _frases(client, session.id, desk)

    assert frase["bridge_take_id"] is None, "uma frase sem gravação falada apontava uma gravação"


async def test_a_re_recorded_sentence_not_yet_translated_names_itself_on_its_frase_until_it_is_told_again(  # noqa: E501
    client: httpx.AsyncClient, db_session: AsyncSession, store: MemoryStore, room_app: App
) -> None:
    session, _, (_, (_, middle, _)) = await rehearsed_in_wav(db_session, store, SCENE_TWO)
    desk = await _the_desk(db_session, room_app)
    laid = await re_record(client, session.id, middle.id, spoken(8.6), sentence_id="sentence-0042")
    assert laid.status_code == 200, laid.text

    awaiting = await _frases(client, session.id, desk)
    await _told_again(client, session.id, middle.id, laid)
    translated = await _frases(client, session.id, desk)

    assert {f["segment_id"]: f["awaiting_sentence_id"] for f in awaiting} == {
        f["segment_id"]: ("sentence-0042" if f["segment_id"] == middle.id else None)
        for f in awaiting
    }, "a frase regravada não dizia que aguarda tradução, ou outra frase dizia"
    assert [f["awaiting_sentence_id"] for f in translated] == [None] * len(translated), (
        "a frase traduzida de novo continuava aguardando"
    )


async def test_a_frase_recorded_again_twice_awaits_under_the_sentence_the_record_names(
    client: httpx.AsyncClient, db_session: AsyncSession, store: MemoryStore, room_app: App
) -> None:
    session, _, (_, (_, middle, _)) = await rehearsed_in_wav(db_session, store, SCENE_TWO)
    desk = await _the_desk(db_session, room_app)
    await re_record(client, session.id, middle.id, spoken(8.6), sentence_id="sentence-0001")
    again = await re_record(client, session.id, middle.id, spoken(1.6), sentence_id="sentence-0002")
    assert again.status_code == 200, again.text

    (named,) = [
        one["sentence_id"]
        for one in await _the_sentences(client, session.id, desk)
        if one["awaiting_frase"] is not None
    ]
    frases = await _frases(client, session.id, desk)

    (frase,) = [f for f in frases if f["segment_id"] == middle.id]
    assert frase["awaiting_sentence_id"] == named == "sentence-0002", (
        "o retro dizia que a frase aguarda sob a primeira regravação, não a que o registro nomeia"
    )


async def test_a_telling_again_says_which_frase_it_supersedes_and_a_first_telling_says_none(
    client: httpx.AsyncClient, db_session: AsyncSession, store: MemoryStore, room_app: App
) -> None:
    session, (one, _two, _three) = await rehearsed_in_parts(db_session, 3)
    by_part = {row.take_id: row.id for row in await current_segments(db_session, session.id)}
    desk = await _the_desk(db_session, room_app)
    await _tell_again(client, session.id, by_part[one.id], take_id=one.id)

    frases = await _frases(client, session.id, desk)

    assert [(f["frase"], f["supersedes"]) for f in frases] == [(1, 1), (2, None), (3, None)], (
        "a frase contada de novo não dizia qual frase substitui, ou uma primeira dizia"
    )


async def test_an_approved_version_whose_release_check_ran_carries_it_and_one_never_checked_carries_none(  # noqa: E501
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    room_app: App,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project, credential = await a_claimed_device(db_session)
    session = await ready_session(db_session, project_id=project.id)
    desk, _facilitator = await at_the_desk(db_session, room_app, project)
    approved = await client.post(team_release(session.id), headers=team_headers(credential))
    assert approved.status_code == 200, approved.text
    never_checked = (await _retro(client, session.id, desk))["release_check"]

    the_bucket_is_in_memory(monkeypatch)
    checked = await client.post(
        f"{PREFIX}/facilitator/sessions/{session.id}/releases/1/check", headers=desk
    )
    assert checked.status_code == 200, checked.text
    carried = (await _retro(client, session.id, desk))["release_check"]

    assert never_checked is None, "uma versão nunca conferida trazia uma conferência"
    assert carried == checked.json(), (
        "o retro não trazia a conferência da versão aprovada como ela foi guardada"
    )


async def test_a_session_with_no_release_carries_no_release_check(
    client: httpx.AsyncClient, db_session: AsyncSession, room_app: App
) -> None:
    project, _credential = await a_claimed_device(db_session)
    session = await ready_session(db_session, project_id=project.id)
    desk, _facilitator = await at_the_desk(db_session, room_app, project)

    retro = await _retro(client, session.id, desk)

    assert retro["release_check"] is None, "um rascunho nunca aprovado trazia uma conferência"


async def test_a_read_reopened_by_a_part_recorded_again_carries_no_release_check(
    client: httpx.AsyncClient, db_session: AsyncSession, store: MemoryStore, room_app: App
) -> None:
    project, credential = await a_claimed_device(db_session)
    session = await ready_session(db_session, project_id=project.id)
    desk, _facilitator = await at_the_desk(db_session, room_app, project)
    approved = await client.post(team_release(session.id), headers=team_headers(credential))
    assert approved.status_code == 200, approved.text
    checked = await client.post(
        f"{PREFIX}/facilitator/sessions/{session.id}/releases/1/check", headers=desk
    )
    assert checked.status_code == 200, checked.text
    assert (await _retro(client, session.id, desk))["release_check"] == checked.json()

    await the_part_recorded_again(db_session, session)
    retro = await _retro(client, session.id, desk)

    assert retro["version"] is None
    assert retro["reopened"]["version"] == 1
    assert retro["release_check"] is None, (
        "o retro reaberto trazia a conferência de uma versão em que o rascunho não está mais"
    )


async def test_a_take_answers_its_signed_address_for_a_rehearsal_take_a_retro_take_and_a_take_recorded_again(  # noqa: E501
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    store: MemoryStore,
    room_app: App,
    signed: None,
) -> None:
    session, (part_one, part_two), ((first,), _) = await rehearsed_in_wav(
        db_session, store, [[(0, 1000)], [(0, 1000)]]
    )
    desk = await _the_desk(db_session, room_app)
    await _part_recorded_again(client, session.id, 2)
    await _tell_again(client, session.id, first.id, take_id=part_one.id, ends_ms=1000)
    (retro_take,) = await _retro_takes(db_session, session.id)
    plays = {
        part_one.id: part_audio(1, 1000),
        part_two.id: part_audio(2, 1000),
        retro_take.id: RETELLING,
    }

    for take_id, bytes_sent in plays.items():
        before = datetime.now(UTC)
        answered = await client.get(take_address(take_id), headers=desk)
        redirected = await client.get(take_audio(take_id), headers=desk, follow_redirects=False)

        assert answered.status_code == 200, answered.text
        address = answered.json()
        assert set(address) == {"url", "expires_at"}
        assert _stored_under(store, address["url"]) == bytes_sent, take_id
        expires_at = datetime.fromisoformat(address["expires_at"])
        assert expires_at.tzinfo is not None
        assert expires_at > before
        assert redirected.status_code == 307
        assert redirected.headers["location"] == address["url"], (
            "o endereço e o redirecionamento apontavam objetos diferentes"
        )


async def test_a_take_a_grain_switch_set_aside_still_answers_its_address(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    store: MemoryStore,
    room_app: App,
    signed: None,
) -> None:
    session, (part_one, _part_two), _ = await rehearsed_in_wav(
        db_session, store, [[(0, 1000)], [(0, 1000)]]
    )
    desk = await _the_desk(db_session, room_app)
    switched = await client.post(
        f"{PREFIX}/sessions/{session.id}/grain",
        json={"grain": "whole"},
        headers={"X-Room-Device": TABLET},
    )
    assert switched.status_code == 200, switched.text
    listing = await client.get(f"{PREFIX}/facilitator/sessions/{session.id}/takes", headers=desk)
    (listed,) = [one for one in listing.json()["takes"] if one["take_id"] == part_one.id]
    assert listed["set_aside_at"] is not None

    address = await _address(client, take_address(part_one.id), desk)

    assert _stored_under(store, address["url"]) == part_audio(1, 1000), (
        "a gravação que a troca de grão pôs de lado não tocava mais"
    )


async def test_a_re_recorded_sentence_answers_its_signed_address_with_the_very_audio_the_team_sent(
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

    address = await _address(client, sentence_address(session.id, "sentence-0042"), desk)
    redirected = await client.get(
        sentence_audio(session.id, "sentence-0042"), headers=desk, follow_redirects=False
    )

    assert set(address) == {"url", "expires_at"}
    assert _stored_under(store, address["url"]) == sent, (
        "o endereço tocava outra coisa que não a frase como a equipe gravou"
    )
    assert redirected.status_code == 307


async def test_another_teams_take_and_sentence_are_answered_as_ones_that_do_not_exist(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    store: MemoryStore,
    room_app: App,
    signed: None,
) -> None:
    session, (part_one, _), (_, (_, middle, _)) = await rehearsed_in_wav(
        db_session, store, SCENE_TWO
    )
    desk = await _the_desk(db_session, room_app)
    await re_record(client, session.id, middle.id, spoken(8.6), sentence_id="sentence-0001")
    other_team, _credential = await a_claimed_device(db_session, email="outra-equipe@example.com")
    stranger, _other = await at_the_desk(db_session, room_app, other_team)
    unknown = "nao-existe-em-lugar-nenhum"
    assert (await client.get(take_address(part_one.id), headers=desk)).status_code == 200

    theirs_take = await client.get(take_address(part_one.id), headers=stranger)
    no_take = await client.get(take_address(unknown), headers=stranger)
    theirs_sentence = await client.get(
        sentence_address(session.id, "sentence-0001"), headers=stranger
    )
    no_sentence = await client.get(sentence_address(session.id, unknown), headers=stranger)
    never_laid = await client.get(sentence_address(session.id, "sentence-0002"), headers=desk)

    assert [theirs_take.status_code, no_take.status_code] == [404, 404]
    assert _blanked(theirs_take.json(), part_one.id) == _blanked(no_take.json(), unknown), (
        "a gravação de outra equipe era recusada de um jeito que entrega que ela existe"
    )
    assert [theirs_sentence.status_code, no_sentence.status_code] == [404, 404]
    assert _blanked(theirs_sentence.json(), "sentence-0001") == _blanked(
        no_sentence.json(), unknown
    ), "a frase de outra equipe era recusada de um jeito que entrega que ela existe"
    assert never_laid.status_code == 404, never_laid.text


async def test_the_consultant_reads_the_retro_and_both_addresses_the_teams_facilitator_reads(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    store: MemoryStore,
    room_app: App,
    consultant: dict[str, str],
    signed: None,
) -> None:
    session, (part_one, _), (_, (_, middle, _)) = await rehearsed_in_wav(
        db_session, store, SCENE_TWO
    )
    desk = await _the_desk(db_session, room_app)
    await re_record(client, session.id, middle.id, spoken(8.6), sentence_id="sentence-0001")

    for url in (
        desk_retro_read(session.id),
        take_address(part_one.id),
        sentence_address(session.id, "sentence-0001"),
    ):
        theirs = await client.get(url, headers=desk)
        consultants = await client.get(url, headers=consultant)

        assert theirs.status_code == consultants.status_code == 200, url
        assert {k: v for k, v in consultants.json().items() if k != "expires_at"} == {
            k: v for k, v in theirs.json().items() if k != "expires_at"
        }, url


async def test_an_archived_session_reads_its_retro_and_answers_its_addresses_as_a_live_one(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    store: MemoryStore,
    room_app: App,
    signed: None,
) -> None:
    session, (part_one, _), (_, (_, middle, _)) = await rehearsed_in_wav(
        db_session, store, SCENE_TWO
    )
    session_id = session.id
    desk = await _the_desk(db_session, room_app)
    await re_record(client, session_id, middle.id, spoken(8.6), sentence_id="sentence-0001")
    doors = [take_address(part_one.id), sentence_address(session_id, "sentence-0001")]
    live = await _retro(client, session_id, desk)
    for door in doors:
        await _address(client, door, desk)

    zeroed = await client.post(
        f"{PREFIX}/facilitator/projects/{TABLET_TEAM}/passages/{P}/archive", headers=desk
    )
    assert zeroed.status_code == 200, zeroed.text
    archived = await _retro(client, session_id, desk)

    assert archived == live, "o retro da sessão arquivada não lia como o da sessão viva"
    for door in doors:
        assert (await client.get(door, headers=desk)).status_code == 200, door


async def test_the_tablets_credential_cannot_reach_the_retro_or_either_address(
    client: httpx.AsyncClient, db_session: AsyncSession, store: MemoryStore, signed: None
) -> None:
    session, (part_one, _), (_, (_, middle, _)) = await rehearsed_in_wav(
        db_session, store, SCENE_TWO
    )
    await re_record(client, session.id, middle.id, spoken(8.6), sentence_id="sentence-0001")

    answers = [
        (await client.get(url)).status_code
        for url in (
            desk_retro_read(session.id),
            take_address(part_one.id),
            sentence_address(session.id, "sentence-0001"),
        )
    ]

    assert answers == [401, 401, 401], "a credencial da tablet alcançava uma porta da mesa"


async def test_nowhere_in_the_read_with_every_new_field_filled_is_the_analysts_note(
    client: httpx.AsyncClient, db_session: AsyncSession, store: MemoryStore, room_app: App
) -> None:
    session, (part_one, _), ((first, second), _) = await rehearsed_in_wav(
        db_session, store, [[(0, 1000), (1000, 2000)], [(0, 1000)]]
    )
    session_id = session.id
    desk = await _the_desk(db_session, room_app)
    await _tell_again(client, session_id, first.id, take_id=part_one.id, ends_ms=1000)
    await re_record(client, session_id, second.id, spoken(0.6), sentence_id="sentence-0001")
    await _part_recorded_again(client, session_id, 2)
    db_session.expire_all()
    live = await get_session(db_session, session_id)
    told = (await current_segments(db_session, session_id))[0]
    missing = Finding(kind=FindingKind.MISSING, note=THE_ANALYSTS_NOTE, segment_id=told.id, chunk=1)
    nuance = Nuance(
        note=THE_ANALYSTS_NOTE,
        chunk=1,
        segment_id=told.id,
        quote=THE_TEAMS_QUOTE,
        story=THE_MAPS_STORY,
        take_id=told.take_id,
        starts_ms=told.starts_ms,
        ends_ms=told.ends_ms,
    )
    await save_back_translation(
        db_session,
        live,
        back_translation_of(live).model_copy(
            update={
                "findings": [missing],
                "nuances": [nuance],
                "analysed_segment_ids": [told.id],
                "checks": [
                    CheckRound(
                        at=datetime(2026, 11, 2, 14, 5, tzinfo=UTC),
                        findings=[missing],
                        spoken="Na frase 1 falta dizer de onde Noemi voltou.",
                        outcome="pass",
                        conferida=False,
                        nuances=[nuance.model_copy(update={"voiced": "before"})],
                    )
                ],
            }
        ),
    )
    forced = await client.post(desk_release(session_id), headers=desk, json={"force": True})
    assert forced.status_code == 200, forced.text
    checked = await client.post(
        f"{PREFIX}/facilitator/sessions/{session_id}/releases/1/check", headers=desk
    )
    assert checked.status_code == 200, checked.text
    (row,) = await releases_of(db_session, session_id)
    assert THE_ANALYSTS_NOTE in json.dumps(row.forced_open_findings)

    served = (await client.get(desk_retro_read(session_id), headers=desk)).text

    body = json.loads(served)
    assert body["release_check"] is not None
    assert any(f["stale"] for f in body["frases"])
    assert any(f["awaiting_sentence_id"] for f in body["frases"])
    assert any(f["supersedes"] is not None for f in body["frases"])
    assert THE_ANALYSTS_NOTE not in served, "a nota do analista aparecia no retro"
    assert THE_TEAMS_QUOTE not in served, "a citação da equipe aparecia no retro"
    assert THE_MAPS_STORY not in served, "a história do mapa aparecia no retro"


async def test_each_finding_and_nuance_names_the_part_it_lands_on_and_one_on_no_stretch_names_none(
    client: httpx.AsyncClient, db_session: AsyncSession, store: MemoryStore, room_app: App
) -> None:
    session, (one, two, three) = await rehearsed_in_parts(db_session, 3)
    by_part = {row.take_id: row for row in await current_segments(db_session, session.id)}
    first, second, third = by_part[one.id].id, by_part[two.id].id, by_part[three.id].id
    session_id, three_id = session.id, three.id
    desk = await _the_desk(db_session, room_app)
    await _tell_again(client, session_id, second, take_id=two.id)
    db_session.expire_all()
    live = await get_session(db_session, session_id)
    await save_back_translation(
        db_session,
        live,
        back_translation_of(live).model_copy(
            update={
                "analysed_segment_ids": [first, second, third],
                "findings": [
                    Finding(kind=FindingKind.ADDITION, note="n", segment_id=first, chunk=1),
                    Finding(kind=FindingKind.UNCLEAR, note="n", segment_id=second, chunk=2),
                    Finding(kind=FindingKind.MISSING, note="n"),
                ],
                "nuances": [
                    Nuance(
                        note="n",
                        chunk=3,
                        segment_id=third,
                        quote="q",
                        story="s",
                        take_id=three_id,
                        starts_ms=0,
                        ends_ms=PART_MS,
                    )
                ],
            }
        ),
    )

    retro = await _retro(client, session_id, desk)

    assert [(f["frase"], f["scene"]) for f in retro["findings"]] == [
        (1, "S1"),
        (None, "S2"),
        (None, None),
    ], "um achado sem frase não dizia em que parte caiu, ou um sem trecho inventava uma parte"
    assert [(n["frase"], n["scene"]) for n in retro["nuances"]] == [(3, "S3")], (
        "a nuance não dizia em que parte caiu"
    )


def test_the_api_reference_documents_the_four_frase_fields_the_release_check_and_both_address_doors() -> (  # noqa: E501
    None
):
    spec = the_app.openapi()
    schemas = spec["components"]["schemas"]
    frase = schemas["SessionRetroFrase"]["properties"]
    retro = schemas["SessionRetroResponse"]["properties"]

    for field in ("stale", "bridge_take_id", "awaiting_sentence_id", "supersedes"):
        assert frase[field].get("description"), field
    assert retro["release_check"].get("description")
    for path in (
        f"{PREFIX}/facilitator/takes/{{take_id}}/address",
        f"{PREFIX}/facilitator/sessions/{{session_id}}/re-recorded-sentences/{{sentence_id}}/address",
    ):
        ok = spec["paths"][path]["get"]["responses"]["200"]["content"]["application/json"]
        assert ok["schema"]["$ref"].endswith("/QuestionAudioResponse"), path


async def test_a_stale_frase_is_on_a_take_the_desks_takes_listing_shows_as_no_longer_live(
    client: httpx.AsyncClient, db_session: AsyncSession, store: MemoryStore, room_app: App
) -> None:
    session, _parts = await rehearsed_in_parts(db_session, 3)
    desk = await _the_desk(db_session, room_app)
    await _part_recorded_again(client, session.id, 2)

    (stale,) = [f for f in await _frases(client, session.id, desk) if f["stale"]]
    listing = await client.get(f"{PREFIX}/facilitator/sessions/{session.id}/takes", headers=desk)

    (take,) = [one for one in listing.json()["takes"] if one["take_id"] == stale["take_id"]]
    assert take["superseded_at"] is not None, (
        "a frase velha apontava uma gravação que a lista da mesa dava como viva"
    )


async def test_each_re_recorded_sentence_names_the_take_it_was_laid_into(
    client: httpx.AsyncClient, db_session: AsyncSession, store: MemoryStore, room_app: App
) -> None:
    session, (_, part_two), (_, (_, middle, _)) = await rehearsed_in_wav(
        db_session, store, SCENE_TWO
    )
    desk = await _the_desk(db_session, room_app)
    laid = await re_record(client, session.id, middle.id, spoken(8.6), sentence_id="sentence-0001")
    assert laid.status_code == 200, laid.text
    (where,) = [one for one in laid.json()["segments"] if one["segment_id"] == middle.id]

    (sentence,) = await _the_sentences(client, session.id, desk)

    assert sentence["take_id"] == where["take_id"] != part_two.id, (
        "o registro não dizia em que gravação a frase regravada foi posta"
    )
