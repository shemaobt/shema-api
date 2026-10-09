"""A sensitive project's prayer request passes the coordination first — OBT-575's DoD, over HTTP.

Karina, via Daniel, 6/oct/2026: *"A coordenação revisa o texto antes de ele ir ao mural e ao
Pulso."* The bold line of the DoD is three tests that try to get a waiting request out — onto the
wall, into the Pulse, into the export — and fail, each beside the released case that succeeds, so
the absence is the review and not an empty path. Then who releases and edits (the coordination,
and every other role refused), and the four answers the pull request proposes: the coordination
is told, a request taken back leaves the queue, a new text waits again, and a project flagged
sensitive takes its requests off the wall until they are read.

**Nothing here is real.** Every place, language and request is invented. The accounts that write
through the API are scoped to ``other`` (``HOME``), where an invented place derives to.

**No test uses a platform admin to prove a refusal**, for ``conftest.py``'s reason.
"""

from __future__ import annotations

import pytest

from app.db.models.shema import ShemaProject
from app.db.models.shema_enums import ShemaPrayerVisibility, ShemaRegionKey
from tests.shema_harness import HOME, need, person
from tests.test_shema.conftest import PREFIX, make_shema_project

WALL = f"{PREFIX}/prayer/requests"
PULSE = f"{PREFIX}/prayer/pulse"
EXPORT = f"{PREFIX}/export/projects"
QUEUE = f"{PREFIX}/prayer/review"
PANEL = f"{PREFIX}/notifications"
PROJECTS = f"{PREFIX}/projects"

AWAY = ShemaRegionKey.AFRICA

#: The team's words, the coordination's edit of them, and a need — long enough not to appear by
#: accident, and the edit shares no phrase with the original.
TEAM_TEXT = "Orem pelo líder preso na cidade de Pedra Funda desde agosto"
EDITED = "Orem pela proteção e pela liberdade de um irmão da equipe"
NEED_TEXT = "Orem pelo dinheiro do barco que leva a equipe até a aldeia escondida"
OPEN_TEXT = "Orem pela colheita do vale aberto e pela saúde dos tradutores"


def release_route(project_id: str) -> str:
    return f"{PROJECTS}/{project_id}/prayer/release"


async def seed(
    db_session,
    project_id: str,
    *,
    text: str = TEAM_TEXT,
    sensitive: bool = True,
    region: ShemaRegionKey = HOME,
    language: str = "Língua Garoa",
) -> ShemaProject:
    """A project whose team authorized its request for the network — ``rede`` with ``text``."""
    project = await make_shema_project(
        db_session, project_id=project_id, region_key=region, language_name=language
    )
    project.location = "Vale Fechado"
    project.sensitive_country = sensitive
    project.prayer_requests = text
    project.prayer_visibility = ShemaPrayerVisibility.REDE
    await db_session.commit()
    return project


@pytest.fixture()
async def coordinator(db_session, shema_app):
    return await person(db_session, shema_app, "coordinator")


@pytest.fixture()
async def circle(db_session, shema_app):
    return await person(db_session, shema_app, "resourceCircle")


@pytest.fixture()
async def strategist(db_session, shema_app):
    """A coordinator holding every region — who exports in ``test_transfer.py``."""
    return await person(db_session, shema_app, "coordinator", regions=tuple(ShemaRegionKey))


@pytest.fixture()
async def waiting(db_session):
    """A sensitive project whose own request and one need the team shared, neither released."""
    project = await seed(db_session, "garoa-vale-fechado")
    row = await need(db_session, project, NEED_TEXT, shared=True)
    return project, row


async def wall_texts(client, headers) -> set[str]:
    response = await client.get(WALL, headers=headers)
    assert response.status_code == 200, response.text
    return {entry["text"] for entry in response.json()}


async def pulse(client, headers) -> str:
    response = await client.get(PULSE, headers=headers)
    assert response.status_code == 200, response.text
    return response.text


async def exported(client, headers) -> list[str]:
    response = await client.get(EXPORT, params={"format": "json"}, headers=headers)
    assert response.status_code == 200, response.text
    return [text for row in response.json()["projects"] for text in row["sharedPrayerRequests"]]


async def queue(client, headers) -> list[dict]:
    response = await client.get(QUEUE, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


async def release(client, headers, project_id: str, body: dict):
    return await client.post(release_route(project_id), json=body, headers=headers)


async def panel_kinds(client, headers) -> list[str]:
    response = await client.get(PANEL, headers=headers)
    assert response.status_code == 200, response.text
    return [entry["kind"] for entry in response.json()]


# --- the three outputs ---------------------------------------------------------------------


async def test_a_waiting_request_is_not_on_the_wall_and_a_released_one_is_as_released(
    client, circle, coordinator, waiting
) -> None:
    project, row = waiting
    assert await wall_texts(client, circle) == set()

    ok = await release(client, coordinator, project.id, {"reviewed": TEAM_TEXT, "text": EDITED})
    assert ok.status_code == 204, ok.text
    ok = await release(client, coordinator, project.id, {"needId": row.id, "reviewed": NEED_TEXT})
    assert ok.status_code == 204, ok.text

    assert await wall_texts(client, circle) == {EDITED, NEED_TEXT}


async def test_a_waiting_request_is_not_in_the_pulse_and_a_released_one_is_as_released(
    client, circle, coordinator, waiting
) -> None:
    project, _ = waiting
    before = await pulse(client, circle)
    assert TEAM_TEXT not in before and NEED_TEXT not in before and EDITED not in before

    await release(client, coordinator, project.id, {"reviewed": TEAM_TEXT, "text": EDITED})

    after = await pulse(client, circle)
    assert EDITED in after
    assert TEAM_TEXT not in after and NEED_TEXT not in after


async def test_a_waiting_request_is_not_in_the_export_and_a_released_one_is_as_released(
    client, strategist, waiting
) -> None:
    project, row = waiting
    assert await exported(client, strategist) == []

    await release(client, strategist, project.id, {"reviewed": TEAM_TEXT, "text": EDITED})
    await release(client, strategist, project.id, {"needId": row.id, "reviewed": NEED_TEXT})

    assert sorted(await exported(client, strategist)) == sorted([EDITED, NEED_TEXT])


async def test_a_project_nothing_withholds_reaches_the_wall_without_review(
    client, db_session, circle, coordinator
) -> None:
    """*Em projeto não sensível, nada muda* — no queue, and nothing to release."""
    project = await seed(db_session, "vale-aberto", text=OPEN_TEXT, sensitive=False)

    assert await wall_texts(client, circle) == {OPEN_TEXT}
    assert await queue(client, coordinator) == []
    refused = await release(client, coordinator, project.id, {"reviewed": OPEN_TEXT})
    assert refused.status_code == 409, refused.text


# --- the queue -----------------------------------------------------------------------------


async def test_the_queue_holds_the_team_s_text_and_empties_as_it_is_released(
    client, coordinator, waiting
) -> None:
    project, row = waiting

    entries = await queue(client, coordinator)
    assert [(entry["needId"], entry["text"]) for entry in entries] == [
        (None, TEAM_TEXT),
        (row.id, NEED_TEXT),
    ]
    assert {entry["projectId"] for entry in entries} == {project.id}
    assert {entry["language"] for entry in entries} == {"Língua Garoa"}

    await release(client, coordinator, project.id, {"reviewed": TEAM_TEXT})
    assert [entry["needId"] for entry in await queue(client, coordinator)] == [row.id]


async def test_a_release_of_a_text_the_team_has_since_changed_is_a_conflict(
    client, circle, coordinator, waiting
) -> None:
    """The release is bound to what the coordination read: a newer text is not released unread."""
    project, _ = waiting

    stale = await release(client, coordinator, project.id, {"reviewed": "um texto mais antigo"})

    assert stale.status_code == 409, stale.text
    assert await wall_texts(client, circle) == set()


async def test_a_request_longer_than_any_cap_is_still_released(
    client, db_session, circle, coordinator
) -> None:
    """The team's text has no cap, so the release that must quote it cannot carry one."""
    long_text = "Orem pela equipe. " * 2_000
    project = await seed(db_session, "garoa-longa", text=long_text)

    ok = await release(client, coordinator, project.id, {"reviewed": long_text.strip()})

    assert ok.status_code == 204, ok.text
    assert await wall_texts(client, circle) == {long_text.strip()}


# --- who releases and edits ----------------------------------------------------------------


@pytest.mark.parametrize("role", ["resourceCircle", "obtLab"])
async def test_only_the_coordination_reads_the_queue_and_releases(
    client, db_session, shema_app, waiting, role
) -> None:
    """The Resource Circle reads the truth and edits nothing (OBT-571); the OBT Lab coordinates
    no region. Both are refused the queue, the release and the edit, and nothing moves."""
    project, _ = waiting
    headers = await person(db_session, shema_app, role)
    circle = await person(db_session, shema_app, "resourceCircle", regions=(HOME, AWAY))

    assert (await client.get(QUEUE, headers=headers)).status_code == 403
    plain = await release(client, headers, project.id, {"reviewed": TEAM_TEXT})
    edited = await release(client, headers, project.id, {"reviewed": TEAM_TEXT, "text": EDITED})

    assert plain.status_code == 403, plain.text
    assert edited.status_code == 403, edited.text
    assert await wall_texts(client, circle) == set()


async def test_a_coordinator_of_another_region_neither_sees_nor_releases(
    client, db_session, shema_app, circle, waiting
) -> None:
    project, _ = waiting
    elsewhere = await person(db_session, shema_app, "coordinator", regions=(AWAY,))

    assert await queue(client, elsewhere) == []
    refused = await release(client, elsewhere, project.id, {"reviewed": TEAM_TEXT})

    assert refused.status_code == 404, refused.text
    assert await wall_texts(client, circle) == set()


async def test_the_admin_coordinates_every_region_and_releases(
    client, db_session, shema_app, circle, waiting
) -> None:
    """``admin`` holds no region rows and coordinates them all (``_scope.readership``)."""
    project, _ = waiting
    admin = await person(db_session, shema_app, "admin", regions=())

    assert [entry["text"] for entry in await queue(client, admin)] == [TEAM_TEXT, NEED_TEXT]
    ok = await release(client, admin, project.id, {"reviewed": TEAM_TEXT})

    assert ok.status_code == 204, ok.text
    assert await wall_texts(client, circle) == {TEAM_TEXT}


# --- the four answers ----------------------------------------------------------------------


async def test_a_request_the_team_takes_back_leaves_the_queue(
    client, db_session, coordinator, waiting
) -> None:
    """Question 2: the withdrawal wins — nothing left to release."""
    project, row = waiting
    project.prayer_visibility = ShemaPrayerVisibility.COORDENACAO
    row.prayer_shared = False
    await db_session.commit()

    assert await queue(client, coordinator) == []
    refused = await release(client, coordinator, project.id, {"reviewed": TEAM_TEXT})
    assert refused.status_code == 409, refused.text


async def test_a_new_text_after_the_release_leaves_the_wall_and_waits_again(
    client, db_session, circle, coordinator, waiting
) -> None:
    """Question 3: a release belongs to the text it was given for; the same text sent again
    stays released."""
    project, _ = waiting
    await release(client, coordinator, project.id, {"reviewed": TEAM_TEXT, "text": EDITED})

    project.prayer_requests = f"  {TEAM_TEXT}  "
    await db_session.commit()
    assert await wall_texts(client, circle) == {EDITED}

    project.prayer_requests = OPEN_TEXT
    await db_session.commit()
    assert await wall_texts(client, circle) == set()
    assert [entry["text"] for entry in await queue(client, coordinator)] == [OPEN_TEXT, NEED_TEXT]


async def test_a_project_flagged_sensitive_takes_its_requests_off_the_wall_until_read(
    client, db_session, circle, coordinator
) -> None:
    """Question 4: they leave the wall and the next Pulse, and wait in the queue."""
    project = await seed(db_session, "vale-que-fecha", text=OPEN_TEXT, sensitive=False)
    assert await wall_texts(client, circle) == {OPEN_TEXT}

    project.sensitive_country = True
    await db_session.commit()

    assert await wall_texts(client, circle) == set()
    assert OPEN_TEXT not in await pulse(client, circle)
    assert [entry["text"] for entry in await queue(client, coordinator)] == [OPEN_TEXT]


# --- who is told ---------------------------------------------------------------------------


async def test_the_coordination_is_told_when_a_request_starts_waiting(
    client, db_session, shema_app, circle, coordinator
) -> None:
    """Question 1. The OBT Lab authorizes the request on the record; the region's coordination
    hears that it waits, and the writer does not. Question 5: a request typed into the ficha came
    with no Pulse, so its release announces nothing to the Resource Circle — as on a project
    nothing withholds. The Pulse's own case is ``test_forms.py``'s."""
    project = await seed(db_session, "garoa-aviso", text=TEAM_TEXT)
    project.prayer_visibility = None
    await db_session.commit()
    lab = await person(db_session, shema_app, "obtLab")

    written = await client.patch(
        f"{PROJECTS}/{project.id}",
        json={"prayerVisibility": "rede"},
        headers={**lab, "If-Match": '"1"'},
    )
    assert written.status_code == 200, written.text

    assert await panel_kinds(client, coordinator) == ["prayerReview"]
    assert "prayerReview" not in await panel_kinds(client, lab)
    assert await panel_kinds(client, circle) == []

    released = await release(client, coordinator, project.id, {"reviewed": TEAM_TEXT})
    assert released.status_code == 204, released.text
    assert await panel_kinds(client, circle) == []
