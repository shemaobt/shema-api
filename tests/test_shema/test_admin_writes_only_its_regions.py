"""OBT-593, found in review: the Admin's every-region reading must not widen a single write.

The record was covered (``refuse_admin_writes``); the review bot found that every **other** write
that lands in a region took that region off the session ``Scope`` — the reading reach, global for
an account holding ``admin`` — so a coordinator of Asia who also holds ``admin`` could file a
health reading, log a Ritmo meeting, mint a leader's link, file or import a Pulse, withdraw an
authorization, import a file, save a region's team or record an ETEN credit on an **Africa**
project, all of which the regional scope refused before. The sweep (``grep`` over every
``POST``/``PUT``/``PATCH``/``DELETE`` under ``app/api/shema`` taking ``Scope``, and every writing
service calling ``visible_projects(scope)``, ``require_writes_region(scope, …)``,
``reaches(scope, …)`` or ``get_project(db, scope, …)``) found nine such routes; they declare
``WriteScope`` now — the regional half — and this file holds each one twice: refused in Africa,
as before OBT-593, and allowed in Asia, as before OBT-593.

The account is the one ``test_scope.py`` says *reads everywhere and writes its own regions*.
No installation admin here: it passes every guard and would prove nothing.
"""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import select

from app.db.models.shema import ShemaProject
from app.db.models.shema_enums import ShemaMediaKind, ShemaRegionKey
from app.db.models.shema_media import ShemaMediaItem
from app.services.shema._media_storage import MEDIA, storage_key
from tests.test_shema.conftest import PREFIX, auth_header, grant, make_scoped_user

PROJECTS = f"{PREFIX}/projects"
LINKS = f"{PREFIX}/intake-links"
SUBMISSIONS = f"{PREFIX}/forms/submissions"
IMPORT = f"{PREFIX}/import/projects"
LOG = f"{PREFIX}/meetings/log"
REGIONS = f"{PREFIX}/regions"
CREDITS = f"{PREFIX}/eten/credits"
ASIA = ShemaRegionKey.ASIA
AFRICA = ShemaRegionKey.AFRICA
#: Minted ids, because the file import takes an unreachable id for a new record and refuses a
#: slug before it refuses the reach; locations whose country derives the region, so a file that
#: re-states them keeps the row home.
NEAR = "e47d7b9f-1944-509c-a7be-f96419afcc1c"
FAR = "d23e9eca-0785-5afc-8d28-d4e99261de3d"
HOME = (NEAR, ASIA, "Nepal")
AWAY = (FAR, AFRICA, "Moçambique")

READING = {
    "date": "2026-09-10",
    "assessor": "Marina Alves",
    "emotional": "boa",
    "relational": "atencao",
    "spiritual": "boa",
    "physical": "boa",
    "dimensionNotes": {"emotional": "Eles estão firmes."},
    "questionSetVersion": 1,
}
MEETING = "bimestral_pi_campo"


async def _seed(db_session) -> None:
    for project_id, region, location in (HOME, AWAY):
        db_session.add(
            ShemaProject(
                id=project_id,
                language_name=f"Lingua {project_id[:8]}",
                bridge_language="Portugues",
                location=location,
                team="JOCUM",
                sensitive_country=False,
                region_key=region,
            )
        )
    await db_session.commit()


@pytest.fixture()
async def beside(db_session, shema_app):
    """``coordinator`` in Asia **and** ``admin``: reads everywhere, writes Asia."""
    await _seed(db_session)
    user = await make_scoped_user(
        db_session,
        shema_app,
        email="asia-admin@writes.test",
        role_key="coordinator",
        regions=[ASIA],
    )
    await grant(db_session, user, shema_app, "admin")
    return await auth_header(db_session, user)


@pytest.fixture()
async def africa(db_session, shema_app):
    """The coordination of Africa, who makes what the Asia account may not touch."""
    user = await make_scoped_user(
        db_session, shema_app, email="africa@writes.test", role_key="coordinator", regions=[AFRICA]
    )
    return await auth_header(db_session, user)


async def test_the_health_reading(client, beside) -> None:
    away = await client.post(f"{PROJECTS}/{FAR}/health-assessments", json=READING, headers=beside)
    home = await client.post(f"{PROJECTS}/{NEAR}/health-assessments", json=READING, headers=beside)

    assert away.status_code == 404, away.text
    assert home.status_code == 201, home.text


async def test_the_ritmo_log_and_its_undo(client, beside) -> None:
    body = {"meetingId": MEETING, "date": "2026-03-10", "notes": ""}

    away = await client.post(LOG, json={**body, "scopeKey": "africa"}, headers=beside)
    home = await client.post(LOG, json={**body, "scopeKey": "asia"}, headers=beside)
    undo_away = await client.delete(f"{LOG}/{MEETING}/africa/2026-B2", headers=beside)
    undo_home = await client.delete(f"{LOG}/{MEETING}/asia/2026-B2", headers=beside)

    assert away.status_code == 403 and "region scope" in away.json()["detail"]
    assert home.status_code == 201, home.text
    assert undo_away.status_code == 403
    assert undo_home.status_code == 204, undo_home.text


async def test_the_leaders_link_and_its_revocation(client, beside, africa) -> None:
    theirs = await client.post(LINKS, json={"projectId": FAR}, headers=africa)
    assert theirs.status_code == 201, theirs.text

    away = await client.post(LINKS, json={"projectId": FAR}, headers=beside)
    home = await client.post(LINKS, json={"projectId": NEAR}, headers=beside)
    revoke_away = await client.post(f"{LINKS}/{theirs.json()['id']}/revoke", headers=beside)
    revoke_home = await client.post(f"{LINKS}/{home.json()['id']}/revoke", headers=beside)

    assert away.status_code == 404, away.text
    assert home.status_code == 201, home.text
    assert revoke_away.status_code == 404, revoke_away.text
    assert revoke_home.status_code == 200, revoke_home.text


async def test_a_pulse_filed_directly_and_one_imported(client, db_session, beside, africa) -> None:
    link = (await client.post(LINKS, json={"projectId": FAR}, headers=africa)).json()
    answered = await client.post(
        f"{PREFIX}/intake/{link['token']}",
        json={"definitionVersion": 1, "answers": {"submittedBy": "Kuaray", "period": "2026-09"}},
    )
    assert answered.status_code == 202, answered.text
    [pending] = (await client.get(SUBMISSIONS, headers=africa)).json()
    filing = {"answers": {"submittedBy": "Kuaray", "period": "2026-08"}}

    away = await client.post(
        SUBMISSIONS, json={**filing, "projectId": FAR}, headers={**beside, "If-Match": '"1"'}
    )
    home = await client.post(
        SUBMISSIONS, json={**filing, "projectId": NEAR}, headers={**beside, "If-Match": '"1"'}
    )
    imported = await client.post(
        f"{SUBMISSIONS}/{pending['id']}/import", headers={**beside, "If-Match": '"1"'}
    )

    assert away.status_code == 404, away.text
    assert home.status_code == 201, home.text
    assert imported.status_code == 404, imported.text


async def test_the_withdrawal_of_an_authorization(client, db_session, beside) -> None:
    items = {}
    for project_id in (FAR, NEAR):
        item = ShemaMediaItem(
            project_id=project_id,
            kind=ShemaMediaKind.PHOTO,
            storage_key=storage_key(MEDIA, f"row-{project_id}", "a" * 64, ".jpg"),
            authorization_granted=True,
        )
        db_session.add(item)
        items[project_id] = item
    await db_session.commit()

    away = await client.post(
        f"{PROJECTS}/{FAR}/media/{items[FAR].id}/authorization/withdraw", headers=beside
    )
    home = await client.post(
        f"{PROJECTS}/{NEAR}/media/{items[NEAR].id}/authorization/withdraw", headers=beside
    )

    assert away.status_code == 404, away.text
    assert home.status_code == 200 and home.json()["granted"] is False


def _record(project_id: str, location: str) -> dict:
    return {
        "id": project_id,
        "languageName": f"Lingua {project_id[:8]}",
        "bridgeLanguage": "Portugues",
        "team": "JOCUM",
        "objective": ["NT"],
        "location": location,
        "statusComments": "pelo arquivo",
    }


async def _upload(client, headers, records: list[dict]):
    return await client.post(
        IMPORT,
        content=json.dumps(records).encode(),
        headers={**headers, "Content-Type": "application/json"},
    )


async def _comments(db_session) -> dict[str, str]:
    rows = await db_session.execute(select(ShemaProject).execution_options(populate_existing=True))
    return {row.id: row.status_comments for row in rows.scalars()}


async def test_the_file_import_refuses_a_file_naming_the_far_project(
    client, db_session, beside
) -> None:
    """An id that exists out of reach reads as a new record, as it did before OBT-593 for every
    regional caller, and the create refuses it — here with the Admin's own sentence, which
    comes before the 409 a plain coordinator meets — and nothing of the file is applied."""
    away = await _upload(client, beside, [_record(FAR, "Moçambique")])

    assert away.status_code == 403, away.text
    assert "writes only access" in away.json()["detail"]
    assert (await _comments(db_session))[FAR] == ""


async def test_the_file_import_applies_a_file_over_the_home_project(
    client, db_session, beside
) -> None:
    home = await _upload(client, beside, [_record(NEAR, "Nepal")])

    assert home.status_code == 200, home.text
    assert (await _comments(db_session))[NEAR] == "pelo arquivo"


async def test_the_regions_team(client, beside) -> None:
    team = {"team": {"coordinator": "Alguém", "obtLab": "", "resourceCircle": ""}}

    away = await client.put(f"{REGIONS}/africa/team", json=team, headers=beside)
    home = await client.put(f"{REGIONS}/asia/team", json=team, headers=beside)

    assert away.status_code == 403, away.text
    assert home.status_code == 200, home.text


async def test_the_eten_credit(client, beside) -> None:
    away = await client.put(f"{CREDITS}/{FAR}/2026", json={"credits": 1}, headers=beside)
    home = await client.put(f"{CREDITS}/{NEAR}/2026", json={"credits": 1}, headers=beside)

    assert away.status_code == 404, away.text
    assert home.status_code == 200, home.text


async def test_the_record_itself_keeps_its_own_sentence(client, beside) -> None:
    """The record is the one write that keeps the reading scope: the row is one the Admin may
    read, so the refusal is a 403 of the Admin's own and not the existence-hiding 404."""
    away = await client.get(f"{PROJECTS}/{FAR}", headers=beside)

    patched = await client.patch(
        f"{PROJECTS}/{FAR}",
        json={"notes": "fora"},
        headers={**beside, "If-Match": away.headers["ETag"]},
    )
    created = await client.post(
        PROJECTS,
        json={
            "id": str(uuid.uuid4()),
            "languageName": "Nova",
            "bridgeLanguage": "Portugues",
            "team": "JOCUM",
            "objective": ["NT"],
            "location": "Moçambique",
        },
        headers=beside,
    )

    assert away.status_code == 200
    assert patched.status_code == 403 and "writes only access" in patched.json()["detail"]
    assert created.status_code == 403 and "writes only access" in created.json()["detail"]
