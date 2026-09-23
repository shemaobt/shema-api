"""ENG-1031: a turn is answered only for the project that owns the session.

`take_turn` resolved a session by id alone, the way `approve_internalization_release` used
to before it adopted `get_session_for_room_caller`, so a device from another project's turn
ran transcription, the Guide, the Validator and synthesis against somebody else's recording
before the room ever turned it away.
"""

from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room import sessions as sessions_api
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.sessions import create_session
from app.services.platform.tts import SynthesizedSpeech
from tests.release_harness import KEY, PREFIX, P, a_claimed_device, team_headers
from tests.room_harness import room_client

TEAM_ANSWER = "Noemi voltou para Belem com Rute no tempo da colheita"
GUIDE_LINE = "Vamos ficar nesta cena. O que voces contariam?"


class _CountingHearing:
    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self, *_: Any, **__: Any) -> HeardSpeech:
        self.calls += 1
        return HeardSpeech(text=TEAM_ANSWER)


class _CountingModel:
    """A Guide that always drafts one line and a Validator that always passes it."""

    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self, *, system_prompt: str, **_: Any) -> str:
        self.calls += 1
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return GUIDE_LINE


class _CountingVoice:
    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self, text: str, **_: Any) -> tuple[SynthesizedSpeech, bool]:
        self.calls += 1
        entry = SynthesizedSpeech(
            audio=b"audio",
            mime_type="audio/mpeg",
            etag="e",
            cached=False,
            key=f"tts/voice/turno-{self.calls}.mp3",
        )
        return entry, False


async def _noop_settle(**_: Any) -> None:
    return None


@pytest.fixture()
async def client(db_session, monkeypatch):
    async with room_client(db_session, monkeypatch) as c:
        yield c


@pytest.fixture()
def fan_out(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """The three legs of the turn's own work, each counted, none of them real."""
    hearing = _CountingHearing()
    monkeypatch.setattr(sessions_api, "heard_speech", hearing)

    model = _CountingModel()
    monkeypatch.setattr(
        sys.modules["app.services.internalization_room.run_turn"], "call_agent", model
    )

    voice = _CountingVoice()
    monkeypatch.setattr(sessions_api.room, "synthesize_facilitator_speech", voice)

    monkeypatch.setattr(sessions_api, "settle_coverage", _noop_settle)

    return {"hearing": hearing, "model": model, "voice": voice}


async def _post_a_turn(
    client, session_id: str, headers: dict[str, str], *, turn_id: str | None = None
):
    data = {"turn_id": turn_id} if turn_id else {}
    return await client.post(
        f"{PREFIX}/sessions/{session_id}/turns",
        headers=headers,
        data=data,
        files={"file": ("resposta.m4a", b"audio", "audio/m4a")},
    )


async def test_a_turn_from_another_projects_device_is_refused_before_any_work_runs(
    client, db_session: AsyncSession, fan_out
) -> None:
    owner, credential_owner = await a_claimed_device(db_session, email="owner@example.com")
    _stranger, credential_stranger = await a_claimed_device(
        db_session, email="stranger@example.com"
    )
    session = await create_session(db_session, language="pt", pericope=P, project_id=owner.id)

    stranger = await _post_a_turn(client, session.id, team_headers(credential_stranger))
    owner_reply = await _post_a_turn(client, session.id, team_headers(credential_owner))

    assert stranger.status_code == 404, stranger.text[:300]
    assert owner_reply.status_code == 200, owner_reply.text[:300]
    assert fan_out["hearing"].calls == 1, "o áudio de outro projeto chegou a ser transcrito"
    assert fan_out["model"].calls == 2, "o Guia ou o Validador rodaram para o estranho"
    assert fan_out["voice"].calls == 1, "a linha foi sintetizada para o estranho"


async def test_a_hot_language_memo_does_not_speculate_for_another_project(
    client, db_session: AsyncSession, fan_out
) -> None:
    """The memo ENG-991 reads before the session is a language, and the language alone
    used to be enough to start transcribing — so a session another project's owner had
    already warmed for the room let a stranger's turn begin work no check had cleared.
    """
    owner, credential_owner = await a_claimed_device(db_session, email="owner4@example.com")
    _stranger, credential_stranger = await a_claimed_device(
        db_session, email="stranger4@example.com"
    )
    session = await create_session(db_session, language="pt", pericope=P, project_id=owner.id)

    warm = await _post_a_turn(client, session.id, team_headers(credential_owner))
    assert warm.status_code == 200, warm.text[:300]
    fan_out["hearing"].calls = 0
    fan_out["model"].calls = 0
    fan_out["voice"].calls = 0

    stranger = await _post_a_turn(client, session.id, team_headers(credential_stranger))

    assert stranger.status_code == 404, stranger.text[:300]
    assert fan_out["hearing"].calls == 0, "a transcrição especulativa rodou para outro projeto"


async def test_a_room_key_caller_with_no_device_still_continues_a_project_owned_session(
    client, db_session: AsyncSession, fan_out
) -> None:
    """The shared key names no device and so no project — `_deps.py`'s own "dated
    compromise, not a design" — and a tablet that has not yet claimed one still has a
    session to continue, the way a facilitator's queue already relies on elsewhere. This
    ticket closes the gap a *device* opens by naming another project, not the one the
    shared key has always had by naming none.
    """
    owner, _credential = await a_claimed_device(db_session, email="owner2@example.com")
    session = await create_session(db_session, language="pt", pericope=P, project_id=owner.id)

    answered = await _post_a_turn(
        client, session.id, {"X-Room-Key": KEY, "X-Room-Device": "tablet-sem-dono"}
    )

    assert answered.status_code == 200, answered.text[:300]


async def test_a_replay_is_not_handed_to_another_project(
    client, db_session: AsyncSession, fan_out
) -> None:
    """`answered_turn` used to look up a turn id with no regard for whose session it named,
    so the very shortcut that spares a resend the fan-out also spared an impostor's request
    from ever reaching the check that would have refused it.
    """
    owner, credential_owner = await a_claimed_device(db_session, email="owner5@example.com")
    _stranger, credential_stranger = await a_claimed_device(
        db_session, email="stranger5@example.com"
    )
    session = await create_session(db_session, language="pt", pericope=P, project_id=owner.id)

    first = await _post_a_turn(
        client, session.id, team_headers(credential_owner), turn_id="turno-1"
    )
    assert first.status_code == 200, first.text[:300]

    stranger = await _post_a_turn(
        client, session.id, team_headers(credential_stranger), turn_id="turno-1"
    )
    assert stranger.status_code == 404, stranger.text[:300]

    again = await _post_a_turn(
        client, session.id, team_headers(credential_owner), turn_id="turno-1"
    )
    assert again.status_code == 200, again.text[:300]
    assert again.json() == first.json(), "o dono perdeu a resposta já dada ao pedir de novo"


async def test_a_room_key_replay_still_works_on_a_project_owned_session(
    client, db_session: AsyncSession, fan_out
) -> None:
    owner, _credential = await a_claimed_device(db_session, email="owner6@example.com")
    session = await create_session(db_session, language="pt", pericope=P, project_id=owner.id)
    headers = {"X-Room-Key": KEY, "X-Room-Device": "tablet-sem-dono"}

    first = await _post_a_turn(client, session.id, headers, turn_id="turno-1")
    assert first.status_code == 200, first.text[:300]

    again = await _post_a_turn(client, session.id, headers, turn_id="turno-1")
    assert again.status_code == 200, again.text[:300]
    assert again.json() == first.json(), (
        "o reenvio sem device recomeçou o turno em vez de repeti-lo"
    )


class _OwnershipCheckThatWaitsToBeReleased:
    """The real `session_for_room_caller`, held open so a resend or a stranger's
    request has a chance to arrive while the owner's own turn is still in flight.
    """

    def __init__(self, real: Any) -> None:
        self._real = real
        self.calls = 0
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

    async def __call__(self, db: AsyncSession, session_id: str, project_id: str | None) -> Any:
        self.calls += 1
        self.entered.set()
        await asyncio.wait_for(self.release.wait(), timeout=1)
        return await self._real(db, session_id, project_id)


async def test_a_concurrent_turn_from_another_project_does_not_join_the_owners_flight(
    client, db_session: AsyncSession, fan_out, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`answer_once` deduped on `(session_id, turn_id)` alone, so a stranger's request
    landing while the owner's own turn was still in flight joined that same flight and
    came back with the owner's answer — transcript, audio handle and all — without its
    own project ever reaching the check that would have refused it.
    """
    owner, credential_owner = await a_claimed_device(db_session, email="owner7@example.com")
    _stranger, credential_stranger = await a_claimed_device(
        db_session, email="stranger7@example.com"
    )
    session = await create_session(db_session, language="pt", pericope=P, project_id=owner.id)

    reads = _OwnershipCheckThatWaitsToBeReleased(sessions_api.room.session_for_room_caller)
    monkeypatch.setattr(sessions_api.room, "session_for_room_caller", reads)

    async def _release_once_the_owners_turn_is_waiting() -> None:
        await asyncio.wait_for(reads.entered.wait(), timeout=1)
        await asyncio.sleep(0.05)  # give the resend and the stranger a chance to arrive too
        reads.release.set()

    first, resend, stranger, _ = await asyncio.gather(
        _post_a_turn(client, session.id, team_headers(credential_owner), turn_id="turno-1"),
        _post_a_turn(client, session.id, team_headers(credential_owner), turn_id="turno-1"),
        _post_a_turn(client, session.id, team_headers(credential_stranger), turn_id="turno-1"),
        _release_once_the_owners_turn_is_waiting(),
    )

    assert first.status_code == 200, first.text[:300]
    assert resend.status_code == 200, resend.text[:300]
    assert resend.json() == first.json(), "o reenvio do dono não se juntou ao voo do dono"
    assert stranger.status_code == 404, stranger.text[:300]
    assert reads.calls == 2, "o voo do dono foi conferido um número errado de vezes"
    assert fan_out["model"].calls == 2, "o turno do dono rodou o fan-out mais de uma vez"
