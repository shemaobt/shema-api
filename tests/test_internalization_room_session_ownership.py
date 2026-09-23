"""ENG-1048: the rest of the room's routes refuse a session that is not the caller's project.

ENG-1031 and ENG-1046 closed this for the turn route and for the retro's finish and chunk
routes with `session_for_room_caller` — the session, when the caller names a project, only
if that project is the session's own; by id, unchanged, for the shared key, whose real
facilitator flow has always depended on reaching a session no device named it holds. Every
other route that names a session id resolved it by id alone: a device from another project
reached another team's stretches, recordings and halts before this file existed to say it
could not.

## Two shapes of "names a session"

Most of the routes below carry ``session_id`` in the path, and are found here by walking the
mounted routes the way ``test_facilitator_scope_audit.py`` walks the facilitator ones
(ENG-534) — a room-caller route added with ``{session_id}`` in its path fails
``test_every_room_caller_route_naming_a_session_is_accounted_for`` below until it is in
``COVERED`` or ``TESTED_ELSEWHERE``, so a new one born without the helper does not slip in
silently. Two name a session outside the path and the walk cannot see them: ``POST
/questions`` takes it as a query parameter, and ``POST /sessions`` takes one as the
``after_session`` field of its body, opened for the team's hand-over between passages. Both
are exercised by hand below.

## Why four routes are not re-exercised here

``POST .../turns``, ``POST .../release``, ``POST .../back-translation/chunks`` and ``POST
.../back-translation/finish`` already resolve their session through the ownership rule —
release through ``get_session_for_room_caller`` directly and unconditionally, a stricter rule
of its own (a release is numbered to a project, so even the shared key is refused on a
project-owned session) that predates this ticket and is not this ticket's to change.
``TESTED_ELSEWHERE`` names each one and where, so the completeness case still accounts for
them without rebuilding their fixtures a second time.
"""

from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSession, IRSessionStatus, IRTakeKind
from app.services.internalization_room.segments import capture_segment, final_segments
from app.services.internalization_room.sessions import create_session, get_session
from app.services.internalization_room.takes import store_take, takes_of
from tests.release_harness import KEY, PREFIX, P, a_claimed_device, team_headers
from tests.room_harness import room_client, the_bucket_is_in_memory
from tests.room_route_audit_harness import room_app_routes

TABLET = "tablet-da-sala"
ROOM_KEY_HEADERS = {"X-Room-Key": KEY, "X-Room-Device": TABLET}


def room_caller_session_routes() -> list[tuple[str, str]]:
    """Every mounted route the room's own gates reach whose path names a session.

    Built on `room_app_routes()` (ENG-1039) rather than a second walk of `app.routes` — that
    is the one place a route gated by hand, like `voice.py`'s clip, is still found, and a
    fix to how routes are discovered reaches this audit too instead of drifting from it.
    """
    found = []
    for route in room_app_routes():
        if "{session_id}" not in route.path:
            continue
        for method in sorted(getattr(route, "methods", set()) - {"HEAD", "OPTIONS"}):
            found.append((method, route.path))
    return sorted(found)


#: The nine routes this ticket fixes, behaviourally exercised below by `cases()` — held to
#: exactly this set by `test_the_exercised_cases_are_exactly_the_covered_routes`, so a route
#: added here is a route the refusal cases run against, not only a line in a table.
COVERED = {
    ("GET", f"{PREFIX}/sessions/{{session_id}}"),
    ("POST", f"{PREFIX}/sessions/{{session_id}}/needs-person"),
    ("POST", f"{PREFIX}/sessions/{{session_id}}/person-arrived"),
    ("GET", f"{PREFIX}/sessions/{{session_id}}/coverage"),
    ("POST", f"{PREFIX}/sessions/{{session_id}}/segments/{{segment_id}}/divide"),
    ("POST", f"{PREFIX}/sessions/{{session_id}}/segments/{{segment_id}}/replace"),
    ("POST", f"{PREFIX}/sessions/{{session_id}}/takes"),
    ("GET", f"{PREFIX}/sessions/{{session_id}}/takes"),
    ("GET", f"{PREFIX}/sessions/{{session_id}}/takes/{{take_id}}/audio"),
}

#: Routes that already resolve their session through the ownership rule, proved by a suite
#: of their own — named here only so a route missing from *both* tables is the one thing
#: that fails `test_every_room_caller_route_naming_a_session_is_accounted_for`.
TESTED_ELSEWHERE = {
    (
        "POST",
        f"{PREFIX}/sessions/{{session_id}}/turns",
    ): "test_internalization_room_turn_ownership.py",
    ("POST", f"{PREFIX}/sessions/{{session_id}}/release"): (
        "release_harness.py's own release cases — a stricter, pre-existing rule"
    ),
    ("POST", f"{PREFIX}/sessions/{{session_id}}/back-translation/chunks"): (
        "test_internalization_room_back_translation_ownership.py"
    ),
    ("POST", f"{PREFIX}/sessions/{{session_id}}/back-translation/finish"): (
        "test_internalization_room_back_translation_ownership.py"
    ),
    ("GET", f"{PREFIX}/voice/{{session_id}}/{{handle}}"): (
        "test_ir_a_turns_voice_is_refused_to_another_team.py"
    ),
}


def test_room_caller_session_routes_is_not_empty() -> None:
    """The guard the completeness case below depends on — see the same case in
    `test_facilitator_scope_audit.py` for why an empty set would pass for nothing.
    """
    assert room_caller_session_routes(), (
        "nenhuma rota da sala com session_id foi encontrada: o portao mudou de nome e esta "
        "auditoria parou de olhar para qualquer coisa"
    )


def test_every_room_caller_route_naming_a_session_is_accounted_for() -> None:
    """A route in neither table is a route this file silently skips.

    The set of routes is derived; which table it belongs to is written by hand. A new room
    route born with `{session_id}` in its path fails here — named — until somebody decides
    whether it is exercised here or already proven elsewhere.
    """
    mounted = set(room_caller_session_routes())
    accounted = COVERED | set(TESTED_ELSEWHERE)

    assert mounted == accounted, (
        "as rotas da sala com session_id mudaram e esta auditoria nao acompanhou — "
        f"sem cobertura: {sorted(mounted - accounted)}; sobrando nas tabelas: "
        f"{sorted(accounted - mounted)}"
    )


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    from app.api.internalization_room import segments as segments_api
    from app.api.internalization_room import takes as takes_api
    from app.services.internalization_room import questions as question_service

    bucket = the_bucket_is_in_memory(monkeypatch)
    monkeypatch.setattr(question_service, "_store", lambda *_, **__: bucket)

    async def _signed(take: Any, **_: Any) -> str:
        return f"https://storage.example/{take.storage_key}"

    monkeypatch.setattr(takes_api, "listen_url", _signed)

    async def _transcribe(*_: Any, **__: Any) -> str:
        return "explicando de novo"

    monkeypatch.setattr(segments_api, "heard", _transcribe)

    async with room_client(db_session, monkeypatch) as c:
        yield c


class Owned:
    """The resources one project owns, for one case: a session, a rehearsal take and the one
    stretch told back over it — the shape every case below needs at most of.
    """

    def __init__(self, session: Any, take: Any, segment: Any) -> None:
        self.session = session
        self.take = take
        self.segment = segment


async def _owned(db: AsyncSession, project_id: str, tag: str) -> Owned:
    session = await create_session(db, pericope=P, project_id=project_id, language="pt")
    take = await store_take(
        db,
        session_id=session.id,
        device_id=f"tablet-{tag}",
        project_id=project_id,
        pericope=P,
        kind=IRTakeKind.ENSAIO,
        scope=P,
        audio=f"a equipe ensaiou {tag}".encode(),
    )
    segment = await capture_segment(
        db,
        session,
        take_id=take.id,
        starts_ms=0,
        ends_ms=20000,
        bridge_take_id=f"retro-{tag}",
        transcript=f"a equipe contou {tag}",
    )
    return Owned(session, take, segment)


def _case(tag: str, *, method: str, path: str, expects: str = "get", **request: Any) -> dict:
    return {"tag": tag, "method": method, "path": path, "expects": expects, "request": request}


def cases(owned: Owned) -> list[dict]:
    """One entry per route this ticket fixes, keyed to the same `Owned` resources.

    `expects` says how the owner's call is read: `"get"` for a plain 200, `"stream"` for an
    SSE response only ever checked by its status (consuming its body would hang the case,
    since the stream never ends on its own), `"redirect"` for the 307 the take-audio route
    answers with instead of a body.
    """
    s, t = owned.session.id, owned.take.id
    return [
        _case("read", method="GET", path=f"/sessions/{s}"),
        _case("needs-person", method="POST", path=f"/sessions/{s}/needs-person"),
        _case("person-arrived", method="POST", path=f"/sessions/{s}/person-arrived"),
        _case("coverage", method="GET", path=f"/sessions/{s}/coverage", expects="stream"),
        _case(
            "divide",
            method="POST",
            path=f"/sessions/{s}/segments/{owned.segment.id}/divide",
            json={"at_ms": 8000},
        ),
        _case(
            "replace",
            method="POST",
            path=f"/sessions/{s}/segments/{owned.segment.id}/replace",
            data={"take_id": t, "starts_ms": "0", "ends_ms": "20000"},
            files={"file": ("trecho.m4a", b"explicando de novo", "audio/mp4")},
        ),
        _case(
            "keep-take",
            method="POST",
            path=f"/sessions/{s}/takes",
            data={"kind": "ensaio", "scope": P},
            files={"file": ("nova.m4a", b"mais uma gravacao", "audio/mp4")},
        ),
        _case("list-takes", method="GET", path=f"/sessions/{s}/takes"),
        _case(
            "take-audio",
            method="GET",
            path=f"/sessions/{s}/takes/{t}/audio",
            expects="redirect",
        ),
    ]


async def _coverage_status(db: AsyncSession, path: str, headers: dict[str, str]) -> int:
    """The coverage channel's opening status, without ever reading its body.

    `httpx.ASGITransport` awaits the whole app call before handing a response back, and this
    route's stream has no end of its own — exactly the trap
    `test_internalization_room_coverage_channel.py`'s own `_listening` helper works around,
    by driving the ASGI app directly with a `receive` that only ever answers a disconnect.
    The status is known as soon as `http.response.start` is sent, well before the generator
    that never returns is ever awaited a second time.
    """
    from fastapi import FastAPI

    from app.api.internalization_room import router as room_router
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    probe_app = FastAPI()
    probe_app.include_router(room_router, prefix=PREFIX)
    register_exception_handlers(probe_app)

    async def _get_db():
        yield db

    probe_app.dependency_overrides[get_db] = _get_db

    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [
            (b"host", b"test"),
            *((k.lower().encode(), v.encode()) for k, v in headers.items()),
        ],
        "client": ("test", 1),
        "server": ("test", 80),
    }
    status: asyncio.Future[int] = asyncio.get_running_loop().create_future()
    hung_up = asyncio.Event()

    async def receive() -> dict[str, Any]:
        await hung_up.wait()
        return {"type": "http.disconnect"}

    async def send(message: dict[str, Any]) -> None:
        if message["type"] == "http.response.start" and not status.done():
            status.set_result(message["status"])

    serving = asyncio.create_task(probe_app(scope, receive, send))
    try:
        return await asyncio.wait_for(status, timeout=5)
    finally:
        hung_up.set()
        await serving


async def _send(
    client: httpx.AsyncClient, db: AsyncSession, case: dict, headers: dict[str, str]
) -> int:
    if case["expects"] == "stream":
        return await _coverage_status(db, f"{PREFIX}{case['path']}", headers)
    url = f"{PREFIX}{case['path']}"
    resp = await client.request(case["method"], url, headers=headers, **case["request"])
    return resp.status_code


_EXPECTED_OWNER_STATUS = {"get": 200, "stream": 200, "redirect": 307}

#: The tags `cases()` builds, named once so the parametrization does not have to construct a
#: throwaway `Owned` just to read them off.
TAGS = [
    "read",
    "needs-person",
    "person-arrived",
    "coverage",
    "divide",
    "replace",
    "keep-take",
    "list-takes",
    "take-audio",
]


def test_the_exercised_cases_are_exactly_the_covered_routes() -> None:
    """`COVERED` is what the sweep checks the mounted routes against; `TAGS` and `cases()` are
    what the refusal cases run. Two hand-written lists with nothing tying them would let a
    route be accounted for above and never exercised below. Built over template ids, so each
    case's path comes back as the route it calls.
    """
    templates = Owned(
        SimpleNamespace(id="{session_id}"),
        SimpleNamespace(id="{take_id}"),
        SimpleNamespace(id="{segment_id}"),
    )
    built = cases(templates)

    assert [case["tag"] for case in built] == TAGS, (
        "TAGS e cases() divergiram: um caso existe sem ser parametrizado, ou o contrário"
    )
    assert {(case["method"], f"{PREFIX}{case['path']}") for case in built} == COVERED, (
        "as rotas exercidas por cases() não são as de COVERED: uma rota está na tabela sem ser "
        "testada, ou é testada sem estar na tabela"
    )


async def _verify_untouched(db: AsyncSession, tag: str, owned: Owned) -> None:
    """What a refused call must not have moved, checked against the resources it was asked
    to act on — a status code alone would not catch a route that refuses but writes anyway.
    """
    if tag == "divide":
        segments = await final_segments(db, owned.session.id)
        assert len(segments) == 1, "um estranho dividiu um trecho de outro projeto"
    elif tag == "replace":
        segments = await final_segments(db, owned.session.id)
        assert segments[0].transcript == owned.segment.transcript, (
            "um estranho substituiu a fala de um trecho de outro projeto"
        )
    elif tag == "keep-take":
        takes = await takes_of(db, owned.session.id)
        assert len(takes) == 1, "um estranho gravou uma tomada numa sessão de outro projeto"
    elif tag == "needs-person":
        session = await get_session(db, owned.session.id)
        assert session.status is IRSessionStatus.IN_PROGRESS, (
            "um estranho parou a sala de outro projeto"
        )
    elif tag == "person-arrived":
        session = await get_session(db, owned.session.id)
        assert session.person_arrived_at is None, (
            "um estranho marcou presença numa sala de outro projeto"
        )


@pytest.mark.parametrize("tag", TAGS)
async def test_a_device_of_another_project_is_refused_before_any_work(
    client: httpx.AsyncClient, db_session: AsyncSession, tag: str
) -> None:
    owner, owner_credential = await a_claimed_device(db_session, email=f"owner-{tag}@example.com")
    _stranger, stranger_credential = await a_claimed_device(
        db_session, email=f"stranger-{tag}@example.com"
    )
    owned = await _owned(db_session, owner.id, tag)
    case = next(c for c in cases(owned) if c["tag"] == tag)

    refused = await _send(client, db_session, case, team_headers(stranger_credential))

    assert refused == 404, f"{tag}: esperava 404 para outro projeto, veio {refused}"
    await _verify_untouched(db_session, tag, owned)

    allowed = await _send(client, db_session, case, team_headers(owner_credential))

    assert allowed == _EXPECTED_OWNER_STATUS[case["expects"]], (
        f"{tag}: o dono deixou de alcançar o próprio recurso, veio {allowed}"
    )


@pytest.mark.parametrize("tag", TAGS)
async def test_a_room_key_caller_still_reaches_a_project_owned_session(
    client: httpx.AsyncClient, db_session: AsyncSession, tag: str
) -> None:
    """The shared key names no device and so no project — `_deps.py`'s own "dated
    compromise, not a design" — and every one of these routes kept working for it before
    this ticket. `session_for_room_caller` preserves that by construction; this proves it.
    """
    owner, _credential = await a_claimed_device(db_session, email=f"key-owner-{tag}@example.com")
    owned = await _owned(db_session, owner.id, f"key-{tag}")
    case = next(c for c in cases(owned) if c["tag"] == tag)

    allowed = await _send(client, db_session, case, ROOM_KEY_HEADERS)

    assert allowed == _EXPECTED_OWNER_STATUS[case["expects"]], (
        f"{tag}: a chave da sala deixou de alcançar uma sessão com dono, veio {allowed}"
    )


# ---------------------------------------------------------------------------
# The two routes that name a session outside the path: audited by hand, since
# `room_caller_session_routes()` only ever looks at path templates.
# ---------------------------------------------------------------------------


async def test_a_question_is_refused_for_another_projects_session(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """`POST /questions` names its session as `?session_id=`, not in the path."""
    owner, owner_credential = await a_claimed_device(db_session, email="owner-q@example.com")
    _stranger, stranger_credential = await a_claimed_device(
        db_session, email="stranger-q@example.com"
    )
    session = await create_session(db_session, pericope=P, project_id=owner.id, language="pt")

    refused = await client.post(
        f"{PREFIX}/questions",
        params={"session_id": session.id},
        headers=team_headers(stranger_credential),
        files={"file": ("pergunta.m4a", b"pergunta", "audio/mp4")},
    )
    assert refused.status_code == 404, refused.text[:300]

    allowed = await client.post(
        f"{PREFIX}/questions",
        params={"session_id": session.id},
        headers=team_headers(owner_credential),
        files={"file": ("pergunta.m4a", b"pergunta", "audio/mp4")},
    )
    assert allowed.status_code == 200, allowed.text[:300]


async def test_a_hand_over_is_refused_from_another_projects_session(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """`POST /sessions` names a second session as the `after_session` field of its body —
    the panorama's own opening, carried over into the passage the team enters next.
    """
    owner, owner_credential = await a_claimed_device(db_session, email="owner-h@example.com")
    _stranger, stranger_credential = await a_claimed_device(
        db_session, email="stranger-h@example.com"
    )
    previous = await create_session(
        db_session, pericope="OV", project_id=owner.id, language="pt", after_panorama=False
    )
    before = await _session_row_count(db_session)

    refused = await client.post(
        f"{PREFIX}/sessions",
        headers=team_headers(stranger_credential),
        json={"pericope": P, "after_session": previous.id},
    )
    assert refused.status_code == 404, refused.text[:300]

    after = await _session_row_count(db_session)
    assert after == before, (
        f"uma sessao orfa ficou para tras num hand-over recusado por dono de outro projeto: "
        f"{before} antes, {after} depois"
    )

    reread = await get_session(db_session, previous.id)
    assert reread.status is IRSessionStatus.IN_PROGRESS, (
        "um estranho mexeu na sessão anterior de outro projeto pelo hand-over"
    )

    allowed = await client.post(
        f"{PREFIX}/sessions",
        headers=team_headers(owner_credential),
        json={"pericope": P, "after_session": previous.id},
    )
    assert allowed.status_code == 200, allowed.text[:300]


async def _session_row_count(db: AsyncSession) -> int:
    result = await db.execute(select(func.count()).select_from(IRSession))
    return result.scalar_one()


async def test_a_hand_over_naming_no_such_session_leaves_no_new_session(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """`POST /sessions` reads `after_session` before it opens one of its own (ENG-1050).

    A hand-over from a session that was never written — not somebody else's, simply absent —
    answers the same 404 `get_session` gives any missing id. The session this request was
    about to open must not be left behind for a hand-over that never happened.
    """
    _owner, owner_credential = await a_claimed_device(db_session, email="owner-orphan@example.com")
    before = await _session_row_count(db_session)

    refused = await client.post(
        f"{PREFIX}/sessions",
        headers=team_headers(owner_credential),
        json={"pericope": P, "after_session": str(uuid.uuid4())},
    )
    assert refused.status_code == 404, refused.text[:300]

    after = await _session_row_count(db_session)
    assert after == before, (
        f"uma sessao orfa ficou para tras num hand-over para um after_session inexistente: "
        f"{before} antes, {after} depois"
    )
