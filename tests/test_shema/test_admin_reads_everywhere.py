"""OBT-593: the Admin without a region reads every region as the coordination; writes only access.

Daniel, 19/oct/2026 (OBT-592), on the bancada of 14/oct: an account holding only ``admin`` saw
no project, a 404 ficha and an empty prayer wall (PME-ACE-063, PME-ORA-002,
INT-E2E-018/022/024/057).
Now its scope is every region as a **reader** (``_scope.reading_scope``) and it reads the truth of
a sensitive place everywhere (``COORDINATION_EVERYWHERE``, OBT-528's reading confirmed on
8/oct); what it may **write** is the regional half alone (``Readership.writes``), nothing for the
Admin alone — the record, the leader's link, the import and the withdrawal stay the regional
coordination's.

Held here per output: the collection and the record (a), the truth of a sensitive place for the
Admin and the reduction for everybody else, unchanged (b), one refusal per write (c), the prayer
wall across regions (e). The notice's pointer (d) is ``test_request_notices.py``'s, beside the
helpers it needs. No account here is an installation admin: they pass every guard, and a refusal
asserted with one would pass for the wrong reason — the Admin here is the ``admin`` **role**.
"""

from __future__ import annotations

import uuid

import pytest

from app.db.models.shema import ShemaProject
from app.db.models.shema_enums import ShemaPrayerVisibility, ShemaRegionKey
from tests.baker import make_user
from tests.test_shema.conftest import PREFIX, auth_header, grant, make_scoped_user

PROJECTS = f"{PREFIX}/projects"
WALL = f"{PREFIX}/prayer/requests"
AFRICA = ShemaRegionKey.AFRICA
ASIA = ShemaRegionKey.ASIA
SECRET_PLACE = "Terra Sigilosa, Vale Escondido"
SECRET_BASE = "JOCUM Vale Escondido"
OPEN_PLACE = "Campo Aberto"


async def _project(db_session, project_id: str, region: ShemaRegionKey, *, sensitive: bool):
    row = ShemaProject(
        id=project_id,
        language_name="Lingua Um" if sensitive else "Lingua Dois",
        bridge_language="Portugues",
        location=SECRET_PLACE if sensitive else OPEN_PLACE,
        team=SECRET_BASE if sensitive else "JOCUM Campo Aberto",
        sensitive_country=sensitive,
        region_key=region,
        prayer_requests=f"PEDIDO-{project_id}",
        prayer_visibility=None if sensitive else ShemaPrayerVisibility.REDE,
    )
    db_session.add(row)
    await db_session.commit()
    return row


async def _admin(db_session, shema_app, email: str = "admin@everywhere.test"):
    user = await make_user(db_session, email=email)
    await grant(db_session, user, shema_app, "admin")
    return await auth_header(db_session, user)


async def _regional(db_session, shema_app, role: str, region: ShemaRegionKey):
    user = await make_scoped_user(
        db_session,
        shema_app,
        email=f"{role.lower()}-{region.value}@everywhere.test",
        role_key=role,
        regions=[region],
    )
    return user, await auth_header(db_session, user)


@pytest.fixture()
async def two_regions(db_session):
    return (
        await _project(db_session, "sigiloso-africa", AFRICA, sensitive=True),
        await _project(db_session, "aberto-asia", ASIA, sensitive=False),
    )


# --- (a) the collection and the record ------------------------------------------------------------


async def test_the_admin_lists_and_opens_every_region(client, db_session, shema_app, two_regions):
    headers = await _admin(db_session, shema_app)

    page = await client.get(PROJECTS, headers=headers)
    records = [await client.get(f"{PROJECTS}/{p.id}", headers=headers) for p in two_regions]

    assert page.status_code == 200, page.text
    assert sorted(item["id"] for item in page.json()["items"]) == ["aberto-asia", "sigiloso-africa"]
    assert [r.status_code for r in records] == [200, 200]


async def test_a_coordinator_outside_the_region_still_gets_the_404(
    client, db_session, shema_app, two_regions
):
    """The out-of-scope 404 stays for whoever does not reach: the reach changed, not the rule."""
    _user, headers = await _regional(db_session, shema_app, "coordinator", ASIA)

    page = await client.get(PROJECTS, headers=headers)
    africa = await client.get(f"{PROJECTS}/sigiloso-africa", headers=headers)

    assert [item["id"] for item in page.json()["items"]] == ["aberto-asia"]
    assert africa.status_code == 404


# --- (b) the truth of a sensitive place -----------------------------------------------------------


async def test_the_admin_reads_the_truth_of_a_sensitive_place_in_every_region(
    client, db_session, shema_app, two_regions
):
    headers = await _admin(db_session, shema_app)

    record = (await client.get(f"{PROJECTS}/sigiloso-africa", headers=headers)).json()
    [card] = [
        c
        for c in (await client.get(PROJECTS, headers=headers)).json()["items"]
        if c["id"] == "sigiloso-africa"
    ]

    # ``locationWithheld`` is the marker — the flag, for every reader; the truth is in the values.
    assert record["readAs"] == "coordination" and record["locationWithheld"] is True
    assert record["location"] == SECRET_PLACE and record["ywamBase"] == SECRET_BASE
    assert card["readAs"] == "coordination" and card["location"] == SECRET_PLACE


@pytest.mark.parametrize(
    ("role", "read_as", "place"),
    [("obtLab", "other", "africa"), ("resourceCircle", "trusted", SECRET_PLACE)],
)
async def test_the_other_readers_of_the_region_are_exactly_as_before(
    client, db_session, shema_app, two_regions, role, read_as, place
):
    """Nothing leaked sideways: the OBT Lab still reads the reduction (the region key where the
    place was), the Resource Circle still reads the truth of its own region (OBT-571), and
    neither reaches the other region."""
    _user, headers = await _regional(db_session, shema_app, role, AFRICA)

    record = (await client.get(f"{PROJECTS}/sigiloso-africa", headers=headers)).json()
    asia = await client.get(f"{PROJECTS}/aberto-asia", headers=headers)

    assert (record["readAs"], record["location"]) == (read_as, place)
    assert record["locationWithheld"] is True
    assert asia.status_code == 404


# --- (c) one refusal per write --------------------------------------------------------------------


async def test_the_admin_does_not_write_the_record(client, db_session, shema_app, two_regions):
    headers = await _admin(db_session, shema_app)
    record = await client.get(f"{PROJECTS}/aberto-asia", headers=headers)

    patched = await client.patch(
        f"{PROJECTS}/aberto-asia",
        json={"notes": "o Admin tentou"},
        headers={**headers, "If-Match": record.headers["ETag"]},
    )
    created = await client.post(
        PROJECTS,
        json={
            "id": str(uuid.uuid4()),
            "languageName": "Nova",
            "bridgeLanguage": "Portugues",
            "team": "JOCUM Campo Aberto",
            "objective": ["NT"],
            "location": OPEN_PLACE,
        },
        headers=headers,
    )

    assert patched.status_code == 403, patched.text
    assert "writes only access" in patched.json()["detail"]
    assert created.status_code == 403, created.text
    assert "writes only access" in created.json()["detail"]
    kept = await db_session.get(ShemaProject, "aberto-asia")
    await db_session.refresh(kept)
    assert kept.notes == ""


async def test_the_admin_beside_a_coordinator_writes_only_where_it_coordinates(
    client, db_session, shema_app, two_regions
):
    """The two halves apart: an account holding ``admin`` and ``coordinator`` in Asia reads
    Africa's record (the Admin's reach) and writes Asia's and not Africa's (the coordinator's)."""
    user, headers = await _regional(db_session, shema_app, "coordinator", ASIA)
    await grant(db_session, user, shema_app, "admin")
    asia = await client.get(f"{PROJECTS}/aberto-asia", headers=headers)
    africa = await client.get(f"{PROJECTS}/sigiloso-africa", headers=headers)

    own = await client.patch(
        f"{PROJECTS}/aberto-asia",
        json={"notes": "da coordenação"},
        headers={**headers, "If-Match": asia.headers["ETag"]},
    )
    other = await client.patch(
        f"{PROJECTS}/sigiloso-africa",
        json={"notes": "fora da coordenação"},
        headers={**headers, "If-Match": africa.headers["ETag"]},
    )

    assert africa.status_code == 200 and africa.json()["location"] == SECRET_PLACE
    assert own.status_code == 200, own.text
    assert other.status_code == 403, other.text


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("POST", f"{PREFIX}/intake-links", {"projectId": "aberto-asia"}),
        ("POST", f"{PREFIX}/forms/submissions/no-such/import", None),
        ("POST", f"{PROJECTS}/aberto-asia/media/no-such/authorization/withdraw", None),
    ],
    ids=["intake-link", "import", "withdraw"],
)
async def test_the_coordinations_own_writes_still_refuse_the_admin(
    client, db_session, shema_app, two_regions, method, path, body
):
    """The leader's link, the import and the withdrawal are ``CoordinatorUser``'s, and the
    bancada's sentence stays: *Role 'coordinator' is required for this action.*"""
    headers = await _admin(db_session, shema_app)

    res = await client.request(method, path, json=body, headers=headers)

    assert res.status_code == 403, res.text
    assert "coordinator" in res.json()["detail"]


# --- (e) the prayer wall --------------------------------------------------------------------------


async def test_the_admins_prayer_wall_shows_every_region(
    client, db_session, shema_app, two_regions
):
    await _project(db_session, "aberto-africa", AFRICA, sensitive=False)
    headers = await _admin(db_session, shema_app)
    _user, africa = await _regional(db_session, shema_app, "coordinator", AFRICA)

    everywhere = await client.get(WALL, headers=headers)
    one_region = await client.get(WALL, headers=africa)

    assert everywhere.status_code == 200, everywhere.text
    assert sorted(e["text"] for e in everywhere.json()) == [
        "PEDIDO-aberto-africa",
        "PEDIDO-aberto-asia",
    ]
    assert [e["text"] for e in one_region.json()] == ["PEDIDO-aberto-africa"]
