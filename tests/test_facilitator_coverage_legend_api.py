"""ENG-530 — the coverage legend, served once rather than repeated on every bead.

Every test here drives the route over HTTP and asserts on what a client receives. None
asserts on where the catalogue lives or on how the loader reads it — that is ENG-442's file
and its own tests.

Three of these carry the slice, and one pair of them looks redundant and is not.

`test_the_names_are_the_catalogues_own_words` and
`test_the_route_reads_the_catalogue_rather_than_a_copy_of_its_own` go red together on a route
that invents its own text — but a table copied out of `legend.json` **correctly** turns only
the second of them red. Measured: the shipped words hard-coded for `absence` leave the first
green. A copy that agrees today is exactly the duplication ENG-442 exists to prevent, because
it agrees until somebody edits one of the two.

The next test substitutes the enum the loader walks. That is the only way to reach a state
this repository does not have yet, and it is the state the whole slice exists to refuse: a value
in `CoverageStatus` that nobody has named. Reading `legend.json` and finding it complete
proves nothing, because the enum is the half that moves.

The one after it is the same substitution pointed the other way, and it is the criterion
that cannot be written any other way: `partially_engaged` is already in the catalogue and
arrives in `CoverageStatus` with ENG-441, so adding a state must cost an enum member and a
catalogue entry and **nothing here**.
"""

from __future__ import annotations

import enum

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.internalization_room import CoverageLegend
from app.services.internalization_room.canon import labels
from app.services.internalization_room.canon.elements import ElementKind
from app.services.internalization_room.canon.labels import LANGUAGES, ElementLabelsBroken
from app.services.internalization_room.coverage import CoverageStatus
from tests.baker import grant_facilitator_app_role, make_user

LEGEND_URL = "/api/facilitator/coverage-legend"


@pytest.fixture()
async def client(db_session: AsyncSession):
    from fastapi import FastAPI

    from app.api.facilitator.legend import facilitator_legend_router
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    test_app = FastAPI()
    test_app.include_router(facilitator_legend_router, prefix=LEGEND_URL)
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app, raise_app_exceptions=True)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def auth_header(db: AsyncSession, user) -> dict[str, str]:
    from app.services.auth.issue_tokens import issue_tokens

    access, _refresh = await issue_tokens(db, user)
    return {"Authorization": f"Bearer {access}"}


async def a_signed_in_caller(db: AsyncSession) -> dict[str, str]:
    """A facilitator, not merely somebody with an account.

    The role is what the door asks for since ENG-438. It is granted here rather than left out
    because these tests are about the legend; that the door refuses everyone else is
    `test_facilitator_role_gate.py`'s subject and this route is in its table.
    """
    user = await make_user(db, email="facilitator@example.com")
    await grant_facilitator_app_role(db, user.id)
    return await auth_header(db, user)


def _served(body: dict, group: str) -> dict[str, dict[str, str]]:
    return {entry["value"]: entry for entry in body[group]}


async def test_every_state_and_kind_reaches_the_desk_named_in_every_language(client, db_session):
    """Driven by the enums, so a value added elsewhere cannot ship as a raw identifier.

    A written list of three would have gone green over the fourth state ENG-441 brings,
    which is the whole failure this route exists to prevent.
    """
    response = await client.get(LEGEND_URL, headers=await a_signed_in_caller(db_session))

    assert response.status_code == 200
    body = response.json()
    assert set(_served(body, "coverage_status")) == {status.value for status in CoverageStatus}
    assert set(_served(body, "element_kind")) == {kind.value for kind in ElementKind}
    for group in ("coverage_status", "element_kind"):
        for value, entry in _served(body, group).items():
            for language in LANGUAGES:
                assert entry[f"label_{language}"].strip(), f"{value} has no {language} name"


async def test_the_names_are_the_catalogues_own_words(client, db_session):
    """The shipped text reaches the client verbatim, so no client needs a table of its own."""
    response = await client.get(LEGEND_URL, headers=await a_signed_in_caller(db_session))

    absence = _served(response.json(), "element_kind")["absence"]
    assert absence["label_pt"] == "Ausência significativa"
    assert absence["label_en"] == "Significant absence"
    assert absence["label_es"] == "Ausencia significativa"


async def test_the_route_reads_the_catalogue_rather_than_a_copy_of_its_own(
    client, db_session, monkeypatch
):
    """Answered from `legend()`, whatever it says — a second copy of the names is red here."""
    from app.api.facilitator import legend as route

    invented = CoverageLegend(
        coverage_status={
            status.value: dict.fromkeys(LANGUAGES, f"state {status.value}")
            for status in CoverageStatus
        },
        element_kind={
            kind.value: dict.fromkeys(LANGUAGES, f"kind {kind.value}") for kind in ElementKind
        },
    )
    monkeypatch.setattr(route, "legend", lambda: invented)

    response = await client.get(LEGEND_URL, headers=await a_signed_in_caller(db_session))

    assert _served(response.json(), "element_kind")["absence"]["label_pt"] == "kind absence"


async def test_a_state_nobody_has_named_is_refused_rather_than_served_raw(
    client, db_session, monkeypatch
):
    """The enum is the half that moves, and a name for a new value is not automatic.

    Substituting the enum the loader walks is the only way to reach a value this repository
    does not have yet. What must not happen is the response arriving with three states in it
    and the fourth quietly missing.
    """

    class GrownStatus(enum.StrEnum):
        NOT_ENCOUNTERED = "not_encountered"
        SURFACED = "surfaced"
        ENGAGED = "engaged"
        NEARLY_THERE = "nearly_there"

    monkeypatch.setattr(labels, "CoverageStatus", GrownStatus)

    with pytest.raises(ElementLabelsBroken) as refused:
        await client.get(LEGEND_URL, headers=await a_signed_in_caller(db_session))

    assert "nearly_there" in str(refused.value)


async def test_a_kind_nobody_has_named_is_refused_rather_than_served_raw(
    client, db_session, monkeypatch
):
    class GrownKind(enum.StrEnum):
        SCENE = "scene"
        BEING = "being"
        PLACE = "place"
        OBJECT = "object"
        TIME = "time"
        ABSENCE = "absence"
        PRESERVED = "preserved"
        GESTURE = "gesture"

    monkeypatch.setattr(labels, "ElementKind", GrownKind)

    with pytest.raises(ElementLabelsBroken) as refused:
        await client.get(LEGEND_URL, headers=await a_signed_in_caller(db_session))

    assert "gesture" in str(refused.value)


async def test_a_state_added_to_the_enum_and_the_catalogue_needs_no_edit_here(
    client, db_session, monkeypatch
):
    """ENG-441's fourth state, arriving with nothing in this slice to change.

    `partially_engaged` is already written in `legend.json` and is waiting on the enum. This
    is what "the four states are served" means today: three now, four the instant the enum
    grows, and the proof is that this test touches neither the route nor the catalogue.
    """

    class WithPartiallyEngaged(enum.StrEnum):
        NOT_ENCOUNTERED = "not_encountered"
        SURFACED = "surfaced"
        PARTIALLY_ENGAGED = "partially_engaged"
        ENGAGED = "engaged"

    monkeypatch.setattr(labels, "CoverageStatus", WithPartiallyEngaged)

    response = await client.get(LEGEND_URL, headers=await a_signed_in_caller(db_session))

    served = _served(response.json(), "coverage_status")
    assert set(served) == {status.value for status in WithPartiallyEngaged}
    assert served["partially_engaged"]["label_pt"] == "Retomado"
    assert served["partially_engaged"]["label_en"] == "Taken up"
    assert served["partially_engaged"]["label_es"] == "Retomado"


async def test_the_legend_arrives_in_the_order_the_enums_declare(client, db_session):
    """A legend is read as a progression, and the order is the server's to serve.

    `not_encountered → surfaced → engaged` is the order a bead travels in, and the kinds are
    the canon's own grouping. A client that had to sort would be deciding it a second time.
    """
    body = (await client.get(LEGEND_URL, headers=await a_signed_in_caller(db_session))).json()

    assert [e["value"] for e in body["coverage_status"]] == [s.value for s in CoverageStatus]
    assert [e["value"] for e in body["element_kind"]] == [k.value for k in ElementKind]


async def test_a_caller_who_is_not_signed_in_is_refused(client):
    """The legend names nothing about the installation, and it is still behind the door.

    Every route under `/api/facilitator` takes the same dependency; a single one that did
    not would be the one somebody points at later to argue the others need not either.
    """
    response = await client.get(LEGEND_URL)

    assert response.status_code in (401, 403)


async def test_the_route_is_reachable_in_the_application_that_is_deployed():
    """Every test above builds its own app, so all of them stay green on an unmounted router.

    What this asserts is reachability and not the mounting: an unauthenticated call to the
    real application answers the door's refusal rather than "no such path".
    """
    from app.main import app

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as caller:
        response = await caller.get(LEGEND_URL)

    assert response.status_code != 404, f"{LEGEND_URL} is not served by the application"
    assert response.status_code in (401, 403)
