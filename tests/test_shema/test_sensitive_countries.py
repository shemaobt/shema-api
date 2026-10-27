"""OBT-616 — the sensitive-country list marks new projects by itself; the mark by project stays.

Karina, via Daniel, 19/out/2026: India, China, Iran, Iraq and the Middle East are sensitive, and a
project in one of them is sensitive **by its country**; a project in a country that is not can still
be marked on its own. Every test here is one line of that, over the real router:

* the list is the Admin's — read and replaced whole by the Admin alone, a 403 for every other role;
* a place that names a listed country, in Portuguese or English, at any position, raises the flag
  of a create and a save — and nothing in the rule lowers it;
* the mark by project works as it did;
* a project already stored does not move until somebody writes it;
* the record tells a reader of the truth which listed countries its place names, and nobody else.

The confirmation and the filing are ``test_pending_projects.py``'s, the import
``test_transfer.py``'s — each beside its own helpers.
"""

from __future__ import annotations

import ast
import uuid
from pathlib import Path

import pytest
from sqlalchemy import select

from app.db.models.shema import ShemaProject
from app.db.models.shema_change_log import ShemaChangeLog
from app.db.models.shema_enums import ShemaRegionKey
from app.utils.shema_derivations import SensitiveCountries
from tests.shema_admin_harness import make_account
from tests.shema_harness import LISTED, list_countries
from tests.test_shema.conftest import PREFIX, auth_header, make_scoped_user

LIST = f"{PREFIX}/sensitive-countries"
PROJECTS = f"{PREFIX}/projects"
REPO_ROOT = Path(__file__).resolve().parents[2]

#: The record a coordinator of ``other`` and ``asia`` files; ``location`` is each test's.
NEW = {
    "languageName": "Língua do Vale",
    "bridgeLanguage": "Português",
    "team": "Base do Vale",
    "objective": ["NT"],
}


def _new_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture()
async def coordination(db_session, shema_app) -> dict[str, str]:
    """A regional coordinator of ``other`` (where Iran lands) and ``asia`` — not an admin."""
    user = await make_scoped_user(
        db_session,
        shema_app,
        email="coordenacao.sensivel@shema.test",
        role_key="coordinator",
        regions=[ShemaRegionKey.OTHER, ShemaRegionKey.ASIA],
    )
    return await auth_header(db_session, user)


@pytest.fixture()
async def admin(db_session, shema_app) -> dict[str, str]:
    """The Admin — the ``admin`` role of the app, never an installation admin."""
    user = await make_scoped_user(
        db_session, shema_app, email="admin.lista@shema.test", role_key="admin"
    )
    return await auth_header(db_session, user)


@pytest.fixture()
async def listed(db_session) -> None:
    await list_countries(db_session)


async def _create(client, headers, location: str, **fields):
    return await client.post(
        PROJECTS, json={**NEW, "id": _new_id(), "location": location, **fields}, headers=headers
    )


async def _stored(db_session, project_id: str) -> ShemaProject:
    stmt = (
        select(ShemaProject)
        .where(ShemaProject.id == project_id)
        .execution_options(populate_existing=True)
    )
    return (await db_session.execute(stmt)).scalar_one()


async def _patch(client, headers, project_id: str, body: dict):
    read = await client.get(f"{PROJECTS}/{project_id}", headers=headers)
    assert read.status_code == 200, read.text
    return await client.patch(
        f"{PROJECTS}/{project_id}", json=body, headers={**headers, "If-Match": read.headers["ETag"]}
    )


# --- the list is the Admin's ----------------------------------------------------------------


async def test_only_the_admin_reads_and_replaces_the_list(client, db_session, admin, listed):
    read = await client.get(LIST, headers=admin)
    replaced = await client.put(
        LIST,
        json={"countries": [{"name": " Síria ", "spellings": ["Syria", " ", "Syria"]}]},
        headers=admin,
    )
    again = await client.get(LIST, headers=admin)

    assert read.status_code == 200, read.text
    assert read.headers["Cache-Control"] == "private, no-store"
    assert read.json() == {
        "countries": [
            {"name": "Índia", "spellings": ["India"]},
            {"name": "Irã", "spellings": ["Iran", "Irão"]},
        ]
    }
    assert replaced.status_code == 200, replaced.text
    assert again.json() == {"countries": [{"name": "Síria", "spellings": ["Syria"]}]}


@pytest.mark.parametrize(
    ("role", "app_name"),
    [
        ("coordinator", "shema"),
        ("obtLab", "shema"),
        ("resourceCircle", "shema"),
        ("gestor", "form"),
        ("mesa", "form"),
        (None, None),
    ],
)
async def test_every_other_role_is_refused_the_list(
    client, db_session, shema_app, form_app, listed, role, app_name
):
    """Never an admin account here: ``require_role`` lets one through, and a refusal proved with it
    would hold with the guard deleted."""
    apps = {"shema": shema_app, "form": form_app}
    grants = [] if role is None else [(apps[app_name], role)]
    account = await make_account(db_session, f"{role or 'sem-papel'}@lista.test", *grants)
    headers = await auth_header(db_session, account)

    read = await client.get(LIST, headers=headers)
    replaced = await client.put(LIST, json={"countries": []}, headers=headers)

    assert (read.status_code, replaced.status_code) == (403, 403), (read.text, replaced.text)
    still = await client.get(LIST, headers=await _admin_headers(db_session, shema_app))
    assert [entry["name"] for entry in still.json()["countries"]] == ["Índia", "Irã"]


async def _admin_headers(db_session, shema_app) -> dict[str, str]:
    user = await make_scoped_user(
        db_session, shema_app, email="admin.confere@shema.test", role_key="admin"
    )
    return await auth_header(db_session, user)


@pytest.mark.parametrize(
    "countries",
    [
        [{"name": "Egito", "spellings": ["Egypt"]}, {"name": "Egypt"}],
        [{"name": "Irã", "spellings": ["Iran"]}, {"name": "IRAN "}],
        [{"name": "Síria"}, {"name": "Siria"}],
        [{"name": "Irã"}, {"name": "Irã"}],
    ],
)
async def test_a_list_that_gives_one_spelling_to_two_countries_is_refused(
    client, admin, listed, countries
):
    """*Siria* and *Síria* are one key, and *Egypt* is the map's spelling of *Egito*: a place that
    writes it would be read as either country."""
    response = await client.put(LIST, json={"countries": countries}, headers=admin)

    assert response.status_code == 422, response.text
    after = await client.get(LIST, headers=admin)
    assert [entry["name"] for entry in after.json()["countries"]] == ["Índia", "Irã"]


@pytest.mark.parametrize(
    "country",
    [{"name": "Coreia, do Norte"}, {"name": "Irã", "spellings": ["Iran, Irão"]}, {"name": " "}],
)
async def test_a_name_with_a_comma_or_no_name_is_refused(client, admin, country):
    """The place is split on commas, so a name holding one could never match a part of it."""
    response = await client.put(LIST, json={"countries": [country]}, headers=admin)

    assert response.status_code == 422, response.text


async def test_replacing_the_list_leaves_a_mark_that_names_no_country(
    client, db_session, admin, listed
):
    """The change log is read by the coordination of every region; the list is the Admin's."""
    same = await client.put(
        LIST,
        json={"countries": [{"name": name, "spellings": list(s)} for name, s in LISTED]},
        headers=admin,
    )
    changed = await client.put(LIST, json={"countries": [{"name": "Chipre"}]}, headers=admin)

    assert (same.status_code, changed.status_code) == (200, 200)
    marks = (
        (
            await db_session.execute(
                select(ShemaChangeLog).where(ShemaChangeLog.subject == "sensitive_countries")
            )
        )
        .scalars()
        .all()
    )
    assert len(marks) == 1, "a save that changed nothing leaves no mark"
    [mark] = marks
    assert mark.action == "replaced"
    assert (mark.subject_id, mark.field_keys, mark.region_key) == (None, None, None)


def test_only_the_list_owner_names_the_table() -> None:
    """*Lida pelo servidor num lugar só*: what the save compares a place with and what the Admin
    reads are one reading of one table."""
    naming = sorted(
        source.name
        for package in ("services", "api")
        for source in (REPO_ROOT / "app" / package / "shema").glob("*.py")
        if any(
            isinstance(node, ast.Name) and node.id == "ShemaSensitiveCountry"
            for node in ast.walk(ast.parse(source.read_text(encoding="utf-8")))
        )
    )
    assert naming == ["_sensitive_list.py"]


# --- a listed place raises the flag ------------------------------------------------------------


@pytest.mark.parametrize("location", ["Irã", "Iran", "Laos, Irã", "iran", "Índia", "Nepal, India"])
async def test_a_project_created_in_a_listed_country_is_born_sensitive(
    client, db_session, coordination, listed, location
):
    created = await _create(client, coordination, location)

    assert created.status_code == 201, created.text
    assert created.json()["sensitiveCountry"] is True
    assert (await _stored(db_session, created.json()["id"])).sensitive_country is True


async def test_a_project_created_off_the_list_is_born_open(
    client, db_session, coordination, listed
):
    created = await _create(client, coordination, "Laos, Teerã do Norte")

    assert created.status_code == 201, created.text
    assert (await _stored(db_session, created.json()["id"])).sensitive_country is False


async def test_a_save_that_moves_the_place_into_a_listed_country_raises_the_flag(
    client, db_session, coordination, listed
):
    created = await _create(client, coordination, "Laos")

    saved = await _patch(client, coordination, created.json()["id"], {"location": "Laos, Irão"})

    assert saved.status_code == 200, saved.text
    assert saved.json()["sensitiveCountry"] is True
    assert saved.json()["listedCountries"] == ["Irã"]


# --- the mark by project, and nothing lowers it ------------------------------------------------


async def test_a_project_is_still_marked_by_hand_where_the_country_is_not_listed(
    client, db_session, coordination, listed
):
    """The north of Brazil: the country is not sensitive, the project is."""
    created = await _create(client, coordination, "Laos")
    project_id = created.json()["id"]

    marked = await _patch(client, coordination, project_id, {"sensitiveCountry": True})
    cleared = await _patch(client, coordination, project_id, {"sensitiveCountry": False})

    assert marked.json()["sensitiveCountry"] is True
    assert marked.json()["listedCountries"] == []
    assert cleared.status_code == 200, cleared.text
    assert (await _stored(db_session, project_id)).sensitive_country is False


async def test_unticking_a_listed_project_leaves_the_flag_raised_and_saves_nothing(
    client, db_session, coordination, listed
):
    created = await _create(client, coordination, "Irã")
    project_id = created.json()["id"]

    unticked = await _patch(client, coordination, project_id, {"sensitiveCountry": False})

    assert unticked.status_code == 200, unticked.text
    assert unticked.json()["sensitiveCountry"] is True
    assert unticked.headers["ETag"] == created.headers["ETag"], "a save that changed nothing"
    assert (await _stored(db_session, project_id)).version == 1


async def test_moving_the_place_or_the_country_off_the_list_never_lowers_the_flag(
    client, db_session, coordination, admin, listed
):
    moved = (await _create(client, coordination, "Irã")).json()["id"]
    kept = (await _create(client, coordination, "Iran")).json()["id"]

    off_place = await _patch(client, coordination, moved, {"location": "Laos"})
    off_list = await client.put(LIST, json={"countries": [{"name": "Índia"}]}, headers=admin)
    after = await _patch(client, coordination, kept, {"notes": "nada mudou de lugar"})

    assert off_place.status_code == 200, off_place.text
    assert off_place.json()["sensitiveCountry"] is True
    assert off_place.json()["listedCountries"] == [], "held by its own mark now"
    assert off_list.status_code == 200, off_list.text
    assert after.json()["sensitiveCountry"] is True
    assert (await _stored(db_session, moved)).sensitive_country is True
    assert (await _stored(db_session, kept)).sensitive_country is True


# --- a stored project does not move until somebody writes it -----------------------------------


async def test_a_stored_project_is_not_flagged_by_reading_it_or_by_changing_the_list(
    client, db_session, coordination, admin
):
    """Daniel, 19/out/2026: *não há migração nem checagem retroativa*. A row written before the
    list — or before its country joined it — keeps its flag through every read and every change
    of the list; the first write that reaches it is what applies the rule."""
    stored = ShemaProject(
        id="5f0c2b9e-3d4a-4e6b-8c1d-2a3b4c5d6e7f",
        language_name="Língua Gravada",
        location="Irã",
        region_key=ShemaRegionKey.OTHER,
    )
    db_session.add(stored)
    await db_session.commit()

    added = await client.put(LIST, json={"countries": [{"name": "Irã"}]}, headers=admin)
    record = await client.get(f"{PROJECTS}/{stored.id}", headers=coordination)
    collection = await client.get(PROJECTS, headers=coordination)
    before_any_write = (await _stored(db_session, stored.id)).sensitive_country
    written = await _patch(client, coordination, stored.id, {"notes": "primeira escrita"})

    assert added.status_code == 200, added.text
    assert record.json()["sensitiveCountry"] is False
    assert record.json()["listedCountries"] == ["Irã"]
    assert collection.status_code == 200, collection.text
    assert before_any_write is False
    assert written.json()["sensitiveCountry"] is True


# --- what the record tells, and to whom --------------------------------------------------------


async def test_the_record_tells_coordination_which_listed_countries_its_place_names(
    client, coordination, listed
):
    created = await _create(client, coordination, "Nepal, Índia, Irã, Iran")

    assert created.json()["listedCountries"] == ["Índia", "Irã"]


async def test_a_reader_who_does_not_read_the_truth_is_told_no_listed_country(
    client, db_session, shema_app, coordination, listed
):
    created = (await _create(client, coordination, "Irã")).json()
    lab = await make_scoped_user(
        db_session,
        shema_app,
        email="lab.lista@shema.test",
        role_key="obtLab",
        regions=[ShemaRegionKey.OTHER],
    )

    read = await client.get(
        f"{PROJECTS}/{created['id']}", headers=await auth_header(db_session, lab)
    )

    assert read.status_code == 200, read.text
    assert read.json()["listedCountries"] == []
    assert "Irã" not in read.text


# --- the comparison itself ---------------------------------------------------------------------


def test_the_list_reads_portuguese_and_english_in_any_position_case_and_accents_aside() -> None:
    listed = SensitiveCountries.of([*LISTED, ("Síria", ("Syria",)), ("Egito", ("Egypt",))])

    assert listed.named_in("Irã") == ("Irã",)
    assert listed.named_in("Teerã, IRAN") == ("Irã",)
    assert listed.named_in("Laos, Siria") == ("Síria",)
    assert listed.named_in("China, Laos, india") == ("Índia",)
    assert listed.named_in("Egipto"), "the region's map knows Egipto as Egypt"
    assert listed.named_in("Minya, Egypt, Irão") == ("Egito", "Irã")


def test_a_part_that_only_contains_a_listed_name_is_not_that_country() -> None:
    listed = SensitiveCountries.of(LISTED)

    assert listed.named_in("Indiana, United States") == ()
    assert listed.named_in("Teerã - Irã") == (), "a position is what a comma says it is"
    assert listed.named_in("") == ()


async def test_nobody_without_a_sign_in_reads_the_list(client):
    assert (await client.get(LIST)).status_code == 401
