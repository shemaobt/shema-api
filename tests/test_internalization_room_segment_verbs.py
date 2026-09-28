"""The two verbs get a door: the team can divide a stretch and replace one.

`capture_segment` has taken `parent` and `replaces` since the stretch became a row, and nobody
could reach either — the only caller was the route that tells a stretch back, and it passes
neither. These are the two routes, and only the two routes.

The cases describe behaviour through the room's own doors. Where one reads the service directly
it is because the question is about what the analyst is given, which is not a route.
"""

from __future__ import annotations

import base64
import json
import sys
import uuid
from typing import Any

import httpx
import pytest
from google_crc32c import Checksum
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSessionStatus, IRTakeKind
from app.services.internalization_room import segments as service
from app.services.internalization_room.sessions import RETELLS_BEFORE_A_WARNING
from app.services.platform.storage import StoredObject
from tests.room_harness import heard_every_part, press_terminei
from tests.turn_harness import the_room_agent_is

PREFIX = "/api/internalization-room"
KEY = "sala-de-teste"
DEVICE = "tablet-da-equipe-1"
PASSAGE = "P01"


class MemoryStore:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def get(self, key: str) -> bytes | None:
        return self.objects.get(key)

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self.objects[key] = data

    async def stat(self, key: str) -> StoredObject | None:
        stored = self.objects.get(key)
        if stored is None:
            return None
        checksum = Checksum()
        checksum.update(stored)
        return StoredObject(
            size=len(stored), crc32c=base64.b64encode(checksum.digest()).decode("ascii")
        )


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    """The room's routes, with the bucket and the transcriber held still.

    `client.said` queues what the transcriber answers, one entry per recording, so a case can
    say what the team told back without a model in the loop.
    """
    from fastapi import FastAPI

    from app.api.internalization_room import back_translation as bt_api
    from app.api.internalization_room import router
    from app.api.internalization_room import segments as segments_api
    from app.core.config import get_settings
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers
    from app.services.internalization_room import takes as takes_service

    monkeypatch.setattr(get_settings(), "internalization_room_api_key", KEY, raising=False)
    bucket = MemoryStore()
    monkeypatch.setattr(takes_service, "_store", lambda *_, **__: bucket)

    said: list[str] = []

    async def _transcribe(*_: Any, **__: Any) -> str:
        return said.pop(0) if said else "algo que a equipe contou"

    # Both routes hold their own reference to `heard`, so both are stubbed. Patching one and
    # not the other let a replacement quietly answer `captured=False` while the case read the
    # status code and believed it.
    monkeypatch.setattr(bt_api, "heard", _transcribe)
    monkeypatch.setattr(segments_api, "heard", _transcribe)

    test_app = FastAPI()
    test_app.include_router(router, prefix=PREFIX)
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    async with httpx.AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test"
    ) as c:
        c.said = said  # type: ignore[attr-defined]
        yield c


HEADERS = {"X-Room-Key": KEY, "X-Room-Device": DEVICE}


async def _session(client: httpx.AsyncClient) -> str:
    made = await client.post(
        f"{PREFIX}/sessions", headers={"X-Room-Key": KEY}, json={"pericope": PASSAGE}
    )
    assert made.status_code == 200, made.text
    return str(made.json()["session_id"])


async def _rehearse(client: httpx.AsyncClient, session_id: str, audio: bytes) -> str:
    kept = await client.post(
        f"{PREFIX}/sessions/{session_id}/takes",
        headers=HEADERS,
        data={"kind": IRTakeKind.ENSAIO.value, "scope": PASSAGE},
        files={"file": ("tomada.m4a", audio, "audio/mp4")},
    )
    assert kept.status_code == 200, kept.text
    return str(kept.json()["take_id"])


async def _tell(
    client: httpx.AsyncClient, session_id: str, take_id: str, starts: int, ends: int, audio: bytes
) -> httpx.Response:
    return await client.post(
        f"{PREFIX}/sessions/{session_id}/back-translation/chunks",
        headers=HEADERS,
        data={"take_id": take_id, "starts_ms": str(starts), "ends_ms": str(ends)},
        files={"file": ("trecho.m4a", audio, "audio/mp4")},
    )


async def _divide(
    client: httpx.AsyncClient, session_id: str, segment_id: str, at_ms: int
) -> httpx.Response:
    return await client.post(
        f"{PREFIX}/sessions/{session_id}/segments/{segment_id}/divide",
        headers=HEADERS,
        json={"at_ms": at_ms},
    )


async def _replace(
    client: httpx.AsyncClient,
    session_id: str,
    segment_id: str,
    *,
    take_id: str,
    starts_ms: int,
    ends_ms: int,
    audio: bytes | None = None,
) -> httpx.Response:
    files = {"file": ("trecho.m4a", audio, "audio/mp4")} if audio is not None else None
    return await client.post(
        f"{PREFIX}/sessions/{session_id}/segments/{segment_id}/replace",
        headers=HEADERS,
        data={"take_id": take_id, "starts_ms": str(starts_ms), "ends_ms": str(ends_ms)},
        files=files,
    )


async def _units(client: httpx.AsyncClient, session_id: str) -> list[dict[str, Any]]:
    """The stretches that count, as the tablet reads them."""
    state = await client.get(f"{PREFIX}/sessions/{session_id}", headers={"X-Room-Key": KEY})
    assert state.status_code == 200, state.text
    return list(state.json()["back_translation"]["segments"])


async def _one_told_stretch(client: httpx.AsyncClient) -> tuple[str, str, dict[str, Any]]:
    """A session with one rehearsal recording and one stretch told back over (0, 20000)."""
    session_id = await _session(client)
    take_id = await _rehearse(client, session_id, b"a equipe ensaiou a passagem inteira")
    client.said.append("Noemi mandou Rute voltar e Rute disse que ia junto.")  # type: ignore[attr-defined]
    told = await _tell(client, session_id, take_id, 0, 20000, b"o trecho inteiro")
    assert told.status_code == 200, told.text
    return session_id, take_id, (await _units(client, session_id))[0]


# ---------------------------------------------------------------------------
# 1. A divided stretch becomes two, and the original stops counting
# ---------------------------------------------------------------------------


async def test_a_divided_stretch_becomes_two_and_the_original_stops_counting(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Two pieces, not one and not three.

    The pieces are then told back, so the second half of the case is about what the analyst
    actually reads and not only about what the tablet lists: the whole stretch must be gone
    from both.
    """
    session_id, _, whole = await _one_told_stretch(client)

    cut = await _divide(client, session_id, whole["segment_id"], 8000)

    assert cut.status_code == 200, cut.text
    units = await _units(client, session_id)
    assert len(units) == 2
    assert whole["segment_id"] not in [one["segment_id"] for one in units]

    client.said.extend(["a primeira metade", "a segunda metade"])  # type: ignore[attr-defined]
    for unit in units:
        answered = await _replace(
            client,
            session_id,
            unit["segment_id"],
            take_id=unit["take_id"],
            starts_ms=unit["starts_ms"],
            ends_ms=unit["ends_ms"],
            audio=b"explicando " + unit["segment_id"].encode(),
        )
        assert answered.status_code == 200, answered.text

    read = service.told_back(await service.final_segments(db_session, session_id))

    assert [one.transcript for one in read] == ["a primeira metade", "a segunda metade"]


# ---------------------------------------------------------------------------
# 2. The two pieces cover the audio the original covered
# ---------------------------------------------------------------------------


async def test_the_two_pieces_cover_exactly_what_the_original_covered(
    client: httpx.AsyncClient,
) -> None:
    """No recording is lost in the division, and none appears twice.

    The intervals are half-open, so the millisecond of the cut belongs to the second piece:
    closed on both sides would count it twice, open on both would drop it.
    """
    session_id, _, whole = await _one_told_stretch(client)

    await _divide(client, session_id, whole["segment_id"], 8000)

    units = await _units(client, session_id)
    spans = [(one["starts_ms"], one["ends_ms"]) for one in units]

    assert spans == [(0, 8000), (8000, 20000)]
    assert spans[0][0] == whole["starts_ms"], "o começo do primeiro é o começo do original"
    assert spans[-1][1] == whole["ends_ms"], "o fim do último é o fim do original"
    assert spans[0][1] == spans[1][0], "sem buraco e sem sobreposição: a borda é uma só"
    covered = sum(end - start for start, end in spans)
    assert covered == whole["ends_ms"] - whole["starts_ms"]
    assert [one["take_id"] for one in units] == [whole["take_id"], whole["take_id"]]


# ---------------------------------------------------------------------------
# 3. The order holds
# ---------------------------------------------------------------------------


async def test_the_pieces_sit_where_the_original_sat_between_the_same_neighbours(
    client: httpx.AsyncClient,
) -> None:
    session_id = await _session(client)
    take_id = await _rehearse(client, session_id, b"o ensaio")
    client.said.extend(["antes", "o do meio", "depois"])  # type: ignore[attr-defined]
    await _tell(client, session_id, take_id, 0, 5000, b"a")
    await _tell(client, session_id, take_id, 5000, 25000, b"b")
    await _tell(client, session_id, take_id, 25000, 30000, b"c")
    before, middle, after = await _units(client, session_id)

    await _divide(client, session_id, middle["segment_id"], 15000)

    units = await _units(client, session_id)

    told_order = [one["segment_id"] for one in units]
    assert told_order[0] == before["segment_id"]
    assert told_order[-1] == after["segment_id"]
    assert [(one["starts_ms"], one["ends_ms"]) for one in units] == [
        (0, 5000),
        (5000, 15000),
        (15000, 25000),
        (25000, 30000),
    ]


# ---------------------------------------------------------------------------
# 4. The one correction: the same slice, told again
# ---------------------------------------------------------------------------


async def test_redoing_only_the_explanation_over_unchanged_audio_is_accepted(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """The correction the room has: the audio stays where it is and the telling is redone."""
    session_id, take_id, whole = await _one_told_stretch(client)

    client.said.append("a explicação refeita")  # type: ignore[attr-defined]
    answered = await _replace(
        client,
        session_id,
        whole["segment_id"],
        take_id=take_id,
        starts_ms=whole["starts_ms"],
        ends_ms=whole["ends_ms"],
        audio=b"contando de novo",
    )

    assert answered.status_code == 200, answered.text
    units = await _units(client, session_id)
    assert len(units) == 1
    assert units[0]["take_id"] == take_id
    assert units[0]["told"] is True

    read = service.told_back(await service.final_segments(db_session, session_id))

    assert [one.transcript for one in read] == ["a explicação refeita"]


# ---------------------------------------------------------------------------
# 6. A divided stretch cannot be replaced as a unit
# ---------------------------------------------------------------------------


async def test_a_divided_stretch_cannot_be_replaced_as_a_unit_through_the_route(
    client: httpx.AsyncClient,
) -> None:
    """The refusal the service already carries, reachable through the door.

    Over the stretch's own slice, so what answers is the guard about the divided unit and not
    the one about the slice: a correction addressed elsewhere is refused a line earlier, and
    this case would go on passing without ever reaching what it is named for.
    """
    session_id, _, whole = await _one_told_stretch(client)
    await _divide(client, session_id, whole["segment_id"], 8000)

    client.said.append("o todo contado outra vez")  # type: ignore[attr-defined]
    refused = await _replace(
        client,
        session_id,
        whole["segment_id"],
        take_id=whole["take_id"],
        starts_ms=whole["starts_ms"],
        ends_ms=whole["ends_ms"],
        audio=b"contando o todo outra vez",
    )

    assert refused.status_code == 400, refused.text
    assert len(await _units(client, session_id)) == 2, "e a recusa não mexeu em nada"


# ---------------------------------------------------------------------------
# 7. The room only reaches its own session
# ---------------------------------------------------------------------------


async def test_a_stretch_of_another_session_is_refused_the_way_an_absent_one_is(
    client: httpx.AsyncClient,
) -> None:
    """The room key is the same string in every tablet, so the session in the path is the
    only thing that says which work is being reached.

    The refusal may not tell "not yours" apart from "does not exist": one message for absent,
    unowned and somebody else's, which is what the room already does for sessions and takes.

    The positive control at the top is load-bearing. Without it this case passes against a
    branch where the route simply does not exist — two generic 404s are also indistinguishable
    from one another — and it would be measuring nothing.
    """
    absent = str(uuid.uuid4())
    mine, _, my_stretch = await _one_told_stretch(client)
    theirs, _, their_stretch = await _one_told_stretch(client)

    allowed = await _divide(client, mine, my_stretch["segment_id"], 8000)
    trespass = await _divide(client, mine, their_stretch["segment_id"], 8000)
    invented = await _divide(client, mine, absent, 8000)

    assert allowed.status_code == 200, allowed.text
    assert trespass.status_code == 404, trespass.text
    assert invented.status_code == 404
    assert trespass.json()["detail"].replace(their_stretch["segment_id"], "X") == invented.json()[
        "detail"
    ].replace(absent, "X"), "a recusa não distingue o que é de outra sessão do que não existe"
    assert len(await _units(client, theirs)) == 1, "e o trecho da outra sessão não foi tocado"


# ---------------------------------------------------------------------------
# 8. Today's back translation goes on working
# ---------------------------------------------------------------------------


async def test_the_back_translation_the_room_already_does_goes_on_working(
    client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The regression case of the slice."""
    session_id = await _session(client)
    take_id = await _rehearse(client, session_id, b"a equipe ensaiou a passagem inteira")
    client.said.extend(["Noemi mandou Rute voltar.", "Rute disse que ia junto."])  # type: ignore[attr-defined]
    first = await _tell(client, session_id, take_id, 0, 9000, b"primeiro")
    second = await _tell(client, session_id, take_id, 9000, 21000, b"segundo")

    assert first.json()["captured"] is True
    assert second.json()["chunks"] == 2

    async def analyst(*, system_prompt: str, user_content: str, **_: Any) -> str:
        return (
            '{"evidence_sufficient": true, "findings": ['
            '{"kind": "missing", "chunk": 2, "note": "faltou dizer para onde Rute ia"}]}'
        )

    the_room_agent_is(monkeypatch, analyst=analyst)

    async def speaker(*, system_prompt: str, user_content: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return "Vocês contaram bem. Falta uma coisa."

    the_room_agent_is(monkeypatch, turn=speaker)

    async def _voice(*_: Any, **__: Any):
        return (type("Voiced", (), {"key": "uma-chave"})(), 0)

    monkeypatch.setattr(
        sys.modules["app.api.internalization_room.back_translation"].room,
        "synthesize_facilitator_speech",
        _voice,
    )

    verdict = await press_terminei(
        client, session_id, report=await heard_every_part(db_session, session_id)
    )

    assert verdict.status_code == 200, verdict.text
    body = verdict.json()
    assert body["checked"] is False
    assert body["finding_kind"] == "missing"
    assert body["finding_segment_id"] == (await _units(client, session_id))[1]["segment_id"]


# ---------------------------------------------------------------------------
# Where the cut may fall — the rule this slice had to decide
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("at_ms", [0, 20000, -1, 25000])
async def test_a_cut_on_the_border_or_outside_the_stretch_is_refused(
    client: httpx.AsyncClient, at_ms: int
) -> None:
    """A cut on either border makes a piece of no duration; one outside is not a cut at all.

    A zero-length piece is not merely useless. It is a final unit that can never be
    completed — no audio to hear, so nothing to tell back, so no explanation ever — and the
    first round only releases when every final unit has one. A tap one millisecond wide of
    the mark would jam the passage for good, and the team has no verb to undo it.
    """
    session_id, _, whole = await _one_told_stretch(client)

    refused = await _divide(client, session_id, whole["segment_id"], at_ms)

    assert refused.status_code == 400, refused.text
    assert len(await _units(client, session_id)) == 1, "e nada foi dividido"


async def test_a_cut_one_millisecond_inside_either_border_is_accepted(
    client: httpx.AsyncClient,
) -> None:
    """The positive control for the case above: strict inequality is the only refusal.

    Without this, a rule that refused every cut whatsoever would pass the parametrised case
    and be just as wrong. No minimum duration is imposed — any floor would be a number
    invented here rather than measured, and the room has no screen to explain a refusal with.
    """
    session_id, _, whole = await _one_told_stretch(client)

    cut = await _divide(client, session_id, whole["segment_id"], 1)

    assert cut.status_code == 200, cut.text
    assert [(one["starts_ms"], one["ends_ms"]) for one in await _units(client, session_id)] == [
        (0, 1),
        (1, 20000),
    ]


async def test_a_stretch_that_was_already_divided_cannot_be_divided_again(
    client: httpx.AsyncClient,
) -> None:
    """Its audio is already covered by its pieces; cutting it again would make a sibling that
    overlaps its own nephews."""
    session_id, _, whole = await _one_told_stretch(client)
    await _divide(client, session_id, whole["segment_id"], 8000)

    refused = await _divide(client, session_id, whole["segment_id"], 4000)

    assert refused.status_code == 400, refused.text
    assert len(await _units(client, session_id)) == 2


# ---------------------------------------------------------------------------
# What the division would otherwise have thrown away
# ---------------------------------------------------------------------------


async def test_the_explanation_of_a_divided_stretch_still_travels_to_refine(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """A divided parent is current and is not a leaf, so it is in neither list the handoff
    carried: not the final units, not the retired ones. Its explanation — what the team said
    about the whole stretch before they heard two ideas in it — vanished from the artifact in
    silence.

    The same class of loss as a replaced stretch, which the handoff already carries on
    purpose. This slice is what creates the state, so this slice is what has to carry it.
    """
    session_id, _, whole = await _one_told_stretch(client)

    await _divide(client, session_id, whole["segment_id"], 8000)

    divided = await service.divided_segments(db_session, session_id)

    assert [one.id for one in divided] == [whole["segment_id"]]
    assert [one.transcript for one in divided] == [
        "Noemi mandou Rute voltar e Rute disse que ia junto."
    ]
    assert [one.id for one in await service.final_segments(db_session, session_id)] != [
        whole["segment_id"]
    ], "e continua fora das unidades finais, que é o que a divisão quer dizer"


# ---------------------------------------------------------------------------
# Raised in review
# ---------------------------------------------------------------------------


async def test_the_pieces_keep_the_pass_the_stretch_they_came_from_was_told_on(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Dividing a stretch told on the second pass gives pieces still on the second pass.

    They were born on the default, so the handoff reported material the team had already been
    asked about once as if it were the first telling. Replacing carries the pass; dividing has
    to carry it too, or the two verbs describe the same stretch differently.
    """
    session_id = await _session(client)
    take_id = await _rehearse(client, session_id, b"o ensaio")
    client.said.append("contado de novo depois de um achado")  # type: ignore[attr-defined]
    retold = await client.post(
        f"{PREFIX}/sessions/{session_id}/back-translation/chunks",
        headers=HEADERS,
        data={
            "take_id": take_id,
            "starts_ms": "0",
            "ends_ms": "20000",
            "retelling": "true",
        },
        files={"file": ("trecho.m4a", b"de novo", "audio/mp4")},
    )
    assert retold.json()["pass_number"] == 2, retold.text
    whole = (await _units(client, session_id))[0]

    await _divide(client, session_id, whole["segment_id"], 8000)

    assert [one["pass_number"] for one in await _units(client, session_id)] == [2, 2]


async def test_a_stretch_that_no_longer_counts_cannot_be_replaced(
    client: httpx.AsyncClient,
) -> None:
    """A tablet that retries a replacement it already sent lands on the row it superseded.

    Two things measured before this case was written, both reached through this route. The
    successor takes the same position as the one already current, so the index that keeps one
    position to one current stretch refuses the insert and the room receives a 500 it cannot
    read. And once a telling-back has been started over there is no current row left to collide
    with, so the same call quietly brings a stretch back from the recording the team threw away.
    """
    session_id, take_id, whole = await _one_told_stretch(client)
    client.said.append("a explicação refeita")  # type: ignore[attr-defined]
    done = await _replace(
        client,
        session_id,
        whole["segment_id"],
        take_id=take_id,
        starts_ms=whole["starts_ms"],
        ends_ms=whole["ends_ms"],
        audio=b"contando de novo",
    )
    assert done.status_code == 200, done.text

    client.said.append("uma terceira vez")  # type: ignore[attr-defined]
    again = await _replace(
        client,
        session_id,
        whole["segment_id"],
        take_id=take_id,
        starts_ms=whole["starts_ms"],
        ends_ms=whole["ends_ms"],
        audio=b"contando outra vez",
    )

    assert again.status_code == 400, again.text
    units = await _units(client, session_id)
    assert len(units) == 1
    assert [one["segment_id"] for one in units] != [whole["segment_id"]]


async def test_a_stretch_that_no_longer_counts_cannot_be_divided_through_the_route(
    client: httpx.AsyncClient,
) -> None:
    """The same door, the same refusal — reached before anything is written."""
    session_id, _, whole = await _one_told_stretch(client)
    client.said.append("o trecho contado outra vez")  # type: ignore[attr-defined]
    await _replace(
        client,
        session_id,
        whole["segment_id"],
        take_id=whole["take_id"],
        starts_ms=whole["starts_ms"],
        ends_ms=whole["ends_ms"],
        audio=b"contando o trecho outra vez",
    )

    refused = await _divide(client, session_id, whole["segment_id"], 4000)

    assert refused.status_code == 400, refused.text
    assert len(await _units(client, session_id)) == 1


# ---------------------------------------------------------------------------
# Correcting a stretch spends retell budget — ENG-685
# ---------------------------------------------------------------------------
#
# `RETELLS_BEFORE_A_WARNING` exists so a team never gets stuck retelling: when it runs out
# the room stops and asks for a person. It was charged on the telling-back route alone, and a
# correction does not go through there — so the one limit the room has against trapping a team
# did not cover the path the team actually corrects by. In a room where nobody reads and the
# facilitator is a voice, a team stuck in that cycle has no way to ask for help.


async def _tellings(db: AsyncSession, session_id: str) -> list[int]:
    """How many times the team has told each stretch that counts, oldest position first.

    Read off the rows rather than off the tablet's state: the count is a property of the
    stretch, and the tablet is deliberately not told about it.
    """
    db.expire_all()
    return [one.tellings for one in await service.current_segments(db, session_id)]


async def _asks_for_a_person(client: httpx.AsyncClient, session_id: str) -> bool:
    """Whether the room has stopped and put a person in front of the team."""
    state = await client.get(f"{PREFIX}/sessions/{session_id}", headers={"X-Room-Key": KEY})
    assert state.status_code == 200, state.text
    return bool(state.json()["status"] == IRSessionStatus.NEEDS_PERSON.value)


async def _correct(
    client: httpx.AsyncClient,
    session_id: str,
    stretch: dict[str, Any],
    *,
    saying: str | None = "Noemi mandou Rute voltar, e Rute foi junto.",
) -> httpx.Response:
    """The team explains one stretch again over the recording that did not move.

    `saying=None` is the transcriber coming back with nothing, which is the shape of an outage.
    """
    if saying is not None:
        client.said.append(saying)  # type: ignore[attr-defined]
    else:
        client.said.append("")  # type: ignore[attr-defined]
    return await _replace(
        client,
        session_id,
        stretch["segment_id"],
        take_id=stretch["take_id"],
        starts_ms=stretch["starts_ms"],
        ends_ms=stretch["ends_ms"],
        audio=b"contado de novo",
    )


async def test_correcting_a_stretch_counts_a_telling_on_it(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Case 1. The count means what it says it means, on the route the team corrects by."""
    session_id, _, stretch = await _one_told_stretch(client)
    assert await _tellings(db_session, session_id) == [1]

    answered = await _correct(client, session_id, stretch)

    assert answered.status_code == 200, answered.text
    assert await _tellings(db_session, session_id) == [2]


async def test_the_count_runs_out_on_one_stretch_and_the_room_offers_a_person(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Case 2. What the count is for: the team stops being alone with a cycle it cannot end.

    The correction that crosses still answers with the stretches — losing the team's own work
    to the moment the room asked for help would be worse than the problem.
    """
    session_id, _, _ = await _one_told_stretch(client)

    for _ in range(RETELLS_BEFORE_A_WARNING - 1):
        standing = (await _units(client, session_id))[0]
        answered = await _correct(client, session_id, standing)
        assert answered.status_code == 200, answered.text

    assert await _tellings(db_session, session_id) == [RETELLS_BEFORE_A_WARNING]
    assert await _asks_for_a_person(client, session_id) is True
    assert answered.json()["segments"], "a resposta daquela correção não se perde no caminho"


async def test_the_count_is_spent_on_the_attempt_not_on_the_result(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Case 3. The same argument the telling-back route already carries in writing.

    If only a correction that landed counted, then during a transcriber outage — when every
    attempt comes back empty — the team could correct forever, the count would never cross,
    and the room's only route to a person would be unreachable exactly when the room is broken.
    """
    session_id, _, stretch = await _one_told_stretch(client)
    assert await _tellings(db_session, session_id) == [1]

    answered = await _correct(client, session_id, stretch, saying=None)

    assert answered.status_code == 200, answered.text
    assert answered.json()["captured"] is False, "nada pôde ser entendido, então nada foi trocado"
    assert await _tellings(db_session, session_id) == [2]


async def test_telling_a_new_stretch_never_counts_against_another(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Case 4, and the control that matters most here.

    Without it this becomes "every recording sent counts", and a team telling six stretches
    back for the first time would be handed to a person having repeated nothing at all —
    punishing the path where nothing went wrong.
    """
    session_id = await _session(client)
    take_id = await _rehearse(client, session_id, b"a equipe ensaiou a passagem inteira")

    for piece in range(6):
        client.said.append(f"o trecho {piece + 1}")  # type: ignore[attr-defined]
        told = await _tell(
            client, session_id, take_id, piece * 5000, (piece + 1) * 5000, b"um trecho"
        )
        assert told.status_code == 200, told.text

    assert await _tellings(db_session, session_id) == [1] * 6
    assert await _asks_for_a_person(client, session_id) is False


async def test_the_telling_back_route_counts_on_the_stretch_it_retells(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Case 5. Control against the change leaking into the neighbour.

    The telling-back route counts only when the team says it is telling again, and it counts
    on the stretch that telling replaces: a first telling is one, a marked retelling is two.
    """
    session_id, take_id, _ = await _one_told_stretch(client)
    assert await _tellings(db_session, session_id) == [1]

    client.said.append("Noemi mandou Rute voltar, de novo.")  # type: ignore[attr-defined]
    retold = await client.post(
        f"{PREFIX}/sessions/{session_id}/back-translation/chunks",
        headers=HEADERS,
        data={
            "take_id": take_id,
            "starts_ms": "0",
            "ends_ms": "20000",
            "retelling": "true",
        },
        files={"file": ("trecho.m4a", b"de novo", "audio/mp4")},
    )

    assert retold.status_code == 200, retold.text
    assert await _tellings(db_session, session_id) == [2]


async def test_dividing_a_stretch_is_not_telling_it_again_and_counts_nothing(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Dividing is the team hearing two ideas where they told one, not telling one again.

    It writes two rows against a recording that was already there — no audio crosses the wire
    and nothing is told again — so counting it would charge a team for an act of reading.

    The pieces keep the count of the stretch they came from, for the reason they keep its
    pass: born on the default, a division of something already told twice would hand the team
    a fresh count on each piece, and the third telling of that stretch would never arrive.
    """
    session_id, _, whole = await _one_told_stretch(client)
    told_again = await _correct(client, session_id, whole)
    assert told_again.status_code == 200, told_again.text
    assert await _tellings(db_session, session_id) == [2]
    standing = (await _units(client, session_id))[0]

    cut = await _divide(client, session_id, standing["segment_id"], 8000)

    assert cut.status_code == 200, cut.text
    assert await _asks_for_a_person(client, session_id) is False, (
        "em dois, um erro de um a menos no portão pediria uma pessoa aqui"
    )
    db_session.expire_all()
    pieces = [
        one
        for one in await service.current_segments(db_session, session_id)
        if one.parent_id is not None
    ]
    assert [one.tellings for one in pieces] == [2, 2]


# ---------------------------------------------------------------------------
# ENG-1133: a session gone is not a take that is not this session's
# ---------------------------------------------------------------------------


async def _session_read(client: httpx.AsyncClient, session_id: str) -> httpx.Response:
    return await client.get(f"{PREFIX}/sessions/{session_id}", headers={"X-Room-Key": KEY})


async def test_a_chunk_for_a_session_the_room_does_not_hold_is_404_the_session_reads_shape(
    client: httpx.AsyncClient,
) -> None:
    absent = str(uuid.uuid4())
    take_id = await _rehearse(client, await _session(client), b"o ensaio")

    refused = await _tell(client, absent, take_id, 0, 9000, b"um trecho")
    read = await _session_read(client, absent)

    assert refused.status_code == 404, refused.text
    assert read.status_code == 404, read.text
    assert refused.json() == read.json()


async def _retro_take_of(client: httpx.AsyncClient, session_id: str) -> str:
    """A back-translation take of the session itself — not a rehearsal take of anything."""
    kept = await client.post(
        f"{PREFIX}/sessions/{session_id}/takes",
        headers=HEADERS,
        data={"kind": IRTakeKind.RETRO.value, "scope": PASSAGE},
        files={"file": ("retro.m4a", b"uma retro qualquer", "audio/mp4")},
    )
    assert kept.status_code == 200, kept.text
    return str(kept.json()["take_id"])


async def _a_take_id_that_does_not_resolve(
    client: httpx.AsyncClient, session_id: str, shape: str
) -> str:
    """The three ways `rehearsal_take_of`'s query can miss, for the session in `session_id`."""
    if shape == "of_another_session":
        return await _rehearse(client, await _session(client), b"o ensaio de outra sessao")
    if shape == "never_existed":
        return str(uuid.uuid4())
    if shape == "retro_of_this_session":
        return await _retro_take_of(client, session_id)
    raise AssertionError(shape)


@pytest.mark.parametrize("shape", ["of_another_session", "never_existed", "retro_of_this_session"])
async def test_a_chunk_naming_a_take_that_does_not_resolve_is_422_unknown_reference(
    client: httpx.AsyncClient, shape: str
) -> None:
    """`rehearsal_take_of` filters on session, id and kind together: any of the three misses
    lands on the same query returning nothing, so all three answer the same 422 — never the
    session's own 404."""
    session_id = await _session(client)
    take_id = await _a_take_id_that_does_not_resolve(client, session_id, shape)

    refused = await _tell(client, session_id, take_id, 0, 9000, b"um trecho")

    assert refused.status_code == 422, refused.text
    body = refused.json()
    assert body["code"] == "UNKNOWN_REFERENCE"
    assert take_id in body["detail"]


async def test_a_replace_for_a_session_the_room_does_not_hold_is_404_the_session_reads_shape(
    client: httpx.AsyncClient,
) -> None:
    _, take_id, whole = await _one_told_stretch(client)
    absent = str(uuid.uuid4())

    refused = await _replace(
        client,
        absent,
        whole["segment_id"],
        take_id=take_id,
        starts_ms=whole["starts_ms"],
        ends_ms=whole["ends_ms"],
        audio=b"de novo",
    )
    read = await _session_read(client, absent)

    assert refused.status_code == 404, refused.text
    assert read.status_code == 404, read.text
    assert refused.json() == read.json()


@pytest.mark.parametrize("shape", ["of_another_session", "never_existed", "retro_of_this_session"])
async def test_a_replace_naming_a_take_that_does_not_resolve_is_422_unknown_reference(
    client: httpx.AsyncClient, shape: str
) -> None:
    session_id, _, whole = await _one_told_stretch(client)
    take_id = await _a_take_id_that_does_not_resolve(client, session_id, shape)

    refused = await _replace(
        client,
        session_id,
        whole["segment_id"],
        take_id=take_id,
        starts_ms=whole["starts_ms"],
        ends_ms=whole["ends_ms"],
        audio=b"de novo",
    )

    assert refused.status_code == 422, refused.text
    body = refused.json()
    assert body["code"] == "UNKNOWN_REFERENCE"
    assert take_id in body["detail"]


async def test_a_divide_for_a_session_the_room_does_not_hold_is_404_the_session_reads_shape(
    client: httpx.AsyncClient,
) -> None:
    """Divide names no take, so it keeps its one refusal: this is the control, not a gap."""
    _, _, whole = await _one_told_stretch(client)
    absent = str(uuid.uuid4())

    refused = await _divide(client, absent, whole["segment_id"], 8000)
    read = await _session_read(client, absent)

    assert refused.status_code == 404, refused.text
    assert read.status_code == 404, read.text
    assert refused.json() == read.json()


async def test_the_room_that_stopped_says_so_in_its_own_state(client: httpx.AsyncClient) -> None:
    """The stopping survives the answer that carried it.

    The reply to the correction says `needs_person`, and a client that ignores that field would
    otherwise lose the one moment the room asked for help. It is written into the session's own
    status too, so the next read of the session finds it — the room stays stopped rather than
    having mentioned it once.
    """
    session_id, _, _ = await _one_told_stretch(client)
    for _ in range(RETELLS_BEFORE_A_WARNING):
        standing = (await _units(client, session_id))[0]
        await _correct(client, session_id, standing)

    state = await client.get(f"{PREFIX}/sessions/{session_id}", headers={"X-Room-Key": KEY})

    assert state.json()["status"] == IRSessionStatus.NEEDS_PERSON.value
