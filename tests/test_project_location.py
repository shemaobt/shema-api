"""A project's location over the wire: what the PATCH clears, keeps and refuses, and what the
create refuses.

The coordinates are optional — a location can be only a name — but they travel as a pair and
they sit on the globe. The PATCH judges the pair on what the request sent, so a field left
out is a field left alone and a field sent as ``null`` is a field cleared
(shemaobt/shema-api#566).
"""

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.project import Project
from tests.baker import make_language, make_project, make_user


@pytest.fixture()
async def client(db_session: AsyncSession):
    """The real application, because the 422 is written by its own validation handler."""
    from app.core.database import get_db
    from app.main import app

    async def _get_db():
        yield db_session

    app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.pop(get_db, None)


async def _admin_headers(db_session: AsyncSession) -> dict[str, str]:
    from app.services.auth.issue_tokens import issue_tokens

    admin = await make_user(db_session, email="admin@location.com", is_platform_admin=True)
    access, _refresh = await issue_tokens(db_session, admin)
    return {"Authorization": f"Bearer {access}"}


async def _located_project(db_session: AsyncSession) -> Project:
    lang = await make_language(db_session, code="loc")
    return await make_project(
        db_session,
        language_id=lang.id,
        name="Located",
        latitude=-3.1,
        longitude=-60.0,
        location_display_name="Manaus",
    )


async def _reread(db_session: AsyncSession, project: Project) -> Project:
    await db_session.refresh(project)
    return project


HALF_PAIRS = [
    pytest.param({"latitude": 10.0}, id="latitude-only"),
    pytest.param({"longitude": 10.0}, id="longitude-only"),
    pytest.param({"latitude": None}, id="latitude-null-only"),
    pytest.param({"longitude": None}, id="longitude-null-only"),
    pytest.param({"latitude": 10.0, "longitude": None}, id="latitude-with-null-longitude"),
    pytest.param({"latitude": None, "longitude": 10.0}, id="longitude-with-null-latitude"),
]

OFF_THE_GLOBE = [
    pytest.param({"latitude": 95.0, "longitude": 0.0}, id="latitude-95"),
    pytest.param({"latitude": 90.0001, "longitude": 0.0}, id="latitude-90.0001"),
    pytest.param({"latitude": -90.0001, "longitude": 0.0}, id="latitude-minus-90.0001"),
    pytest.param({"latitude": 0.0, "longitude": 200.0}, id="longitude-200"),
    pytest.param({"latitude": 0.0, "longitude": 180.0001}, id="longitude-180.0001"),
    pytest.param({"latitude": 0.0, "longitude": -180.0001}, id="longitude-minus-180.0001"),
]

NOT_A_NUMBER = [
    pytest.param('{"latitude": NaN, "longitude": 0}', id="latitude-nan"),
    pytest.param('{"latitude": 0, "longitude": NaN}', id="longitude-nan"),
    pytest.param('{"latitude": Infinity, "longitude": 0}', id="latitude-infinity"),
    pytest.param('{"latitude": 0, "longitude": -Infinity}', id="longitude-minus-infinity"),
]

GLOBE_EDGES = [
    pytest.param(90.0, 180.0, id="north-east"),
    pytest.param(-90.0, -180.0, id="south-west"),
    pytest.param(90.0, -180.0, id="north-west"),
    pytest.param(-90.0, 180.0, id="south-east"),
]


async def test_patch_with_three_nulls_clears_the_whole_location(client, db_session) -> None:
    """The console's *Clear location* sends this body; it used to answer 200 and keep all."""
    project = await _located_project(db_session)
    headers = await _admin_headers(db_session)

    resp = await client.patch(
        f"/api/projects/{project.id}/location",
        json={"latitude": None, "longitude": None, "location_display_name": None},
        headers=headers,
    )

    assert resp.status_code == 200
    body = resp.json()
    assert (body["latitude"], body["longitude"], body["location_display_name"]) == (
        None,
        None,
        None,
    )
    stored = await _reread(db_session, project)
    assert (stored.latitude, stored.longitude, stored.location_display_name) == (None, None, None)


async def test_patch_clearing_the_coordinates_keeps_the_name(client, db_session) -> None:
    project = await _located_project(db_session)
    headers = await _admin_headers(db_session)

    resp = await client.patch(
        f"/api/projects/{project.id}/location",
        json={"latitude": None, "longitude": None},
        headers=headers,
    )

    assert resp.status_code == 200
    stored = await _reread(db_session, project)
    assert (stored.latitude, stored.longitude) == (None, None)
    assert stored.location_display_name == "Manaus"


async def test_patch_with_only_the_name_keeps_the_coordinates(client, db_session) -> None:
    project = await _located_project(db_session)
    headers = await _admin_headers(db_session)

    resp = await client.patch(
        f"/api/projects/{project.id}/location",
        json={"location_display_name": "Manaus, Amazonas"},
        headers=headers,
    )

    assert resp.status_code == 200
    stored = await _reread(db_session, project)
    assert (stored.latitude, stored.longitude) == (-3.1, -60.0)
    assert stored.location_display_name == "Manaus, Amazonas"


async def test_patch_clearing_only_the_name_keeps_the_coordinates(client, db_session) -> None:
    project = await _located_project(db_session)
    headers = await _admin_headers(db_session)

    resp = await client.patch(
        f"/api/projects/{project.id}/location",
        json={"location_display_name": None},
        headers=headers,
    )

    assert resp.status_code == 200
    stored = await _reread(db_session, project)
    assert (stored.latitude, stored.longitude) == (-3.1, -60.0)
    assert stored.location_display_name is None


async def test_patch_with_coordinates_only_keeps_the_name(client, db_session) -> None:
    project = await _located_project(db_session)
    headers = await _admin_headers(db_session)

    resp = await client.patch(
        f"/api/projects/{project.id}/location",
        json={"latitude": 1.5, "longitude": 2.5},
        headers=headers,
    )

    assert resp.status_code == 200
    stored = await _reread(db_session, project)
    assert (stored.latitude, stored.longitude) == (1.5, 2.5)
    assert stored.location_display_name == "Manaus"


async def test_patch_gives_a_location_that_is_only_a_name(client, db_session) -> None:
    lang = await make_language(db_session, code="nam")
    project = await make_project(db_session, language_id=lang.id, name="Unlocated")
    headers = await _admin_headers(db_session)

    resp = await client.patch(
        f"/api/projects/{project.id}/location",
        json={"latitude": None, "longitude": None, "location_display_name": "Alto Xingu"},
        headers=headers,
    )

    assert resp.status_code == 200
    stored = await _reread(db_session, project)
    assert (stored.latitude, stored.longitude) == (None, None)
    assert stored.location_display_name == "Alto Xingu"


@pytest.mark.parametrize("body", HALF_PAIRS)
async def test_patch_with_half_a_pair_is_refused_and_changes_nothing(
    client, db_session, body
) -> None:
    project = await _located_project(db_session)
    headers = await _admin_headers(db_session)

    resp = await client.patch(f"/api/projects/{project.id}/location", json=body, headers=headers)

    assert resp.status_code == 422
    stored = await _reread(db_session, project)
    assert (stored.latitude, stored.longitude) == (-3.1, -60.0)


@pytest.mark.parametrize("body", OFF_THE_GLOBE)
async def test_patch_with_a_point_off_the_globe_is_refused(client, db_session, body) -> None:
    project = await _located_project(db_session)
    headers = await _admin_headers(db_session)

    resp = await client.patch(f"/api/projects/{project.id}/location", json=body, headers=headers)

    assert resp.status_code == 422
    stored = await _reread(db_session, project)
    assert (stored.latitude, stored.longitude) == (-3.1, -60.0)


@pytest.mark.parametrize("raw", NOT_A_NUMBER)
async def test_patch_with_nan_or_infinity_is_refused(client, db_session, raw) -> None:
    """``json.loads`` reads ``NaN`` and ``Infinity``, so they do reach the model."""
    project = await _located_project(db_session)
    headers = {**await _admin_headers(db_session), "Content-Type": "application/json"}

    resp = await client.patch(f"/api/projects/{project.id}/location", content=raw, headers=headers)

    assert resp.status_code == 422
    stored = await _reread(db_session, project)
    assert (stored.latitude, stored.longitude) == (-3.1, -60.0)


@pytest.mark.parametrize(("latitude", "longitude"), GLOBE_EDGES)
async def test_patch_accepts_the_edges_of_the_globe(
    client, db_session, latitude, longitude
) -> None:
    project = await _located_project(db_session)
    headers = await _admin_headers(db_session)

    resp = await client.patch(
        f"/api/projects/{project.id}/location",
        json={"latitude": latitude, "longitude": longitude},
        headers=headers,
    )

    assert resp.status_code == 200
    stored = await _reread(db_session, project)
    assert (stored.latitude, stored.longitude) == (latitude, longitude)


async def _post_project(client, db_session, **location) -> httpx.Response:
    lang = await make_language(db_session, code="new")
    headers = await _admin_headers(db_session)
    return await client.post(
        "/api/projects",
        json={"name": "New", "language_id": lang.id, **location},
        headers=headers,
    )


async def test_create_with_a_location_that_is_only_a_name_is_accepted(client, db_session) -> None:
    resp = await _post_project(client, db_session, location_display_name="Alto Xingu")

    assert resp.status_code == 201
    body = resp.json()
    assert (body["latitude"], body["longitude"]) == (None, None)
    assert body["location_display_name"] == "Alto Xingu"


@pytest.mark.parametrize(
    "location",
    [
        pytest.param({"latitude": 10.0}, id="latitude-only"),
        pytest.param({"longitude": 10.0}, id="longitude-only"),
        pytest.param({"latitude": 10.0, "longitude": None}, id="latitude-with-null-longitude"),
        pytest.param({"latitude": None, "longitude": 10.0}, id="longitude-with-null-latitude"),
    ],
)
async def test_create_with_half_a_pair_is_refused(client, db_session, location) -> None:
    resp = await _post_project(client, db_session, **location)

    assert resp.status_code == 422


@pytest.mark.parametrize("location", OFF_THE_GLOBE)
async def test_create_with_a_point_off_the_globe_is_refused(client, db_session, location) -> None:
    resp = await _post_project(client, db_session, **location)

    assert resp.status_code == 422


@pytest.mark.parametrize("raw", NOT_A_NUMBER)
async def test_create_with_nan_or_infinity_is_refused(client, db_session, raw) -> None:
    lang = await make_language(db_session, code="nan")
    headers = {**await _admin_headers(db_session), "Content-Type": "application/json"}
    body = raw.replace("{", f'{{"name": "New", "language_id": "{lang.id}", ', 1)

    resp = await client.post("/api/projects", content=body, headers=headers)

    assert resp.status_code == 422


@pytest.mark.parametrize(("latitude", "longitude"), GLOBE_EDGES)
async def test_create_accepts_the_edges_of_the_globe(
    client, db_session, latitude, longitude
) -> None:
    resp = await _post_project(client, db_session, latitude=latitude, longitude=longitude)

    assert resp.status_code == 201
    assert (resp.json()["latitude"], resp.json()["longitude"]) == (latitude, longitude)
