"""ENG-1378 — a name said in a turn moves its bead with that turn's own reply.

Her room checks names inside every turn, once the reply is made (her `oralTurn.ts:88-90`,
PRD ch.13): a being, place, object or time the team names — «Noemi» for Naomi — is engaged,
one the voice names is surfaced, and the turn is saved and answered with them
(`route.ts:247`). Ours left every bead to the classifier that runs after the reply has
shipped, so the beads lagged a turn behind for names, and a classifier that failed moved
none of them at all.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.internalization_room import sessions as sessions_api
from app.services.internalization_room import turn_instructions
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.sessions import append_exchange, get_session
from tests.release_harness import PREFIX, a_claimed_device, team_headers
from tests.room_harness import room_client, the_bucket_is_in_memory
from tests.tablet_turn_harness import the_room_opens, the_team_says, the_turn_is_scripted
from tests.turn_harness import the_room_agent_is

OPENING = "Vamos ouvir uma história juntos."
REPLY = "Isso. Contem mais."


@pytest.fixture()
def voice_says() -> list[str]:
    return [OPENING, REPLY]


@pytest.fixture()
def validator_says() -> list[str]:
    return ["pass"]


@pytest.fixture()
def team_says(
    monkeypatch: pytest.MonkeyPatch, voice_says: list[str], validator_says: list[str]
) -> list[HeardSpeech]:
    said = [HeardSpeech(text="A Noemi ficou.")]

    async def heard(*_: Any, **__: Any) -> HeardSpeech:
        return said[0]

    async def model(*, system_prompt: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": validator_says[0], "issues": ["fora do mapa"]})
        return voice_says.pop(0) if voice_says else REPLY

    async def no_opening_ahead(*_: Any, **__: Any) -> None:
        return None

    the_turn_is_scripted(monkeypatch, heard=heard, model=model)
    monkeypatch.setattr(sessions_api, "prepare_opening", no_opening_ahead)
    return said


@pytest.fixture()
def per_request(test_engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture()
async def client(db_session: AsyncSession, per_request, team_says, monkeypatch):
    the_bucket_is_in_memory(monkeypatch)
    async with room_client(db_session, monkeypatch, per_request=per_request) as c:
        yield c


async def _a_p01_session(client, db_session) -> tuple[str, str]:
    _team, tablet = await a_claimed_device(db_session)
    opened = await client.post(
        f"{PREFIX}/sessions",
        headers=team_headers(tablet),
        json={"language": "pt", "pericope": "P01"},
    )
    return tablet, opened.json()["session_id"]


async def _stored(per_request, session_id: str) -> dict[str, str]:
    async with per_request() as fresh:
        return dict((await get_session(fresh, session_id)).coverage_state or {})


async def test_the_team_saying_noemi_engages_naomi_on_that_turns_reply_with_no_classifier(
    client, db_session, per_request
) -> None:
    tablet, session_id = await _a_p01_session(client, db_session)
    await the_room_opens(client, tablet, session_id)

    answered = await the_team_says(client, tablet, session_id, "turno-1")

    stored = await _stored(per_request, session_id)
    assert [stored.get(f"being:S{scene}:B3") for scene in (1, 2, 3)] == ["engaged"] * 3, (
        "a equipe dizia «Noemi» e a conta de Noemi só andava quando o classificador rodasse"
    )
    assert answered.json()["coverage"]["engaged"] >= 3, (
        "a resposta do turno voltava com as contas de antes do nome dito"
    )


async def test_the_voice_naming_elimelech_surfaces_him_and_leaves_naomi_engaged(
    client, db_session, per_request, voice_says
) -> None:
    voice_says[1] = "E a Noemi foi com o Elimeleque."
    tablet, session_id = await _a_p01_session(client, db_session)
    await the_room_opens(client, tablet, session_id)

    await the_team_says(client, tablet, session_id, "turno-1")

    stored = await _stored(per_request, session_id)
    assert [stored.get(f"being:S{scene}:B2") for scene in (1, 2)] == ["surfaced"] * 2, (
        "a voz dizia Elimeleque na resposta e a conta dele ficava como não tocada"
    )
    assert stored.get("being:S1:B3") == "engaged", (
        "Noemi, dita pela equipe, descia para surfaced quando a voz também a nomeava"
    )


TOLD = "Elimeleque e Noemi saíram de Belém."


async def test_the_names_the_voice_tells_in_the_opening_are_surfaced_and_none_engaged(
    client, db_session, per_request, voice_says
) -> None:
    voice_says[0] = TOLD
    tablet, session_id = await _a_p01_session(client, db_session)

    await the_room_opens(client, tablet, session_id)

    stored = await _stored(per_request, session_id)
    assert [stored.get(key) for key in ("being:S1:B2", "being:S1:B3", "place:S1:PL1")] == [
        "surfaced"
    ] * 3, "a abertura nomeava Elimeleque, Noemi e Belém e nenhuma conta saía do lugar"
    assert "engaged" not in stored.values(), "a abertura da voz engajava o que a equipe não disse"


async def test_the_names_an_opening_prepared_ahead_tells_are_surfaced_when_it_is_heard(
    client, db_session, per_request
) -> None:
    tablet, session_id = await _a_p01_session(client, db_session)
    async with per_request() as fresh:
        row = await get_session(fresh, session_id)
        row.prepared_speech = TOLD
        row.prepared_audio_key = "prepared/abertura.mp3"
        await fresh.commit()

    await the_room_opens(client, tablet, session_id)

    stored = await _stored(per_request, session_id)
    assert stored.get("being:S1:B2") == "surfaced", (
        "a abertura preparada nomeava Elimeleque e a conta dele não saía do lugar"
    )


NOTE = "[A sessão acabou de começar. A equipe abriu a passagem P01 e falou da Noemi.]"


def _the_note_names_noemi(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(turn_instructions, "opening_note", lambda *_: NOTE)


async def test_a_name_in_the_opening_note_is_read_as_the_teams_and_engaged(
    client, db_session, per_request, monkeypatch
) -> None:
    _the_note_names_noemi(monkeypatch)
    tablet, session_id = await _a_p01_session(client, db_session)

    await the_room_opens(client, tablet, session_id)

    stored = await _stored(per_request, session_id)
    assert stored.get("being:S1:B3") == "engaged", (
        "a nota de abertura é a fala da equipe no turno 0, e o nome nela não era lido"
    )


async def test_a_name_in_the_note_of_an_opening_prepared_ahead_is_engaged(
    client, db_session, per_request, monkeypatch
) -> None:
    _the_note_names_noemi(monkeypatch)
    tablet, session_id = await _a_p01_session(client, db_session)
    async with per_request() as fresh:
        row = await get_session(fresh, session_id)
        row.prepared_speech = OPENING
        row.prepared_audio_key = "prepared/abertura.mp3"
        await fresh.commit()

    await the_room_opens(client, tablet, session_id)

    stored = await _stored(per_request, session_id)
    assert stored.get("being:S1:B3") == "engaged", (
        "a nota da abertura preparada nomeava Noemi e a conta dela não era engajada"
    )


async def test_an_opening_dropped_because_the_team_spoke_first_moves_no_bead(
    client, db_session, per_request, monkeypatch
) -> None:
    tablet, session_id = await _a_p01_session(client, db_session)

    async def the_team_speaks_while_the_guide_thinks(*, system_prompt: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        async with per_request() as rival:
            team = await get_session(rival, session_id)
            await append_exchange(rival, team, team_utterance="Sim.", guide_response=REPLY)
        return TOLD

    the_room_agent_is(monkeypatch, turn=the_team_speaks_while_the_guide_thinks)

    await the_room_opens(client, tablet, session_id)

    stored = await _stored(per_request, session_id)
    assert stored.get("being:S1:B2", "not_encountered") == "not_encountered", (
        "a abertura descartada, que não ficou no registro, ainda movia as contas que nomeava"
    )


async def test_an_opening_prepared_ahead_and_dropped_because_the_team_spoke_first_moves_no_bead(
    client, db_session, per_request, monkeypatch
) -> None:
    tablet, session_id = await _a_p01_session(client, db_session)
    async with per_request() as fresh:
        row = await get_session(fresh, session_id)
        row.prepared_speech = TOLD
        row.prepared_audio_key = "prepared/abertura.mp3"
        await fresh.commit()

    async def the_team_speaks_while_the_clip_is_found(key: str, *_: Any, **__: Any) -> str:
        async with per_request() as rival:
            team = await get_session(rival, session_id)
            await append_exchange(rival, team, team_utterance="Sim.", guide_response=REPLY)
        return key

    monkeypatch.setattr(
        sessions_api.room, "in_a_voice_the_room_has", the_team_speaks_while_the_clip_is_found
    )

    await the_room_opens(client, tablet, session_id)

    stored = await _stored(per_request, session_id)
    assert stored.get("being:S1:B2", "not_encountered") == "not_encountered", (
        "a abertura preparada e descartada ainda movia as contas que nomeava"
    )


async def test_a_mother_tongue_take_engages_nothing_and_the_names_the_voice_says_are_surfaced(
    client, db_session, per_request, voice_says, team_says
) -> None:
    team_says[0] = HeardSpeech(
        text="A Noemi ficou.", language_code="ter", language_probability=0.99
    )
    voice_says[1] = "Vocês ensaiaram a cena de Noemi."
    tablet, session_id = await _a_p01_session(client, db_session)
    await the_room_opens(client, tablet, session_id)

    await the_team_says(client, tablet, session_id, "turno-1")

    stored = await _stored(per_request, session_id)
    assert "engaged" not in stored.values(), (
        "um ensaio na língua materna engajava os nomes que o transcritor escreveu nele"
    )
    assert stored.get("being:S1:B3") == "surfaced", (
        "a voz nomeava Noemi depois do ensaio na língua materna e a conta não saía do lugar"
    )


async def test_a_turn_that_ends_in_a_fail_safe_line_still_engages_the_name_the_team_said(
    client, db_session, per_request, validator_says
) -> None:
    tablet, session_id = await _a_p01_session(client, db_session)
    await the_room_opens(client, tablet, session_id)
    validator_says[0] = "regenerate"

    await the_team_says(client, tablet, session_id, "turno-1")

    async with per_request() as fresh:
        guide = (await get_session(fresh, session_id)).messages[-1]
    assert guide.get("category"), "o turno não terminou na fala de fail-safe"
    stored = await _stored(per_request, session_id)
    assert stored.get("being:S1:B3") == "engaged", (
        "a voz caía no fail-safe e a Noemi que a equipe disse ficava sem conta"
    )


async def test_the_classifier_reads_the_row_with_the_name_already_engaged_by_the_turn(
    client, db_session, per_request, monkeypatch
) -> None:
    read_by_the_settle: list[dict[str, str]] = []

    async def the_settle_reads_the_row(*, session_id: str, **_: Any) -> None:
        read_by_the_settle.append(await _stored(per_request, session_id))

    monkeypatch.setattr(sessions_api, "settle_coverage", the_settle_reads_the_row)
    tablet, session_id = await _a_p01_session(client, db_session)
    await the_room_opens(client, tablet, session_id)

    await the_team_says(client, tablet, session_id, "turno-1")

    assert [read.get("being:S1:B3") for read in read_by_the_settle] == ["engaged"], (
        "o classificador lia a linha antes do commit do turno e gravava por cima a conta de Noemi"
    )
