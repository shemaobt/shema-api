"""A sensitive project's prayer request is the team's own sentence, kept from the OBT Lab (OBT-655).

API-PRIV-002 and 022, E2E run of 28/out/2026: on the P-SENS record the OBT Lab read everything that
names the place reduced — and the prayer request whole, *Orem pela proteção da equipe em Minya*,
in a field it could type over. The request is raised in the health assessment and the OBT Lab is
in its audience (``_consent.PRAYER_AUDIENCE``), but the record's free text on a withheld project
is coordination's (OBT-556), and the request was never on that list. Levi, 28/out/2026, the
issue's recommendation, for Karina to validate: on a withheld record the request and its recording
go with the notes — ``""`` to every reader who does not read the truth, and refused on write.

Asserted for the OBT Lab against the coordination and the Admin, who read it, against the Resource
Circle, which reads the truth and still only what the team authorized, and against a cleared
record, which the OBT Lab reads and writes as before. No account here is an installation admin:
they pass every guard, and a refusal asserted with one would pass for the wrong reason.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.db.models.shema import ShemaProject
from app.db.models.shema_enums import ShemaPrayerVisibility, ShemaRegionKey
from app.db.models.shema_health import ShemaHealthAssessment
from tests.baker import make_user
from tests.test_shema.conftest import PREFIX, auth_header, grant, make_scoped_user

PROJECTS = f"{PREFIX}/projects"

#: The region the records live in — ``other``, because the invented places name no country the
#: region map knows, so a save keeps the record here.
HERE = ShemaRegionKey.OTHER

WITHHELD_ID = "5d0c3e7a-9b21-4f6e-8a14-6e2f0b9c7d61"
CLEARED_ID = "5d0c3e7a-9b21-4f6e-8a14-6e2f0b9c7d62"
KEPT_ID = "5d0c3e7a-9b21-4f6e-8a14-6e2f0b9c7d63"

#: What the team asked for, naming where it is. Long enough not to appear by accident.
REQUEST = "PEDIDO-SIGILOSO orem pela proteção da equipe no Vale Escondido"
RECORDING = "shema-private/pedidos/vale-escondido.webm"


async def _seed(
    db_session,
    project_id: str,
    *,
    sensitive: bool,
    visibility: ShemaPrayerVisibility | None = None,
) -> ShemaProject:
    row = ShemaProject(
        id=project_id,
        language_name="Lingua Oracao",
        bridge_language="Portugues",
        location="Terra Sigilosa, Vale Escondido" if sensitive else "Campo Aberto",
        sensitive_country=sensitive,
        region_key=HERE,
        prayer_requests=REQUEST,
        prayer_requests_audio=RECORDING,
        prayer_visibility=visibility,
    )
    db_session.add(row)
    await db_session.commit()
    return row


@pytest.fixture()
async def withheld(db_session) -> ShemaProject:
    return await _seed(db_session, WITHHELD_ID, sensitive=True)


@pytest.fixture()
async def cleared(db_session) -> ShemaProject:
    return await _seed(db_session, CLEARED_ID, sensitive=False)


async def _headers(db_session, shema_app, role: str, *, email: str | None = None):
    user = await make_scoped_user(
        db_session,
        shema_app,
        email=email or f"{role.lower()}@pedido-retido.test",
        role_key=role,
        regions=[HERE],
    )
    return await auth_header(db_session, user)


async def _admin(db_session, shema_app):
    """The ``admin`` role — not an installation admin — which reads every region as coordination."""
    user = await make_user(db_session, email="admin@pedido-retido.test")
    await grant(db_session, user, shema_app, "admin")
    return await auth_header(db_session, user)


async def _read(client, headers, project_id: str = WITHHELD_ID):
    res = await client.get(f"{PROJECTS}/{project_id}", headers=headers)
    assert res.status_code == 200, res.text
    return res


async def _stored(db_session, project_id: str = WITHHELD_ID) -> ShemaProject:
    stmt = (
        select(ShemaProject)
        .where(ShemaProject.id == project_id)
        .execution_options(populate_existing=True)
    )
    return (await db_session.execute(stmt)).scalar_one()


# --- the read ------------------------------------------------------------------------------------


@pytest.mark.parametrize("visibility", [None, ShemaPrayerVisibility.REDE])
async def test_the_obt_lab_reads_a_sensitive_projects_prayer_request_blank(
    client, db_session, shema_app, visibility
) -> None:
    """**The DoD's first test.** Whatever the team authorized: the wall carries what the
    coordination released (OBT-575), never this column. The visibility stays — it names nothing."""
    await _seed(db_session, WITHHELD_ID, sensitive=True, visibility=visibility)

    res = await _read(client, await _headers(db_session, shema_app, "obtLab"))

    body = res.json()
    assert (body["readAs"], body["locationWithheld"]) == ("other", True)
    assert (body["prayerRequests"], body["prayerRequestsAudio"]) == ("", "")
    assert REQUEST not in res.text and RECORDING not in res.text
    assert body["prayerVisibility"] == (visibility.value if visibility else None)


@pytest.mark.parametrize("visibility", [None, ShemaPrayerVisibility.REDE])
async def test_the_coordination_reads_a_sensitive_projects_prayer_request(
    client, db_session, shema_app, visibility
) -> None:
    """**The DoD's second test**: the region's coordinator reads every word, kept or shared."""
    await _seed(db_session, WITHHELD_ID, sensitive=True, visibility=visibility)

    body = (await _read(client, await _headers(db_session, shema_app, "coordinator"))).json()

    assert body["readAs"] == "coordination"
    assert (body["prayerRequests"], body["prayerRequestsAudio"]) == (REQUEST, RECORDING)


@pytest.mark.parametrize("visibility", [None, ShemaPrayerVisibility.REDE])
async def test_the_admin_reads_a_sensitive_projects_request_as_it_reads_any_other(
    client, db_session, shema_app, visibility
) -> None:
    """The Admin reads the place as the coordination (OBT-528) and keeps reading the request as
    before: whole once the team shared it, and — being outside ``_consent.PRAYER_AUDIENCE``, as it
    is outside the health audience — ``""`` while the team keeps it, on any record alike."""
    await _seed(db_session, WITHHELD_ID, sensitive=True, visibility=visibility)
    await _seed(db_session, CLEARED_ID, sensitive=False, visibility=visibility)
    admin = await _admin(db_session, shema_app)

    sensitive = (await _read(client, admin, WITHHELD_ID)).json()
    cleared = (await _read(client, admin, CLEARED_ID)).json()

    assert sensitive["readAs"] == "coordination"
    assert sensitive["prayerRequests"] == cleared["prayerRequests"]
    assert sensitive["prayerRequests"] == (REQUEST if visibility else "")


async def test_the_resource_circle_reads_a_sensitive_projects_request_as_the_team_authorized_it(
    client, db_session, shema_app
) -> None:
    """The Circle reads the truth of a sensitive place (OBT-571), and the consent rule over the
    request is the one it always was: the request the team shared, whole; the one it kept,
    ``""``."""
    shared = await _seed(
        db_session, WITHHELD_ID, sensitive=True, visibility=ShemaPrayerVisibility.REDE
    )
    kept = await _seed(db_session, KEPT_ID, sensitive=True)
    circle = await _headers(db_session, shema_app, "resourceCircle")

    shared_body = (await _read(client, circle, shared.id)).json()
    kept_body = (await _read(client, circle, kept.id)).json()

    assert shared_body["readAs"] == kept_body["readAs"] == "trusted"
    assert shared_body["prayerRequests"] == REQUEST
    assert kept_body["prayerRequests"] == ""


async def test_the_obt_lab_reads_a_cleared_projects_prayer_request_whole(
    client, db_session, shema_app, cleared
) -> None:
    """The reduction is the withheld record's: on a cleared one the OBT Lab is the audience a
    request nobody authorized reaches, as before."""
    body = (await _read(client, await _headers(db_session, shema_app, "obtLab"), CLEARED_ID)).json()

    assert (body["prayerRequests"], body["prayerRequestsAudio"]) == (REQUEST, RECORDING)


# --- the write -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("field", "value"),
    [("prayerRequests", "orem por outra coisa"), ("prayerRequestsAudio", "outra/gravacao.webm")],
)
async def test_the_obt_lab_may_not_write_a_sensitive_projects_prayer_request_it_reads_blank(
    client, db_session, shema_app, withheld, field, value
) -> None:
    """**The DoD's third test.** Handed ``""``, a request typed there would overwrite one the writer
    cannot see. A 403 naming the field and nothing about the record; the row and its version
    stay."""
    res = await client.patch(
        f"{PROJECTS}/{WITHHELD_ID}",
        json={field: value},
        headers={**(await _headers(db_session, shema_app, "obtLab")), "If-Match": '"1"'},
    )

    assert res.status_code == 403
    assert field in res.json()["detail"]
    assert REQUEST not in res.text
    stored = await _stored(db_session)
    assert (stored.prayer_requests, stored.prayer_requests_audio) == (REQUEST, RECORDING)
    assert stored.version == 1


async def test_the_obt_lab_still_writes_a_cleared_projects_prayer_request(
    client, db_session, shema_app, cleared
) -> None:
    """The refusal is the withheld record's: on a cleared one the mentor writes the request."""
    res = await client.patch(
        f"{PROJECTS}/{CLEARED_ID}",
        json={"prayerRequests": "orem pela colheita"},
        headers={**(await _headers(db_session, shema_app, "obtLab")), "If-Match": '"1"'},
    )

    assert res.status_code == 200, res.text
    assert res.json()["prayerRequests"] == "orem pela colheita"


async def test_a_conflict_does_not_tell_the_obt_lab_that_a_sensitive_projects_request_moved(
    client, db_session, shema_app, withheld
) -> None:
    """The coordination rewrites the request and the translators; the OBT Lab, saving from the
    version before, is told the translators moved and not the request — it reads that blank."""
    coordinator = await _headers(db_session, shema_app, "coordinator")
    saved = await client.patch(
        f"{PROJECTS}/{WITHHELD_ID}",
        json={"prayerRequests": "orem pela nova casa", "translators": "Equipe A"},
        headers={**coordinator, "If-Match": '"1"'},
    )
    assert saved.status_code == 200, saved.text

    res = await client.patch(
        f"{PROJECTS}/{WITHHELD_ID}",
        json={"technicalReviewers": "Revisao"},
        headers={**(await _headers(db_session, shema_app, "obtLab")), "If-Match": '"1"'},
    )

    assert res.status_code == 409
    assert res.json()["changedFields"] == ["translators"]


#: A reading the wizard files — one rating is enough for an assessment to rate something.
READING = {"date": "2026-10-20", "emotional": "boa", "questionSetVersion": 1}


async def _history(db_session, project_id: str = WITHHELD_ID) -> int:
    stmt = select(ShemaHealthAssessment).where(ShemaHealthAssessment.project_id == project_id)
    return len((await db_session.execute(stmt)).scalars().all())


async def test_a_health_reading_from_the_obt_lab_may_not_carry_a_request_over_one_it_reads_blank(
    client, db_session, shema_app, withheld
) -> None:
    """The wizard's door to the same column (review of shema-api#965): the request keeps no
    history, unlike the reading's own notes, so a request filed here would replace one the mentor
    cannot see. Refused with the save's sentence before anything is written — no reading, no
    version, the request where it was."""
    filed = await client.post(
        f"{PROJECTS}/{WITHHELD_ID}/health-assessments",
        json={**READING, "prayerRequests": "orem pela viagem do mentor"},
        headers=await _headers(db_session, shema_app, "obtLab"),
    )

    assert filed.status_code == 403
    assert "prayerRequests" in filed.json()["detail"]
    assert REQUEST not in filed.text
    stored = await _stored(db_session)
    assert (stored.prayer_requests, stored.version) == (REQUEST, 1)
    assert await _history(db_session) == 0


async def test_a_blank_request_from_the_obt_lab_is_no_request_and_the_reading_is_filed(
    client, db_session, shema_app, withheld
) -> None:
    """OBT-658: a request sent with nothing written in it is not sent, so the refusal above has no
    request to refuse — the reading is filed and the request the OBT Lab reads blank stays as the
    coordination wrote it."""
    filed = await client.post(
        f"{PROJECTS}/{WITHHELD_ID}/health-assessments",
        json={**READING, "prayerRequests": ""},
        headers=await _headers(db_session, shema_app, "obtLab"),
    )

    assert filed.status_code == 201, filed.text
    assert (await _stored(db_session)).prayer_requests == REQUEST
    assert await _history(db_session) == 1


async def test_the_obt_labs_reading_without_a_request_is_filed_and_the_coordination_files_one(
    client, db_session, shema_app, withheld
) -> None:
    """The refusal is the request's, not the reading's: the same reading without it is filed — the
    console's wizard does not offer the request to this reader — and the coordination, who reads
    the request, still raises one through the wizard."""
    lab = await client.post(
        f"{PROJECTS}/{WITHHELD_ID}/health-assessments",
        json=READING,
        headers=await _headers(db_session, shema_app, "obtLab"),
    )
    coordination = await client.post(
        f"{PROJECTS}/{WITHHELD_ID}/health-assessments",
        json={**READING, "prayerRequests": "orem pela nova casa"},
        headers=await _headers(db_session, shema_app, "coordinator"),
    )

    assert lab.status_code == coordination.status_code == 201, (lab.text, coordination.text)
    assert coordination.json()["prayerRequests"] == "orem pela nova casa"
    assert await _history(db_session) == 2
