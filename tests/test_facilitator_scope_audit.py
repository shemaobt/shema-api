"""ENG-534 — every facilitator route is scoped to the caller's own teams, checked as a set.

The role gate has its own audit (ENG-438) and it passes on all eleven routes. It has to:
**holding the role is not owning the resource**, and this file exists because that
distinction was invisible to a test that only ever asked whether the door had a lock.

## Why each route is exercised twice

The refusal for "not yours" is deliberately identical to the one for "no such thing", so
that a caller cannot map the installation by asking for ids. That design has a consequence
for its own test: **an audit that asks for an id that does not exist goes green for the
wrong reason**, and would keep going green if every scope check in the codebase were
deleted tomorrow. The guarantee is, from the outside, indistinguishable from the state in
which it has failed.

So each route is asked twice:

1. a **real** resource belonging to team B, requested by facilitator A — must refuse;
2. **the same** resource, requested by B — must not refuse.

The second is what makes the first mean anything. Without it this file proves that ids
which do not exist are not served, which nobody doubted.

## Where the other scope tests live

`tests/test_facilitator_scope.py` (ENG-439) covers the same question for the Desk's team
and device routes, in depth: which project roles count as facilitating, what an
organization-only path reaches, what a platform admin reaches. This file does not repeat
any of that. What it adds is the **set**: that no facilitator route is missing a scope
check at all, which is how the five routes this slice fixed went unnoticed while that file
was green.

Read together: that one asks "is this scoping correct"; this one asks "is anything
unscoped". Neither answers the other's question, and this slice exists because the second
one had never been asked.

## Two shapes of scoping, both asserted

A route that names a resource **refuses**. A route that lists refuses nothing — it
**filters**, and the failure there is a row appearing, not a status. Both are scoping and
both are checked; what is not allowed is a route being in neither group, which is what the
coverage case below is for.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ProjectRole
from app.db.models.internalization_room import (
    IRQuestion,
    IRQuestionStatus,
    IRSession,
    IRTake,
    IRTakeKind,
)
from app.services.device import claim_device_as_facilitator, create_device
from app.services.internalization_room import questions as question_service
from app.services.internalization_room.voice_handles import to_handle
from tests.baker import (
    grant_facilitator_app_role,
    make_language,
    make_project,
    make_project_user_access,
    make_user,
)

IR = "/api/internalization-room"
DESK = "/api/facilitator"
AUDIO = {"files": {"file": ("resposta.m4a", b"resposta falada", "audio/mp4")}}


def _dependency_calls(dependant) -> set:
    found = {dependant.call}
    for sub in dependant.dependencies:
        found |= _dependency_calls(sub)
    return found


def facilitator_routes() -> list[tuple[str, str]]:
    """Every mounted route behind the facilitator role, as (method, path).

    Derived from the gate object in each route's dependency tree rather than from the path,
    because `/facilitator` in a path is a naming convention and this is not. A route added
    to either family is covered here the moment it is mounted.
    """
    from app.api.facilitator._deps import facilitator_role
    from app.main import app

    gate = getattr(facilitator_role, "dependency", facilitator_role)
    found = []
    for route in app.routes:
        dependant = getattr(route, "dependant", None)
        if dependant is None:
            continue
        calls = {getattr(c, "dependency", c) for c in _dependency_calls(dependant)}
        if gate not in calls:
            continue
        for method in sorted(getattr(route, "methods", set()) - {"HEAD", "OPTIONS"}):
            found.append((method, route.path))
    return sorted(found)


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    """The real application, so no route is out of scope by not being mounted here."""
    from app.api.internalization_room import takes as take_routes
    from app.core.database import get_db
    from app.main import app
    from app.services.internalization_room import questions as question_service

    class MemoryStore:
        def __init__(self) -> None:
            self.objects: dict[str, bytes] = {}

        async def get(self, key: str) -> bytes | None:
            return self.objects.get(key)

        async def put(self, key: str, data: bytes, content_type: str) -> None:
            self.objects[key] = data

    store = MemoryStore()
    monkeypatch.setattr(question_service, "_store", lambda *a, **kw: store)

    async def _signed_question(key: str, **kw) -> question_service.SignedAudio:
        return question_service.SignedAudio(
            url=f"https://storage.example/{key}",
            expires_at=datetime.now(UTC) + timedelta(minutes=question_service.LISTEN_MINUTES),
        )

    async def _signed_take(take, **kw) -> str:
        return f"https://storage.example/{take.storage_key}"

    monkeypatch.setattr(question_service, "listen_address", _signed_question)
    monkeypatch.setattr(take_routes, "listen_url", _signed_take)

    async def _get_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


class Facilitator:
    def __init__(self, user, project, headers: dict[str, str]) -> None:
        self.user = user
        self.project = project
        self.headers = headers


async def a_facilitator(db: AsyncSession, *, email: str) -> Facilitator:
    user = await make_user(db, email=email)
    language = await make_language(db, name=f"Lang {email}", code=email[:3])
    project = await make_project(db, language.id, name=f"Team {email}")
    await make_project_user_access(db, project.id, user.id, role=ProjectRole.FACILITATOR)
    await grant_facilitator_app_role(db, user.id)

    from app.services.auth.issue_tokens import issue_tokens

    access, _refresh = await issue_tokens(db, user)
    return Facilitator(user, project, {"Authorization": f"Bearer {access}"})


# --- one builder per route: makes a resource owned by ``owner`` and says how to ask for it


async def _a_device_of(db: AsyncSession, owner: Facilitator, tag: str) -> str:
    minted = await create_device(db)
    claimed = await claim_device_as_facilitator(
        db, user=owner.user, code=minted.claim_code, project_id=owner.project.id
    )
    return claimed.device.id


async def _a_question_of(db: AsyncSession, owner: Facilitator, tag: str) -> str:
    session = IRSession(id=f"s-{tag}", pericope="P03", project_id=owner.project.id)
    db.add(session)
    await db.flush()
    question = IRQuestion(
        id=f"q-{tag}",
        session_id=session.id,
        device_id=f"t-{tag}",
        project_id=owner.project.id,
        pericope="P03",
        status=IRQuestionStatus.OPEN,
        audio_key=f"internalization-room/questions/{tag}.m4a",
    )
    db.add(question)
    await db.commit()
    return question.id


async def _a_recorded_session_of(db: AsyncSession, owner: Facilitator, tag: str) -> tuple[str, str]:
    session = IRSession(id=f"s-{tag}", pericope="P03", project_id=owner.project.id)
    db.add(session)
    await db.flush()
    take = IRTake(
        id=f"tk-{tag}",
        session_id=session.id,
        device_id=f"t-{tag}",
        project_id=owner.project.id,
        pericope="P03",
        kind=IRTakeKind.ENSAIO,
        scope="passagem",
        storage_key=f"internalization-room/takes/{tag}.m4a",
        size_bytes=8,
        sha256="0" * 64,
        crc32c="AAAAAA==",
        content_type="audio/mp4",
    )
    db.add(take)
    await db.commit()
    return session.id, take.id


async def _claim_of(db: AsyncSession, owner: Facilitator, tag: str) -> dict:
    minted = await create_device(db)
    return {"json": {"code": minted.claim_code, "project_id": owner.project.id}}


async def _device_request(db: AsyncSession, owner: Facilitator, tag: str, **extra) -> dict:
    device_id = await _a_device_of(db, owner, tag)
    return {"path_args": {"device_id": device_id}, **extra}


#: How to build, for each route that names a resource, a request for a resource that
#: ``owner`` owns. Every mounted facilitator route must be here or in ``FILTERS`` — see
#: ``test_every_facilitator_route_is_covered_by_this_audit``.
async def refusing_routes(db: AsyncSession, owner: Facilitator, tag: str) -> list[dict]:
    """One entry per route that names a resource.

    Each carries the request for a resource ``owner`` owns and the same request for one
    that does not exist. Both are needed: the refusals have to match, and matching is what
    "indistinguishable" means.
    """
    # One question per route, not one shared by three: `reply` answers the card, and a
    # later `resolve` on the same card is then refused by a business rule that has nothing
    # to do with scope. A shared fixture would make this file fail for the wrong reason.
    heard_id = await _a_question_of(db, owner, f"h{tag}")
    reply_id = await _a_question_of(db, owner, f"r{tag}")
    resolve_id = await _a_question_of(db, owner, f"v{tag}")
    await _a_question_of(db, owner, f"k{tag}")
    #: The key route names its resource by key, so the bytes have to exist for the owner's
    #: half to mean "reached" rather than "no such audio". `_store` is the patched one.
    owned_key = f"internalization-room/questions/k{tag}.m4a"
    await question_service._store().put(owned_key, b"a equipe perguntou", "audio/mp4")
    absent_key = "internalization-room/questions/nao-existe-em-lugar-nenhum.m4a"
    session_id, take_id = await _a_recorded_session_of(db, owner, f"t{tag}")
    patch_device = await _a_device_of(db, owner, f"p{tag}")
    delete_device = await _a_device_of(db, owner, f"d{tag}")
    claim = await _claim_of(db, owner, f"c{tag}")
    absent = "nao-existe-em-lugar-nenhum"

    return [
        {
            "method": "POST",
            "owned": (f"{DESK}/devices/claim", claim),
            "absent": (
                f"{DESK}/devices/claim",
                {"json": {**claim["json"], "project_id": absent}},
            ),
            "ids": (owner.project.id, absent),
        },
        {
            "method": "PATCH",
            "owned": (f"{DESK}/devices/{patch_device}", {"json": {"label": "x"}}),
            "absent": (f"{DESK}/devices/{absent}", {"json": {"label": "x"}}),
            "ids": (patch_device, absent),
        },
        {
            "method": "DELETE",
            "owned": (f"{DESK}/devices/{delete_device}", {}),
            "absent": (f"{DESK}/devices/{absent}", {}),
            "ids": (delete_device, absent),
        },
        {
            "method": "GET",
            "owned": (f"{DESK}/teams/{owner.project.id}", {}),
            "absent": (f"{DESK}/teams/{absent}", {}),
            "ids": (owner.project.id, absent),
        },
        {
            "method": "GET",
            "owned": (f"{DESK}/teams/{owner.project.id}/devices", {}),
            "absent": (f"{DESK}/teams/{absent}/devices", {}),
            "ids": (owner.project.id, absent),
        },
        {
            "method": "GET",
            "owned": (f"{DESK}/teams/{owner.project.id}/coverage", {"params": {"pericope": "P01"}}),
            "absent": (f"{DESK}/teams/{absent}/coverage", {"params": {"pericope": "P01"}}),
            "ids": (owner.project.id, absent),
        },
        {
            "method": "GET",
            "owned": (f"{DESK}/teams/{owner.project.id}/pericopes", {}),
            "absent": (f"{DESK}/teams/{absent}/pericopes", {}),
            "ids": (owner.project.id, absent),
        },
        {
            "method": "GET",
            "owned": (f"{IR}/facilitator/questions", {"params": {"team_id": owner.project.id}}),
            "absent": (f"{IR}/facilitator/questions", {"params": {"team_id": absent}}),
            "ids": (owner.project.id, absent),
        },
        {
            "method": "GET",
            "owned": (f"{IR}/facilitator/questions/{heard_id}/audio", {}),
            "absent": (f"{IR}/facilitator/questions/{absent}/audio", {}),
            "ids": (heard_id, absent),
        },
        {
            "method": "GET",
            "owned": (f"{IR}/facilitator/questions/audio/{to_handle(owned_key)}", {}),
            "absent": (f"{IR}/facilitator/questions/audio/{to_handle(absent_key)}", {}),
            "ids": (to_handle(owned_key), to_handle(absent_key)),
        },
        {
            "method": "POST",
            "owned": (f"{IR}/facilitator/questions/{reply_id}/reply", AUDIO),
            "absent": (f"{IR}/facilitator/questions/{absent}/reply", AUDIO),
            "ids": (reply_id, absent),
        },
        {
            "method": "POST",
            "owned": (f"{IR}/facilitator/questions/{resolve_id}/resolve", {}),
            "absent": (f"{IR}/facilitator/questions/{absent}/resolve", {}),
            "ids": (resolve_id, absent),
        },
        {
            "method": "GET",
            "owned": (f"{IR}/facilitator/sessions/{session_id}/takes", {}),
            "absent": (f"{IR}/facilitator/sessions/{absent}/takes", {}),
            "ids": (session_id, absent),
        },
        {
            "method": "GET",
            "owned": (f"{IR}/facilitator/takes/{take_id}/audio", {}),
            "absent": (f"{IR}/facilitator/takes/{absent}/audio", {}),
            "ids": (take_id, absent),
        },
    ]


def _shape(body, *ids: str):
    """A response body with the caller's own ids blanked out.

    The ids are the caller's own input, so their appearing in a message tells them nothing.
    Everything else must match, which is where "belongs to another team" would show.
    """
    if not isinstance(body, dict):
        return body
    out = dict(body)
    for value in ids:
        out = {k: (v.replace(value, "<id>") if isinstance(v, str) else v) for k, v in out.items()}
    return out


#: Templates of the same set, for matching against the mounted paths.
REFUSING_TEMPLATES = {
    ("POST", f"{DESK}/devices/claim"),
    ("PATCH", f"{DESK}/devices/{{device_id}}"),
    ("DELETE", f"{DESK}/devices/{{device_id}}"),
    ("GET", f"{DESK}/teams/{{team_id}}"),
    ("GET", f"{DESK}/teams/{{team_id}}/devices"),
    ("GET", f"{DESK}/teams/{{team_id}}/coverage"),
    ("GET", f"{DESK}/teams/{{team_id}}/pericopes"),
    ("GET", f"{IR}/facilitator/questions"),
    ("GET", f"{IR}/facilitator/questions/{{question_id}}/audio"),
    ("GET", f"{IR}/facilitator/questions/audio/{{handle}}"),
    ("POST", f"{IR}/facilitator/questions/{{question_id}}/reply"),
    ("POST", f"{IR}/facilitator/questions/{{question_id}}/resolve"),
    ("GET", f"{IR}/facilitator/sessions/{{session_id}}/takes"),
    ("GET", f"{IR}/facilitator/takes/{{take_id}}/audio"),
}

#: Routes that name no resource and cannot refuse: they answer with a list, and the scoping
#: shows as a row that is absent rather than a status. Checked by its own case below.
FILTERING_TEMPLATES = {("GET", f"{DESK}/teams")}

#: Routes that carry nothing of the installation at all: the answer is the same for every
#: facilitator, so there is no scope to check and pretending to check one would be theatre.
#:
#: **An exemption list in a scope audit is the thing that rots it**, so membership here is
#: not taken on trust — the case below refuses an entry whose route could name a resource.
#: A route earns this by having no path parameter and asking for nothing but the caller.
NOTHING_TO_SCOPE = {("GET", f"{DESK}/coverage-legend")}


def test_the_audit_is_not_empty() -> None:
    """The guard every other case here depends on.

    Each case below reads "for every facilitator route, ...". Over an empty set that is
    true and worthless, and it would go green precisely when the gate object is renamed —
    the moment this file stops watching anything.
    """
    assert facilitator_routes(), (
        "nenhuma rota de facilitador foi encontrada: o portao mudou de nome e esta "
        "auditoria parou de olhar para qualquer coisa"
    )


def test_every_facilitator_route_is_covered_by_this_audit() -> None:
    """A route in neither group is a route this file silently skips.

    The set of routes is derived; what is written by hand is how to *ask* each one. This is
    what stops the two drifting apart — a new facilitator route fails here until somebody
    says which kind of scoping it has.
    """
    mounted = set(facilitator_routes())
    covered = REFUSING_TEMPLATES | FILTERING_TEMPLATES | NOTHING_TO_SCOPE

    assert mounted == covered, (
        "as rotas de facilitador mudaram e esta auditoria nao acompanhou — "
        f"sem cobertura: {sorted(mounted - covered)}; sobrando na tabela: "
        f"{sorted(covered - mounted)}"
    )


async def test_no_facilitator_route_refuses_differently_for_another_team_than_for_nothing(
    client, db_session
):
    """The first half: A asks for B's things, and for things that do not exist.

    The two answers must be the same one. Note what is *not* asserted: a particular status.
    `POST /devices/claim` refuses with 400 and `CLAIM_CODE_UNKNOWN`, which is right for it —
    what matters is that a team the caller does not facilitate is refused exactly as an
    unknown one, not that every route settled on 404.
    """
    a = await a_facilitator(db_session, email="a@example.com")
    b = await a_facilitator(db_session, email="b@example.com")

    wrong = []
    for case in await refusing_routes(db_session, b, "b"):
        method = case["method"]
        (owned_url, owned_kw), (absent_url, absent_kw) = case["owned"], case["absent"]

        theirs = await client.request(method, owned_url, headers=a.headers, **owned_kw)
        nothing = await client.request(method, absent_url, headers=a.headers, **absent_kw)

        if theirs.status_code != nothing.status_code:
            wrong.append(f"{method} {owned_url}: {theirs.status_code} vs {nothing.status_code}")
        elif _shape(theirs.json(), *case["ids"]) != _shape(nothing.json(), *case["ids"]):
            wrong.append(f"{method} {owned_url}: corpos diferentes")

    assert not wrong, (
        "estas rotas tratam 'de outra equipe' diferente de 'nao existe', e a diferenca "
        f"enumera a instalacao: {wrong}"
    )


async def test_the_same_resources_are_reachable_by_the_team_that_owns_them(client, db_session):
    """The second half, and the one that makes the first half mean anything.

    Every id used above is asked for again by its owner. If these were refused too, the
    case above would be asserting that made-up ids are refused the same way as other
    made-up ids — true of any API, scoped or not, and exactly how this audit would rot
    into decoration.
    """
    b = await a_facilitator(db_session, email="b@example.com")

    refused = []
    for case in await refusing_routes(db_session, b, "own"):
        method = case["method"]
        owned_url, owned_kw = case["owned"]
        answer = await client.request(method, owned_url, headers=b.headers, **owned_kw)
        if answer.status_code >= 400:
            refused.append(f"{method} {owned_url} -> {answer.status_code}")

    assert not refused, (
        "o dono nao alcancou o proprio recurso, entao a recusa do caso anterior nao prova "
        f"escopo — prova apenas que dois ids inexistentes sao recusados igual: {refused}"
    )


def test_a_route_exempted_from_scoping_could_not_have_been_scoped() -> None:
    """The guard on the exemption, without which `NOTHING_TO_SCOPE` is a way out.

    Every other case here proves a route scopes. This one proves the routes that claim not
    to need it are telling the truth, because the cheapest way to make this file green is to
    move a route into that set and the second cheapest is to mean it.

    The bar is what makes "nothing to scope" true rather than asserted: a route that names
    no resource in its path and asks for nothing but the caller has no installation data to
    scope. Anything with a path parameter, a query parameter or a body is naming something,
    and naming something is what a scope check is for.
    """
    from app.main import app

    for route in app.routes:
        key = None
        for method in sorted(getattr(route, "methods", set()) - {"HEAD", "OPTIONS"}):
            if (method, route.path) in NOTHING_TO_SCOPE:
                key = (method, route.path)
        if key is None:
            continue

        assert "{" not in route.path, f"{key} nomeia um recurso no caminho e nao esta isenta"

        dependant = route.dependant
        named = [p.name for p in dependant.path_params + dependant.query_params]
        assert not named, (
            f"{key} recebe {named}, entao ha algo da instalacao a escopar — "
            "tire-a de NOTHING_TO_SCOPE em vez de alargar a isencao"
        )
        assert dependant.body_params == [], f"{key} recebe um corpo e nao esta isenta"


async def test_a_listing_route_leaves_out_the_other_teams_rows(client, db_session):
    """The filtering shape: `GET /facilitator/teams` refuses nothing and must still scope.

    Asserting only that A sees their own team would pass against a route that returns
    every team on the installation, so what is asserted is B's absence — and B's team is
    built here precisely so that it could appear.
    """
    a = await a_facilitator(db_session, email="a@example.com")
    b = await a_facilitator(db_session, email="b@example.com")

    listed = await client.get(f"{DESK}/teams", headers=a.headers)

    assert listed.status_code == 200
    teams = {row["team_id"] for row in listed.json()["teams"]}
    assert a.project.id in teams, "o cenario nao provou nada: o dono nao viu a propria equipe"
    assert b.project.id not in teams, "a lista mostrou a equipe de outro facilitador"
