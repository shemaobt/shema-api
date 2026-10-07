"""The prayer wall, the Prayer Pulse and the authorization of a request — BE-09's DoD, over HTTP.

The line the issue puts in bold is here as three tests that **try** to get an unauthorized
request out and fail: onto the wall, into the Pulse, and into the export. The export is BE-14's
(OBT-403, stacked on this branch), so its route test is written here as ``xfail(strict=True)`` —
it turns red the day the route exists and BE-14 removes the mark — and the filter the export will
call is proved directly in the meantime.

**Nothing here is real.** Every place, language, base and request is invented, because the region
a fictional place derives to is ``other`` (``FALLBACK_REGION``) and a record written through the
API is re-derived on every save: the accounts that write are scoped to ``other`` for that reason,
and the one project in another region is only ever read.

**No test uses a platform admin to prove a refusal.** An installation admin passes every guard,
so a negative test written with one passes for the wrong reason (``conftest.py``).
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.db.models.shema import ShemaProject
from app.db.models.shema_enums import ShemaPrayerVisibility, ShemaRegionKey
from app.db.models.shema_need import ShemaNeed
from app.services.shema import authorized_requests_by_project
from tests.shema_harness import HOME, need, person
from tests.test_shema.conftest import PREFIX, auth_header, make_shema_project

WALL = f"{PREFIX}/prayer/requests"
PULSE = f"{PREFIX}/prayer/pulse"
PROJECTS = f"{PREFIX}/projects"
SUBMISSIONS = f"{PREFIX}/forms/submissions"
EXPORT = f"{PREFIX}/export/projects"

AWAY = ShemaRegionKey.AFRICA

#: What a team said nobody else may read. Every assertion that something is withheld looks for
#: these strings, so they are long enough not to appear by accident.
KEPT = "Orem pela consulta médica que ninguém fora da coordenação deve saber"
KEPT_NEED = "Orem pela dívida do gerador que a equipe não quer que se espalhe"
SHARED = "Orem pela colheita do vale e pela saúde dos tradutores"
SHARED_NEED = "Orem pela viagem de barco até a aldeia de Pedra Clara"

#: A create the console would send: the four required fields and a place that derives to ``HOME``.
CREATE = {
    "id": "8d67234d-5f89-50b1-b7fe-7db602f743ba",
    "languageName": "Língua Junco",
    "bridgeLanguage": "Português",
    "team": "Base Junco",
    "objective": ["NT"],
    "location": "Vale Novo",
    "prayerRequests": "",
}


async def seed(
    db_session,
    project_id: str,
    *,
    text: str = "",
    visibility: ShemaPrayerVisibility | None = None,
    sensitive: bool = False,
    region: ShemaRegionKey = HOME,
    location: str = "Vale Novo, Serra Clara",
    team: str = "Base Serra Clara",
    language: str = "Língua Aurora",
) -> ShemaProject:
    project = await make_shema_project(
        db_session, project_id=project_id, region_key=region, language_name=language
    )
    project.location = location
    project.team = team
    project.sensitive_country = sensitive
    project.prayer_requests = text
    project.prayer_visibility = visibility
    await db_session.commit()
    return project


@pytest.fixture()
async def circle(db_session, shema_app):
    return await person(db_session, shema_app, "resourceCircle")


@pytest.fixture()
async def coordinator(db_session, shema_app):
    return await person(db_session, shema_app, "coordinator")


@pytest.fixture()
async def strategist(db_session, shema_app):
    """A coordinator holding every region — where the Global Strategist's reach went (OBT-572)."""
    return await person(db_session, shema_app, "coordinator", regions=tuple(ShemaRegionKey))


@pytest.fixture()
async def mixed(db_session):
    """One project whose own request is kept and one whose own request is shared, each with a
    shared need and a kept one — every combination the gate has to tell apart."""
    kept = await seed(
        db_session, "aurora-vale", text=KEPT, visibility=ShemaPrayerVisibility.COORDENACAO
    )
    shared = await seed(
        db_session,
        "brisa-serra",
        text=SHARED,
        visibility=ShemaPrayerVisibility.REDE,
        language="Língua Brisa",
    )
    await need(db_session, kept, KEPT_NEED, shared=False)
    await need(db_session, shared, SHARED_NEED, shared=True)
    return kept, shared


def texts(entries: list[dict]) -> set[str]:
    return {entry["text"] for entry in entries}


async def wall(client, headers) -> list[dict]:
    response = await client.get(WALL, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


async def pulse(client, headers, lang: str = "pt-BR") -> str:
    response = await client.get(PULSE, params={"lang": lang}, headers=headers)
    assert response.status_code == 200, response.text
    return response.text


async def patch(client, headers, project_id: str, body: dict, version: int = 1):
    return await client.patch(
        f"{PROJECTS}/{project_id}", json=body, headers={**headers, "If-Match": f'"{version}"'}
    )


async def test_an_unauthorized_request_cannot_be_placed_on_the_wall(client, circle, mixed) -> None:
    """The project's request kept in coordination and a need nobody shared are both on the rows
    the wall is built from, and neither reaches it — while the two authorized ones beside them
    do, which is what makes the absence a refusal and not an empty path."""
    body = await wall(client, circle)

    assert texts(body) == {SHARED, SHARED_NEED}
    assert KEPT not in str(body) and KEPT_NEED not in str(body)


async def test_an_unauthorized_request_cannot_be_placed_in_the_pulse(client, circle, mixed) -> None:
    file = await pulse(client, circle)

    assert SHARED in file and SHARED_NEED in file
    assert KEPT not in file and KEPT_NEED not in file


async def test_the_filter_the_export_reuses_yields_no_unauthorized_request(
    db_session, mixed
) -> None:
    """``authorized_requests_by_project`` is what BE-14's ``sharedPrayerRequests`` reads, and
    here it is handed the rows directly, every need of each project included."""
    kept, shared = mixed

    authorized = await authorized_requests_by_project(db_session, [kept, shared])

    assert authorized[kept.id] == []
    assert {request.text for request in authorized[shared.id]} == {SHARED, SHARED_NEED}


async def test_an_unauthorized_request_is_absent_from_the_export(client, strategist, mixed) -> None:
    for fmt in ("json", "csv"):
        response = await client.get(EXPORT, params={"format": fmt}, headers=strategist)
        assert response.status_code == 200
        assert SHARED in response.text
        assert KEPT not in response.text and KEPT_NEED not in response.text


async def test_the_other_outputs_of_today_carry_no_unauthorized_request(
    client, db_session, shema_app, strategist, coordinator, circle, mixed
) -> None:
    """The cards, the notification panel and the ETEN report are the paths that leave or list
    today; the submission notice has its own tests in ``test_forms.py``."""
    kept, _ = mixed
    kept.in_eten = True
    await db_session.commit()

    for headers in (strategist, coordinator, circle):
        cards = await client.get(PROJECTS, headers=headers)
        panel = await client.get(f"{PREFIX}/notifications", headers=headers)
        assert cards.status_code == panel.status_code == 200
        for body in (cards.text, panel.text):
            assert KEPT not in body and KEPT_NEED not in body

    report = await client.get(f"{PREFIX}/eten/report", params={"year": 2027}, headers=strategist)
    assert report.status_code == 200
    assert KEPT not in report.text and KEPT_NEED not in report.text


async def test_a_request_nobody_authorized_reaches_neither_the_wall_nor_the_pulse(
    client, db_session, circle
) -> None:
    """NULL is ``coordenacao``, and a need is born unshared: nothing written, nothing leaves."""
    silent = await seed(db_session, "cedro-vale", text=KEPT)
    await need(db_session, silent, KEPT_NEED, shared=False)
    assert silent.prayer_visibility is None

    assert await wall(client, circle) == []
    file = await pulse(client, circle)
    assert KEPT not in file and KEPT_NEED not in file
    assert "Nenhum pedido autorizado" in file


async def test_authorization_is_per_request_not_per_project(client, db_session, circle) -> None:
    """Three shared needs and a fourth that was not: the fourth is absent whatever the project
    says. And a project that kept its own request still shares the need it did share."""
    open_project = await seed(
        db_session, "duna-vale", text=SHARED, visibility=ShemaPrayerVisibility.REDE
    )
    for index in range(3):
        await need(db_session, open_project, f"{SHARED_NEED} {index}", shared=True)
    await need(db_session, open_project, KEPT_NEED, shared=False)
    closed = await seed(
        db_session, "eira-vale", text=KEPT, visibility=ShemaPrayerVisibility.COORDENACAO
    )
    await need(db_session, closed, "Orem pela escola da comunidade", shared=True)

    body = await wall(client, circle)

    assert texts(body) == {
        SHARED,
        f"{SHARED_NEED} 0",
        f"{SHARED_NEED} 1",
        f"{SHARED_NEED} 2",
        "Orem pela escola da comunidade",
    }
    assert {entry["source"] for entry in body if entry["projectId"] == "eira-vale"} == {
        "Necessidade"
    }


async def test_a_new_request_without_its_authorization_is_unauthorized(
    client, db_session, circle, coordinator
) -> None:
    """The fourth request lands where the third was, and does not inherit its ``rede``."""
    project = await seed(
        db_session, "fonte-vale", text=SHARED, visibility=ShemaPrayerVisibility.REDE
    )

    same = await patch(client, coordinator, project.id, {"prayerRequests": SHARED})
    assert same.json()["prayerVisibility"] == "rede"

    response = await patch(client, coordinator, project.id, {"prayerRequests": KEPT})

    assert response.status_code == 200, response.text
    assert response.json()["prayerVisibility"] is None
    assert await wall(client, circle) == []
    assert KEPT not in await pulse(client, circle)


async def test_restating_the_authorization_with_the_new_request_keeps_it(
    client, db_session, circle, coordinator
) -> None:
    project = await seed(db_session, "gruta-vale", text=KEPT, visibility=ShemaPrayerVisibility.REDE)

    response = await patch(
        client, coordinator, project.id, {"prayerRequests": SHARED, "prayerVisibility": "rede"}
    )

    assert response.status_code == 200, response.text
    assert texts(await wall(client, circle)) == {SHARED}


async def test_a_rewritten_need_leaves_the_wall_until_it_is_shared_again(
    client, db_session, circle, coordinator
) -> None:
    project = await seed(db_session, "horto-vale")
    row = await need(db_session, project, SHARED_NEED, shared=True)

    rewritten = await patch(
        client, coordinator, project.id, {"needsItems": [{"id": row.id, "description": KEPT_NEED}]}
    )
    assert rewritten.status_code == 200, rewritten.text
    assert await wall(client, circle) == []

    restated = await patch(
        client,
        coordinator,
        project.id,
        {"needsItems": [{"id": row.id, "description": KEPT_NEED, "prayerShared": True}]},
        version=2,
    )
    assert restated.status_code == 200, restated.text
    assert texts(await wall(client, circle)) == {KEPT_NEED}


async def test_the_health_wizard_carries_the_rule_too(
    client, db_session, shema_app, circle
) -> None:
    """The wizard sends the request and its visibility together, so it keeps what the mentor
    stated; a submission that sends the text alone is the fourth request again."""
    mentor = await person(db_session, shema_app, "obtLab")
    project = await seed(
        db_session, "ilha-vale", text=SHARED, visibility=ShemaPrayerVisibility.REDE
    )
    reading = {"date": "2026-09-10", "emotional": "boa", "questionSetVersion": 1}
    route = f"{PROJECTS}/{project.id}/health-assessments"

    stated = await client.post(
        route,
        json={**reading, "prayerRequests": SHARED_NEED, "prayerVisibility": "rede"},
        headers=mentor,
    )
    assert stated.status_code == 201, stated.text
    assert texts(await wall(client, circle)) == {SHARED_NEED}

    alone = await client.post(route, json={**reading, "prayerRequests": KEPT}, headers=mentor)
    assert alone.status_code == 201, alone.text
    assert alone.json()["prayerVisibility"] is None
    assert await wall(client, circle) == []


async def test_a_pulse_import_without_a_consent_answer_does_not_inherit_the_last_one(
    client, db_session, circle, coordinator
) -> None:
    """The Pulso Mensal writes the visibility only when the leader answers it — the path the
    rule exists for."""
    project = await seed(
        db_session, "jardim-vale", text=SHARED, visibility=ShemaPrayerVisibility.REDE
    )

    response = await client.post(
        SUBMISSIONS,
        json={
            "projectId": project.id,
            "answers": {"submittedBy": "Líder", "period": "2026-09", "prayerRequest": KEPT},
        },
        headers={**coordinator, "If-Match": '"1"'},
    )

    assert response.status_code == 201, response.text
    await db_session.refresh(project)
    assert project.prayer_visibility is None
    assert await wall(client, circle) == []


async def test_withdrawal_takes_the_request_out_of_the_next_wall_and_the_next_pulse(
    client, db_session, circle, coordinator
) -> None:
    """Derived, never stored: the next read has nothing to clean. The text stays on the record,
    because coordination is a destination and not a wastebasket."""
    project = await seed(
        db_session, "lago-vale", text=SHARED, visibility=ShemaPrayerVisibility.REDE
    )
    row = await need(db_session, project, SHARED_NEED, shared=True)
    assert texts(await wall(client, circle)) == {SHARED, SHARED_NEED}
    assert SHARED in await pulse(client, circle)

    response = await patch(
        client,
        coordinator,
        project.id,
        {
            "prayerVisibility": "coordenacao",
            "needsItems": [{"id": row.id, "prayerShared": False}],
        },
    )

    assert response.status_code == 200, response.text
    assert await wall(client, circle) == []
    file = await pulse(client, circle)
    assert SHARED not in file and SHARED_NEED not in file
    assert response.json()["prayerRequests"] == SHARED


async def test_the_pulse_carries_exactly_what_the_wall_carries(
    client, db_session, circle, mixed
) -> None:
    third = await seed(
        db_session,
        "mata-vale",
        text="Orem pelo casamento de dois tradutores",
        visibility=ShemaPrayerVisibility.REDE,
        language="Língua Mata",
    )
    await need(db_session, third, "Orem pelo conserto do telhado", shared=True, answered=True)

    body = await wall(client, circle)
    file = await pulse(client, circle)

    assert len(body) == 4
    assert "4 pedidos" in file
    for entry in body:
        assert entry["text"] in file
    assert file.count("• ") == 4
    assert [entry["text"] for entry in body if entry["answered"]] == [
        "Orem pelo conserto do telhado"
    ]
    assert "(respondido)" in file


async def test_a_sensitive_country_is_transformed_before_the_pulse_is_written(
    client, db_session, shema_app
) -> None:
    """An authorized request from a sensitive country still leaves without its place: the
    region where the country would be, no base, no slug. The project sits in a region that is
    not the fallback, so a Pulse that named ``other`` for every withheld entry would fail."""
    circle = await person(db_session, shema_app, "resourceCircle", regions=(HOME, AWAY))
    await seed(
        db_session,
        "nevoa-lugar-secreto",
        text=SHARED,
        visibility=ShemaPrayerVisibility.REDE,
        sensitive=True,
        region=AWAY,
        location="Lugar Secreto, Vila Escondida",
        team="Base Lugar Secreto",
        language="Língua Névoa",
    )
    await seed(
        db_session,
        "orvalho-vale",
        text=SHARED_NEED,
        visibility=ShemaPrayerVisibility.REDE,
        location="Terra Aberta",
        team="Base Terra Aberta",
        language="Língua Orvalho",
    )

    file = await pulse(client, circle)

    assert "Lugar Secreto" not in file and "Vila Escondida" not in file
    assert "nevoa-lugar-secreto" not in file
    # The language's own name can name the place, so a sensitive project with no public name
    # registered is headed by words, not by the name (OBT-560).
    assert "Língua Névoa" not in file
    assert "• Projeto sensível — África" in file
    assert "• Língua Orvalho — Terra Aberta" in file
    assert "Base Terra Aberta" not in file

    english = await pulse(client, circle, lang="en")
    assert "• Sensitive project — Africa" in english


@pytest.mark.parametrize("lang", ["pt-BR", "en"])
async def test_the_pulse_names_no_place_it_cannot_tell(client, db_session, circle, lang) -> None:
    """``other`` is the console's *América Central* and also where every country the map does not
    know falls, so an entry whose country the Pulse does not print — withheld, or never written —
    goes out with no place rather than a guess, in a file that cannot be recalled."""
    await seed(
        db_session,
        "sereno-lugar-secreto",
        text=SHARED,
        visibility=ShemaPrayerVisibility.REDE,
        sensitive=True,
        location="Lugar Secreto",
        language="Língua Sereno",
    )
    await seed(
        db_session,
        "tordo",
        text=SHARED_NEED,
        visibility=ShemaPrayerVisibility.REDE,
        location="",
        language="Língua Tordo",
    )

    lines = (await pulse(client, circle, lang=lang)).splitlines()

    unnamed = "• Projeto sensível" if lang == "pt-BR" else "• Sensitive project"
    assert unnamed in lines and "• Língua Tordo" in lines
    assert not any("Central" in line or "Lugar Secreto" in line for line in lines)


async def test_the_wall_entry_of_a_withheld_project_carries_no_country_and_no_base(
    client, db_session, shema_app
) -> None:
    """The wall is an output path: the region's own coordinator reads the region here too."""
    coordinator = await person(db_session, shema_app, "coordinator", regions=(HOME, AWAY))
    await seed(
        db_session,
        "pico-lugar-secreto",
        text=SHARED,
        visibility=ShemaPrayerVisibility.REDE,
        sensitive=True,
        region=AWAY,
        location="Lugar Secreto",
        team="Base Lugar Secreto",
    )
    await seed(
        db_session,
        "quinta-vale",
        text=SHARED_NEED,
        visibility=ShemaPrayerVisibility.REDE,
        location="Terra Aberta, Vila Nova",
        team="Base Terra Aberta",
    )

    body = {entry["projectId"]: entry for entry in await wall(client, coordinator)}

    withheld = body["pico-lugar-secreto"]
    assert withheld["country"] == "" and withheld["base"] == ""
    assert withheld["locationWithheld"] is True and withheld["region"] == AWAY.value
    assert withheld["languageNameWithheld"] is True and withheld["language"] == AWAY.value
    assert "Lugar Secreto" not in str(withheld)
    open_entry = body["quinta-vale"]
    assert open_entry["country"] == "Terra Aberta" and open_entry["base"] == "Base Terra Aberta"
    assert open_entry["locationWithheld"] is False
    assert set(open_entry) == {
        "id",
        "projectId",
        "language",
        "base",
        "country",
        "region",
        "locationWithheld",
        "languageNameWithheld",
        "text",
        "source",
        "answered",
        "date",
    }


@pytest.mark.parametrize(
    ("lang", "network_only", "no_recall", "name"),
    [
        (
            "pt-BR",
            "Só para a rede de intercessores. Ao receber este arquivo, você se compromete a não "
            "repassá-lo.",
            "Depois de enviado, o que está aqui não pode ser recolhido.",
            "pulso-de-oracao-",
        ),
        (
            "en",
            "For the intercessor network only. By receiving this file you commit not to forward "
            "it.",
            "Once sent, what is here cannot be recalled.",
            "prayer-pulse-",
        ),
    ],
)
async def test_the_pulse_says_it_is_for_the_network_only_and_cannot_be_recalled(
    client, db_session, circle, lang, network_only, no_recall, name
) -> None:
    """Both sentences, before the first request, so a file cut short by a forward still says
    them — and a file that is not kept anywhere on the way."""
    await seed(db_session, "rio-vale", text=SHARED, visibility=ShemaPrayerVisibility.REDE)

    response = await client.get(PULSE, params={"lang": lang}, headers=circle)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert response.headers["cache-control"] == "private, no-store"
    disposition = response.headers["content-disposition"]
    assert disposition.startswith(f'attachment; filename="{name}') and disposition.endswith('.txt"')
    file = response.text
    assert file.index(network_only) < file.index(SHARED)
    assert file.index(no_recall) < file.index(SHARED)


async def test_a_language_the_console_does_not_speak_is_refused(client, circle) -> None:
    assert (await client.get(PULSE, params={"lang": "fr"}, headers=circle)).status_code == 422


async def test_the_record_hides_an_unauthorized_request_from_the_resource_circle(
    client, db_session, circle
) -> None:
    """The wall's own audience reads what the team authorized, on the record as on the wall."""
    await seed(db_session, "sol-vale", text=KEPT, visibility=ShemaPrayerVisibility.COORDENACAO)
    await seed(db_session, "sombra-vale", text=SHARED, visibility=ShemaPrayerVisibility.REDE)

    kept = await client.get(f"{PROJECTS}/sol-vale", headers=circle)
    shared = await client.get(f"{PROJECTS}/sombra-vale", headers=circle)

    assert kept.status_code == shared.status_code == 200
    assert kept.json()["prayerRequests"] == "" and KEPT not in kept.text
    assert kept.json()["prayerVisibility"] == "coordenacao"
    assert shared.json()["prayerRequests"] == SHARED


@pytest.mark.parametrize("role_key", ["coordinator", "obtLab"])
async def test_the_follow_up_reads_an_unauthorized_request_on_the_record(
    client, db_session, shema_app, role_key
) -> None:
    """``coordenacao`` is a destination: the people who follow up and support read it."""
    await seed(db_session, "tarde-vale", text=KEPT)
    headers = await person(db_session, shema_app, role_key)

    response = await client.get(f"{PROJECTS}/tarde-vale", headers=headers)

    assert response.status_code == 200
    assert response.json()["prayerRequests"] == KEPT


@pytest.mark.parametrize(
    "body",
    [{"prayerRequests": SHARED}, {"prayerVisibility": "rede"}, {"prayerRequestsAudio": "a/b"}],
)
async def test_the_resource_circle_may_not_write_a_request_it_cannot_read(
    client, db_session, circle, body
) -> None:
    """Não dá para editar o que não se vê: overwriting a text read as ``""``, or publishing it
    unseen. Since Daniel's decision of 7/oct/2026 (OBT-571) the Circle writes nothing at all, so
    the refusal is the Circle's own, before the version is compared, and nothing moves."""
    project = await seed(db_session, "uva-vale", text=KEPT)

    response = await patch(client, circle, project.id, body)

    assert response.status_code == 403
    assert "Resource Circle reads a project and does not edit it" in response.text
    await db_session.refresh(project)
    assert project.prayer_requests == KEPT and project.prayer_visibility is None
    assert project.version == 1


async def test_the_resource_circle_no_longer_writes_the_rest_of_the_record(
    client, db_session, circle
) -> None:
    """It did until OBT-571; Daniel (7/oct/2026) read Karina's *só não podem editar* whole."""
    project = await seed(db_session, "vento-vale", text=KEPT)

    response = await patch(client, circle, project.id, {"statusComments": "visita marcada"})

    assert response.status_code == 403, response.text
    await db_session.refresh(project)
    assert project.prayer_requests == KEPT and project.version == 1


@pytest.mark.parametrize(
    ("shared", "row"),
    [
        (False, {"prayerShared": True}),
        (True, {"prayerShared": False}),
        (None, {"category": "financial", "description": KEPT_NEED, "prayerShared": True}),
    ],
    ids=["shares-a-kept-need", "unshares-a-shared-need", "raises-a-need-already-shared"],
)
async def test_the_resource_circle_may_not_decide_what_a_need_shares(
    client, db_session, circle, shared, row
) -> None:
    """A need's ``prayerShared`` is an authorization like the project's visibility: the role that
    shares with the network does not decide it, in either direction, on a need it raises or on
    one that exists — and since OBT-571 (Daniel, 7/oct/2026) writes no need at all, so the
    refusal is the Circle's own. Nothing is written and nothing reaches the wall or the Pulse."""
    project = await seed(db_session, "vime-vale")
    existing = None
    if shared is not None:
        existing = await need(db_session, project, KEPT_NEED, shared=shared)
        row = {"id": existing.id, **row}

    response = await patch(client, circle, project.id, {"needsItems": [row]})

    assert response.status_code == 403, response.text
    assert "Resource Circle reads a project and does not edit it" in response.text
    stored = (await db_session.execute(select(ShemaNeed))).scalars().all()
    assert [(item.id, item.prayer_shared) for item in stored] == (
        [] if existing is None else [(existing.id, shared)]
    )
    await db_session.refresh(project)
    assert project.version == 1
    if not shared:
        assert await wall(client, circle) == []
        assert KEPT_NEED not in await pulse(client, circle)


async def test_the_resource_circle_no_longer_works_the_needs(client, db_session, circle) -> None:
    """The needs were the Resource Circle's own work until OBT-571; Daniel (7/oct/2026) closed
    the Circle's every write, the needs included. The row and the wall stay as they were."""
    project = await seed(db_session, "vime-serra")
    row = await need(db_session, project, SHARED_NEED, shared=True)

    response = await patch(
        client,
        circle,
        project.id,
        {
            "needsItems": [
                {
                    "id": row.id,
                    "status": "in-progress",
                    "description": SHARED_NEED,
                    "prayerShared": True,
                },
                {"category": "training", "description": "Oficina de gravação"},
            ]
        },
    )

    assert response.status_code == 403, response.text
    await db_session.refresh(row)
    assert row.prayer_shared is True and row.status.value != "in-progress"
    assert texts(await wall(client, circle)) == {SHARED_NEED}


async def test_the_resource_circle_may_not_keep_a_share_on_a_text_it_rewrote(
    client, db_session, circle
) -> None:
    """The flag does not move, and the decision is still there: restating ``prayerShared`` over a
    new description is sharing the new text, and the team authorized the one it replaced."""
    project = await seed(db_session, "vime-rio")
    row = await need(db_session, project, SHARED_NEED, shared=True)

    response = await patch(
        client,
        circle,
        project.id,
        {"needsItems": [{"id": row.id, "description": KEPT_NEED, "prayerShared": True}]},
    )

    assert response.status_code == 403, response.text
    assert "Resource Circle reads a project and does not edit it" in response.text
    await db_session.refresh(row)
    assert (row.description, row.prayer_shared) == (SHARED_NEED, True)
    assert texts(await wall(client, circle)) == {SHARED_NEED}
    assert KEPT_NEED not in await pulse(client, circle)


async def test_a_need_the_resource_circle_tries_to_rewrite_stays_on_the_wall(
    client, db_session, circle
) -> None:
    """Until OBT-571 the rewrite was the Circle's to make and withdrew the share; since Daniel's
    decision of 7/oct/2026 the Circle writes no need, so the text and the share stay."""
    project = await seed(db_session, "vime-lago")
    row = await need(db_session, project, SHARED_NEED, shared=True)

    response = await patch(
        client, circle, project.id, {"needsItems": [{"id": row.id, "description": KEPT_NEED}]}
    )

    assert response.status_code == 403, response.text
    await db_session.refresh(row)
    assert (row.description, row.prayer_shared) == (SHARED_NEED, True)
    assert texts(await wall(client, circle)) == {SHARED_NEED}


@pytest.mark.parametrize(
    "body",
    [
        {"prayerVisibility": "rede", "prayerRequests": KEPT},
        {"needsItems": [{"category": "financial", "description": KEPT_NEED, "prayerShared": True}]},
    ],
    ids=["authorizes-the-request", "shares-a-need"],
)
async def test_the_resource_circle_may_not_authorize_on_a_create_either(
    client, db_session, circle, body
) -> None:
    """A create shows its author what they type, so the text is theirs to write — the decision to
    share it is not, on a new record any more than on an old one.

    The request's session is this test's, so it is rolled back here as the request's own is
    discarded when the refusal leaves the handler: nothing was committed."""
    payload = {**CREATE, **body}

    response = await client.post(PROJECTS, json=payload, headers=circle)

    assert response.status_code == 403, response.text
    assert "Resource Circle reads a project and does not edit it" in response.text
    await db_session.rollback()
    assert (await db_session.execute(select(ShemaProject))).scalars().all() == []


async def test_the_resource_circle_no_longer_creates_a_record(client, db_session, circle) -> None:
    """It did until OBT-571 — the console's create sends every field it holds — and since
    Daniel's decision of 7/oct/2026 it is refused as every other write of the Circle's."""
    response = await client.post(
        PROJECTS, json={**CREATE, "prayerRequests": KEPT, "needsItems": []}, headers=circle
    )

    assert response.status_code == 403, response.text
    assert await wall(client, circle) == []


@pytest.mark.parametrize("role_key", ["coordinator", "obtLab"])
async def test_only_the_resource_circle_generates_the_pulse(
    client, db_session, shema_app, circle, role_key
) -> None:
    await seed(db_session, "xisto-vale", text=SHARED, visibility=ShemaPrayerVisibility.REDE)
    other = await person(db_session, shema_app, role_key)

    assert (await client.get(PULSE, headers=other)).status_code == 403
    assert (await client.get(PULSE, headers=circle)).status_code == 200


async def test_the_wall_and_the_pulse_need_a_shema_account(client, db_session) -> None:
    from tests.baker import make_user

    stranger = await make_user(db_session, email="sem-papel@oracao.test")
    headers = await auth_header(db_session, stranger)

    assert (await client.get(WALL)).status_code in (401, 403)
    assert (await client.get(WALL, headers=headers)).status_code == 403
    assert (await client.get(PULSE, headers=headers)).status_code == 403


async def test_the_wall_and_the_pulse_are_scoped(
    client, db_session, shema_app, circle, strategist
) -> None:
    """A regional Resource Circle's wall and file carry its own regions; a coordinator holding
    every region reads the whole wall."""
    await seed(db_session, "zinco-vale", text=SHARED, visibility=ShemaPrayerVisibility.REDE)
    await seed(
        db_session,
        "zimbro-monte",
        text=SHARED_NEED,
        visibility=ShemaPrayerVisibility.REDE,
        region=AWAY,
        location="Monte Sereno",
    )
    mentor = await person(db_session, shema_app, "obtLab")

    assert texts(await wall(client, circle)) == {SHARED}
    assert texts(await wall(client, mentor)) == {SHARED}
    assert texts(await wall(client, strategist)) == {SHARED, SHARED_NEED}
    file = await pulse(client, circle)
    assert SHARED in file and SHARED_NEED not in file


async def test_a_project_the_admin_has_not_confirmed_reaches_neither_the_wall_nor_the_pulse(
    client, db_session, circle, strategist
) -> None:
    """A project the mesa's approval filed is nobody's until the Admin confirms it (OBT-547), and
    the wall starts where every reader starts — so an authorized request on one, and a need it
    shared, reach neither output, for the global seat either."""
    pending = await seed(
        db_session, "sereia-vale", text=KEPT, visibility=ShemaPrayerVisibility.REDE
    )
    pending.pending_confirmation = True
    await db_session.commit()
    await need(db_session, pending, KEPT_NEED, shared=True)
    await seed(db_session, "sabia-vale", text=SHARED, visibility=ShemaPrayerVisibility.REDE)

    assert texts(await wall(client, circle)) == {SHARED}
    assert texts(await wall(client, strategist)) == {SHARED}
    file = await pulse(client, circle)
    assert SHARED in file and KEPT not in file and KEPT_NEED not in file


async def test_the_wall_reads_the_needs_of_its_own_projects_only(db_session) -> None:
    """The one query for needs is keyed by the projects handed in, so a need of a project out of
    scope cannot ride along with one in it."""
    inside = await seed(db_session, "abeto-vale")
    outside = await seed(db_session, "acacia-monte", region=AWAY)
    await need(db_session, outside, SHARED_NEED, shared=True)

    authorized = await authorized_requests_by_project(db_session, [inside])

    assert authorized == {inside.id: []}
    stored = (await db_session.execute(select(ShemaNeed))).scalars().all()
    assert [row.project_id for row in stored] == [outside.id]
