"""The projects a person is on, on the Admin's lookup — OBT-679, through the real routes.

The Admin searched a person and saw the roles and regions, never the teams, and had to guess the
project to take somebody off one. The lookup now answers the account's live memberships, each its
id and the language's name as the reader reads it, and the grant and the revocation answer the
same list, because the screen redraws from one reply.

Memberships are written through ``POST``/``DELETE /projects/{id}/members`` — the route the PME's
*Tirar do projeto* calls — and the projects are rows built here, with the columns a sensitive
project needs, rather than through the shared ``make_shema_project``. Every account is an ordinary
one: the Admin holds ``admin`` in both apps and is not an installation admin
(``tests/shema_admin_harness.py``).
"""

from __future__ import annotations

from app.api.shema._deps import APP_KEY, FORM_APP_KEY
from app.db.models.shema import ShemaProject
from app.db.models.shema_enums import ShemaRegionKey
from app.services.shema import GrantApps, account_grants
from app.services.shema._scope import NO_COORDINATION
from tests.shema_admin_harness import (
    GRANTS,
    PEOPLE,
    REVOKE,
    make_account,
    make_admin,
    surface_client,
)
from tests.test_shema.conftest import PREFIX

APPS = GrantApps(shema=APP_KEY, form=FORM_APP_KEY)
AFRICA = ShemaRegionKey.AFRICA
SECRET_PLACE = "Terra Sigilosa, Vale Escondido"
SECRET_BASE = "JOCUM Vale Escondido"


async def _project(
    db_session,
    project_id: str,
    name: str,
    *,
    sensitive: bool = False,
    public_name: str | None = None,
) -> ShemaProject:
    row = ShemaProject(
        id=project_id,
        language_name=name,
        location=SECRET_PLACE if sensitive else "Campo Aberto",
        team=SECRET_BASE if sensitive else "JOCUM Campo Aberto",
        sensitive_country=sensitive,
        public_language_name=public_name,
        region_key=AFRICA,
    )
    db_session.add(row)
    await db_session.commit()
    return row


def _members(project_id: str) -> str:
    return f"{PREFIX}/projects/{project_id}/members"


async def _join(client, headers, project_id: str, user_id: str) -> None:
    res = await client.post(_members(project_id), json={"userId": user_id}, headers=headers)
    assert res.status_code == 201, res.text


async def _leave(client, headers, project_id: str, user_id: str) -> None:
    res = await client.delete(f"{_members(project_id)}/{user_id}", headers=headers)
    assert res.status_code == 204, res.text


async def _lookup(client, headers, email: str) -> list[dict]:
    res = await client.get(PEOPLE, params={"email": email}, headers=headers)
    assert res.status_code == 200, res.text
    return res.json()["projects"]


async def test_the_lookup_lists_the_projects_the_person_is_a_live_member_of(
    db_session, shema_app, form_app
) -> None:
    """Live memberships only, ordered by the name — folded, so *Ávila* is not filed after *Zulu*
    — and not by the id, which here runs the other way."""
    _admin, headers = await make_admin(db_session, shema_app, form_app)
    person = await make_account(db_session, "person@shema.example")
    other = await make_account(db_session, "other@shema.example")
    await _project(db_session, "p-a", "Zulu")
    await _project(db_session, "p-b", "Ávila")
    await _project(db_session, "p-c", "Encerrado")
    await _project(db_session, "p-d", "Alheio")
    await _project(db_session, "p-e", "Sem Vínculo")

    async with surface_client(db_session) as client:
        await _join(client, headers, "p-a", person.id)
        await _join(client, headers, "p-b", person.id)
        await _join(client, headers, "p-c", person.id)
        await _leave(client, headers, "p-c", person.id)
        await _join(client, headers, "p-d", other.id)
        projects = await _lookup(client, headers, person.email)

    assert [(ref["id"], ref["languageName"]) for ref in projects] == [
        ("p-b", "Ávila"),
        ("p-a", "Zulu"),
    ]


async def test_a_person_on_no_team_answers_an_empty_list(db_session, shema_app, form_app) -> None:
    """Present and empty — the screen says *on no team*, which an absent field could not mean."""
    _admin, headers = await make_admin(db_session, shema_app, form_app)
    person = await make_account(db_session, "person@shema.example")

    async with surface_client(db_session) as client:
        res = await client.get(PEOPLE, params={"email": person.email}, headers=headers)

    assert res.json()["projects"] == []


async def test_taking_the_person_off_a_team_takes_the_project_off_the_lookup(
    db_session, shema_app, form_app
) -> None:
    """The PME's *Tirar do projeto* is this ``DELETE``; the lookup it re-reads no longer lists the
    project, and coming back lists it once."""
    _admin, headers = await make_admin(db_session, shema_app, form_app)
    person = await make_account(db_session, "person@shema.example")
    await _project(db_session, "p-leave", "Makua")

    async with surface_client(db_session) as client:
        await _join(client, headers, "p-leave", person.id)
        assert [ref["id"] for ref in await _lookup(client, headers, person.email)] == ["p-leave"]

        await _leave(client, headers, "p-leave", person.id)
        assert await _lookup(client, headers, person.email) == []

        await _join(client, headers, "p-leave", person.id)
        assert [ref["id"] for ref in await _lookup(client, headers, person.email)] == ["p-leave"]


async def test_a_grant_and_a_revocation_answer_the_persons_projects_too(
    db_session, shema_app, form_app
) -> None:
    """The card is redrawn from the answer of a grant, so an answer without the projects would
    empty the list every time a role changed."""
    _admin, headers = await make_admin(db_session, shema_app, form_app)
    person = await make_account(db_session, "person@shema.example")
    await _project(db_session, "p-team", "Makua")
    body = {"userId": person.id, "appKey": FORM_APP_KEY, "roleKey": "gestor"}

    async with surface_client(db_session) as client:
        await _join(client, headers, "p-team", person.id)
        granted = await client.post(GRANTS, json=body, headers=headers)
        revoked = await client.post(REVOKE, json=body, headers=headers)

    assert granted.status_code == 200, granted.text
    assert revoked.status_code == 200, revoked.text
    for answer in (granted.json(), revoked.json()):
        assert [(ref["id"], ref["languageName"]) for ref in answer["projects"]] == [
            ("p-team", "Makua")
        ]


async def test_the_admin_reads_a_sensitive_projects_own_name(
    db_session, shema_app, form_app
) -> None:
    """The Admin reads as the coordination everywhere (``COORDINATION_EVERYWHERE``), so the name is
    the language's own and not the one coordination registered for everybody else."""
    _admin, headers = await make_admin(db_session, shema_app, form_app)
    person = await make_account(db_session, "person@shema.example")
    await _project(
        db_session, "p-sens", "Lingua Secreta", sensitive=True, public_name="Lingua Publica"
    )

    async with surface_client(db_session) as client:
        await _join(client, headers, "p-sens", person.id)
        projects = await _lookup(client, headers, person.email)

    assert projects == [
        {
            "id": "p-sens",
            "languageName": "Lingua Secreta",
            "locationWithheld": True,
            "languageNameWithheld": False,
        }
    ]


async def test_the_name_is_the_boundarys_for_a_reader_who_does_not_read_the_truth(
    db_session, shema_app, form_app
) -> None:
    """The name is built for the reader by ``LeavingShape``, never copied off the row: built for a
    reader who coordinates nothing, a sensitive project reads the public name coordination
    registered — or the region key while none is — and says the name is not the language's own.
    """
    _admin, headers = await make_admin(db_session, shema_app, form_app)
    person = await make_account(db_session, "person@shema.example")
    await _project(
        db_session, "p-public", "Lingua Secreta", sensitive=True, public_name="Lingua Publica"
    )
    await _project(db_session, "p-unnamed", "Outra Secreta", sensitive=True)
    await _project(db_session, "p-open", "Makua")

    async with surface_client(db_session) as client:
        for project_id in ("p-public", "p-unnamed", "p-open"):
            await _join(client, headers, project_id, person.id)

    account = await account_grants(db_session, APPS, person, readership=NO_COORDINATION)

    named = {ref.id: (ref.language_name, ref.language_name_withheld) for ref in account.projects}
    assert named == {
        "p-public": ("Lingua Publica", True),
        "p-unnamed": (AFRICA.value, True),
        "p-open": ("Makua", False),
    }


async def test_a_project_on_the_lookup_carries_its_id_and_name_and_no_place(
    db_session, shema_app, form_app
) -> None:
    """A narrow ref: the id the ``DELETE`` takes and the name the card prints — never the place or
    the base of a sensitive project, on the body as it is serialised."""
    _admin, headers = await make_admin(db_session, shema_app, form_app)
    person = await make_account(db_session, "person@shema.example")
    await _project(db_session, "p-sens", "Lingua Secreta", sensitive=True)

    async with surface_client(db_session) as client:
        await _join(client, headers, "p-sens", person.id)
        res = await client.get(PEOPLE, params={"email": person.email}, headers=headers)

    [ref] = res.json()["projects"]
    assert set(ref) == {"id", "languageName", "locationWithheld", "languageNameWithheld"}
    assert SECRET_PLACE not in res.text
    assert SECRET_BASE not in res.text
