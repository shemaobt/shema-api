"""The export and the import — BE-14's DoD, over HTTP, in every format the server writes.

The line the issue puts in bold is here as tests that **try** to get something out and fail: an
unauthorized prayer request, a row outside the caller's scope, the place, base and contacts of a
sensitive project — each through the JSON file and through the CSV, and the place through the
file its own region's coordinator exports. The import's half tries the other direction: to get a
broken record, the exported report, a reduced read or an authorization into the database through
a file — or any file at all, from somebody who is not coordination.

**Nothing here is real.** Every place, language, base, person and request is invented; a fictional
place derives to the region ``other`` (``FALLBACK_REGION``), so the accounts that write are scoped
to ``other`` and the one project in another region is only ever read.

**No test uses a platform admin to prove a refusal.** An installation admin passes every guard, so
a negative test written with one passes for the wrong reason (``conftest.py``).
"""

from __future__ import annotations

import ast
import importlib
import json
import threading
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy import Enum, String, Text, event, select

from app.db.models.shema import ShemaProject
from app.db.models.shema_audit import ShemaRecordEdit
from app.db.models.shema_enums import ShemaPrayerVisibility, ShemaRegionKey
from app.db.models.shema_eten import ShemaEtenReport
from app.db.models.shema_export import ShemaExport
from app.db.models.shema_need import ShemaNeed
from app.models.shema_privacy import LeavingShape
from app.models.shema_transfer import CSV_BOM, ExportedProject
from app.services.shema.save_project import MINTED_ID_REQUIRED, _bump_version
from tests.test_shema.conftest import PREFIX, make_shema_project
from tests.test_shema.test_prayer import need, person

EXPORT = f"{PREFIX}/export/projects"
IMPORT = f"{PREFIX}/import/projects"
WALL = f"{PREFIX}/prayer/requests"
PROJECTS = f"{PREFIX}/projects"

HOME = ShemaRegionKey.OTHER
AWAY = ShemaRegionKey.AFRICA
FORMATS = ("json", "csv")

#: FE-44 §8.4's ``ExportedProject``, the allowlist — ``notes`` is its 24th, asked of
#: ``can_export_notes`` under ``publico`` and never granted.
ALLOWLIST = frozenset(
    {
        "id",
        "languageName",
        "languageCode",
        "bridgeLanguage",
        "vitalityStatus",
        "speakerCount",
        "base",
        "location",
        "locationWithheld",
        "sensitiveCountry",
        "objective",
        "translationType",
        "status",
        "startDate",
        "deadline",
        "translatedUnits",
        "communityCheckedUnits",
        "approvedUnits",
        "totalUnits",
        "overallHealth",
        "openNeeds",
        "sharedPrayerRequests",
        "lastUpdated",
    }
)

#: What a team said nobody else may read, and what it allowed out. Long enough not to appear by
#: accident in a file that did not carry them.
KEPT = "Orem pela consulta médica que ninguém fora da coordenação deve saber"
KEPT_NEED = "Orem pela dívida do gerador que a equipe não quer que se espalhe"
SHARED = "Orem pela colheita do vale e pela saúde dos tradutores"
SHARED_NEED = "Orem pela viagem de barco até a aldeia de Pedra Clara"

#: The truth of a sensitive project — none of it may reach a file, whoever exports.
PLACE = "Vale Escondido, Serra Funda"
SECOND_LINE = "Rua do Moinho Velho"
BASE = "Base Serra Funda"
CONTACTS = ("contato.serra@exemplo.org", "lider.serra@exemplo.org", "mentor.serra@exemplo.org")
REASON = "Motivo de sensibilidade que não sai"
COORDS = (12.3456, -45.6789)

#: What no file carries, sensitive or not.
NOTE = "Nota interna que não sai em arquivo nenhum"
LEADER = "Maria Fictícia da Serra"
MENTOR = "João Imaginário do Vale"
TRANSLATORS = "Ana Inventada e Pedro Suposto"


async def seed(
    db_session,
    project_id: str,
    *,
    region: ShemaRegionKey = HOME,
    language: str | None = None,
    sensitive: bool = False,
    text: str = "",
    visibility: ShemaPrayerVisibility | None = None,
) -> ShemaProject:
    project = await make_shema_project(
        db_session, project_id=project_id, region_key=region, language_name=language
    )
    project.location = "Vale Novo, Serra Clara"
    project.team = "Base Serra Clara"
    project.bridge_language = "Português"
    project.objective = ["NT"]
    project.sensitive_country = sensitive
    project.prayer_requests = text
    project.prayer_visibility = visibility
    await db_session.commit()
    return project


#: The four personas, by the name a parametrised test asks for.
PERSONAS: dict[str, tuple[str, tuple[ShemaRegionKey, ...]]] = {
    "strategist": ("globalStrategist", ()),
    "coordinator": ("coordinator", (HOME,)),
    "lab": ("obtLab", (HOME,)),
    "circle": ("resourceCircle", (HOME,)),
}


async def persona(db_session, shema_app, name: str) -> dict[str, str]:
    role_key, regions = PERSONAS[name]
    return await person(db_session, shema_app, role_key, regions=regions)


@pytest.fixture()
async def strategist(db_session, shema_app):
    return await person(db_session, shema_app, "globalStrategist", regions=())


@pytest.fixture()
async def coordinator(db_session, shema_app):
    return await person(db_session, shema_app, "coordinator")


@pytest.fixture()
async def lab(db_session, shema_app):
    return await person(db_session, shema_app, "obtLab")


@pytest.fixture()
async def circle(db_session, shema_app):
    return await person(db_session, shema_app, "resourceCircle")


@pytest.fixture()
async def sensitive(db_session) -> ShemaProject:
    """A project in a sensitive place, in the region the writers are scoped to, with everything
    the rule withholds filled in."""
    project = await seed(db_session, "serra-funda", language="Língua Serrana", sensitive=True)
    project.location = PLACE
    project.location2 = SECOND_LINE
    project.team = BASE
    project.team_contact, project.team_leader_contact, project.mentor_contact = CONTACTS
    project.sensitivity = REASON
    project.latitude, project.longitude = COORDS
    await db_session.commit()
    return project


@pytest.fixture()
async def mixed(db_session):
    """One project whose request is kept and one whose request is shared, each with a need of
    the other kind — every combination the consent gate has to tell apart."""
    kept = await seed(
        db_session, "aurora-vale", text=KEPT, visibility=ShemaPrayerVisibility.COORDENACAO
    )
    shared = await seed(
        db_session, "brisa-serra", text=SHARED, visibility=ShemaPrayerVisibility.REDE
    )
    await need(db_session, kept, KEPT_NEED, shared=False)
    await need(db_session, shared, SHARED_NEED, shared=True)
    return kept, shared


async def export(client, headers, fmt: str = "json", **params: str) -> httpx.Response:
    response = await client.get(EXPORT, params={"format": fmt, **params}, headers=headers)
    assert response.status_code == 200, response.text
    return response


def document(response: httpx.Response) -> dict[str, Any]:
    return json.loads(response.content.decode("utf-8"))


def csv_lines(response: httpx.Response) -> list[str]:
    text = response.content.decode("utf-8")
    assert text.startswith(CSV_BOM)
    return text.removeprefix(CSV_BOM).split("\r\n")


def csv_preamble(response: httpx.Response) -> list[str]:
    lines = csv_lines(response)
    return lines[: lines.index("")]


def text_of(response: httpx.Response) -> str:
    return response.content.decode("utf-8")


def test_the_export_row_is_the_allowlist_and_a_leaving_shape() -> None:
    row = ExportedProject(id="-").as_row()

    assert issubclass(ExportedProject, LeavingShape)
    assert set(row) == ALLOWLIST
    assert set(ExportedProject(id="-", exported_notes="n").as_row()) == ALLOWLIST | {"notes"}


def _marked_columns() -> list[str]:
    """Every text column of ``shema_projects`` that is not an enum, a key or a foreign key."""
    return [
        column.name
        for column in ShemaProject.__table__.columns
        if isinstance(column.type, String | Text)
        and not isinstance(column.type, Enum)
        and not column.primary_key
        and not column.foreign_keys
    ]


#: The text columns the allowlist reads, by the wire name the file carries them under.
ALLOWED_COLUMNS = {
    "language_name",
    "language_code",
    "bridge_language",
    "vitality_status",
    "speaker_count",
    "location",
    "team",
}


@pytest.mark.parametrize("fmt", FORMATS)
async def test_a_column_the_allowlist_does_not_name_never_reaches_the_file(
    client, db_session, strategist, fmt
) -> None:
    """*A field added to* ``Project`` *later stays out of the file until somebody puts it in.*

    Every text column of the table — today's and whichever one is added next — is filled with a
    marker, on a project that is **not** sensitive, so nothing is withheld for the place's sake:
    what reaches the file is exactly what the allowlist declares.
    """
    project = await seed(db_session, "marcado-todo")
    for column in _marked_columns():
        setattr(project, column, f"<{column}>")
    project.financial_resources = ["<financial_resources>"]
    project.book_progress = [{"id": "GEN", "name": "<book_progress>"}]
    project.phases = [{"label": "<phases>", "scope": "", "date": ""}]
    project.source = {"prayerRequests": "<source>"}
    project.prayer_visibility = ShemaPrayerVisibility.COORDENACAO
    await db_session.commit()

    body = text_of(await export(client, strategist, fmt))

    present = {column for column in _marked_columns() if f"<{column}>" in body}
    assert present == ALLOWED_COLUMNS
    for marker in ("financial_resources", "book_progress", "phases", "source"):
        assert f"<{marker}>" not in body


def test_the_export_reads_through_the_listing_the_boundary_and_the_consent_gate() -> None:
    """One code path, as a property of the tree: the scope is the listing's query, the rows are
    the leaving shape, the requests are the gate's, and nothing selects the table itself."""
    source = Path(__file__).resolve().parents[2] / "app/services/shema/export_projects.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    attributes = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    selected = {
        inner.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "select"
        for inner in ast.walk(node)
        if isinstance(inner, ast.Name)
    }

    assert {"list_projects", "authorized_requests_by_project", "ExportedProject"} <= names
    assert {"withheld_note", "can_export_notes"} <= names
    assert "ShemaProject" not in selected
    assert "read_by" not in attributes


@pytest.mark.parametrize("fmt", FORMATS)
async def test_an_unauthorized_request_never_reaches_the_file(
    client, strategist, mixed, fmt
) -> None:
    body = text_of(await export(client, strategist, fmt))

    assert SHARED in body and SHARED_NEED in body
    assert KEPT not in body and KEPT_NEED not in body


@pytest.mark.parametrize("fmt", FORMATS)
async def test_a_row_outside_the_scope_never_reaches_the_file(
    client, db_session, coordinator, fmt
) -> None:
    await seed(db_session, "perto-daqui", language="Língua Vizinha")
    await seed(
        db_session,
        "longe-dali",
        region=AWAY,
        language="Língua Distante do Outro Lado",
        text=SHARED,
        visibility=ShemaPrayerVisibility.REDE,
    )

    body = text_of(await export(client, coordinator, fmt))

    assert "perto-daqui" in body
    assert "longe-dali" not in body
    assert "Língua Distante do Outro Lado" not in body
    assert SHARED not in body


async def pending(db_session, project_id: str) -> ShemaProject:
    """A project the mesa's approval filed and the Admin has not confirmed (OBT-547), in the
    region the writers reach — with a request that would otherwise be on the wall."""
    project = await seed(
        db_session,
        project_id,
        language="Língua Ainda Não Confirmada",
        text=SHARED,
        visibility=ShemaPrayerVisibility.REDE,
    )
    project.pending_confirmation = True
    await db_session.commit()
    return project


@pytest.mark.parametrize("fmt", FORMATS)
@pytest.mark.parametrize("role", ["strategist", "coordinator"])
async def test_a_pending_project_never_reaches_the_file(
    client, db_session, shema_app, role, fmt
) -> None:
    """OBT-547's *pendente invisível nos exports*, by the scope and not by a filter of the
    export's own: the file starts where every reader starts, and the pending project is not
    there — nor its request, nor in the log of what left."""
    headers = await persona(db_session, shema_app, role)
    await seed(db_session, "vale-registrado")
    await pending(db_session, "1e19f041-2c6a-5a50-a0eb-62ad40ea87b7")

    body = text_of(await export(client, headers, fmt))

    assert "vale-registrado" in body
    assert "1e19f041-2c6a-5a50-a0eb-62ad40ea87b7" not in body
    assert "Língua Ainda Não Confirmada" not in body
    assert SHARED not in body
    (entry,) = (await db_session.execute(select(ShemaExport))).scalars().all()
    assert entry.project_ids == ["vale-registrado"]
    assert entry.request_ids == []


@pytest.mark.parametrize("fmt", FORMATS)
@pytest.mark.parametrize("role", list(PERSONAS))
async def test_a_sensitive_place_base_and_contacts_never_reach_the_file(
    client, db_session, shema_app, sensitive, fmt, role
) -> None:
    """The region's own coordinator included: a file is ``outside``, whoever made it."""
    body = text_of(await export(client, await persona(db_session, shema_app, role), fmt))

    for truth in (PLACE, "Serra Funda", SECOND_LINE, BASE, REASON, *CONTACTS):
        assert truth not in body
    for number in COORDS:
        assert str(number) not in body
    assert "serra-funda" in body


async def test_a_withheld_row_carries_its_own_region_and_says_so(
    client, db_session, strategist
) -> None:
    """In a region that is not the fallback, so a file that named ``other`` for every withheld
    row — the region a shape falls back to when it cannot say — would fail here."""
    project = await seed(db_session, "longe-sigiloso", region=AWAY, sensitive=True)
    project.location = PLACE
    project.team = BASE
    await db_session.commit()

    (row,) = document(await export(client, strategist))["projects"]

    assert row["location"] == AWAY.value
    assert row["base"] == ""
    assert row["locationWithheld"] is True
    assert row["sensitiveCountry"] is True


@pytest.mark.parametrize("fmt", FORMATS)
async def test_notes_people_and_money_never_reach_the_file(
    client, db_session, strategist, fmt
) -> None:
    """Not in the allowlist at all — and the money is BE-08's case of the same test: an amount
    against a named project is the combination the sensitive-country rule exists for."""
    project = await seed(db_session, "vale-das-notas", sensitive=True)
    project.notes = NOTE
    project.team_leader = LEADER
    project.mentor = MENTOR
    project.translators = TRANSLATORS
    project.team_contact = CONTACTS[0]
    project.financial_notes = "Nota de finanças que não sai"
    await db_session.commit()
    row = await need(db_session, project, SHARED_NEED, shared=True)
    row.estimated_value = "cerca de 98.765, se a segunda aldeia entrar"
    row.estimated_amount = Decimal("98765.43")
    row.estimated_currency = "BRL"
    await db_session.commit()

    body = text_of(await export(client, strategist, fmt))

    for private in (NOTE, LEADER, MENTOR, TRANSLATORS, CONTACTS[0], "Nota de finanças"):
        assert private not in body
    assert "98765" not in body and "98.765" not in body and "BRL" not in body
    assert SHARED_NEED in body
    if fmt == "json":
        (row,) = document(await export(client, strategist))["projects"]
        assert "notes" not in row


async def test_every_json_file_opens_with_its_provenance(client, db_session, coordinator) -> None:
    await seed(db_session, "vale-da-origem")

    response = await export(client, coordinator)
    meta = document(response)["meta"]

    assert meta["contains"].startswith("Projetos do Ecossistema Shemá")
    assert meta["confidential"].startswith("Confidencial")
    assert meta["generatedBy"] == "Test User"
    assert meta["generatedAt"].endswith("Z")
    assert meta["scope"] == [HOME.value]
    assert meta["format"] == "json"
    assert meta["projectCount"] == 1
    assert meta["exportId"]
    assert response.headers["content-type"].startswith("application/json")
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["content-disposition"].startswith(
        'attachment; filename="shema-projetos-'
    )
    assert response.headers["content-disposition"].endswith('.json"')


async def test_every_csv_file_opens_with_its_provenance(client, db_session, strategist) -> None:
    await seed(db_session, "vale-da-origem")

    response = await export(client, strategist, "csv")
    preamble = csv_preamble(response)

    assert preamble[0].startswith("Projetos do Ecossistema Shemá")
    assert preamble[1].startswith("Gerado em ") and preamble[1].endswith(" UTC por Test User")
    assert preamble[2] == "Escopo: todas as regiões"
    assert preamble[3].startswith("Confidencial")
    assert preamble[4].startswith("Registro deste arquivo: ")
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["content-disposition"].endswith('.csv"')


async def test_an_empty_scope_exports_a_file_that_still_says_what_it_is(
    client, db_session, shema_app
) -> None:
    """A regional role with no region reaches nothing, and its file says so — headed, logged."""
    await seed(db_session, "vale-inalcancavel")
    nobody = await person(db_session, shema_app, "coordinator", regions=())

    exported = document(await export(client, nobody))
    lines = csv_lines(await export(client, nobody, "csv"))

    assert exported["projects"] == []
    assert exported["meta"]["projectCount"] == 0
    assert exported["meta"]["scope"] == []
    assert "vale-inalcancavel" not in json.dumps(exported) + "".join(lines)
    assert lines[lines.index("") + 1].startswith("ID;")
    assert len((await db_session.execute(select(ShemaExport))).scalars().all()) == 2


async def test_the_header_speaks_the_language_asked_for(client, db_session, strategist) -> None:
    await seed(db_session, "vale-da-lingua")

    preamble = csv_preamble(await export(client, strategist, "csv", lang="en"))
    meta = document(await export(client, strategist, lang="en"))["meta"]

    assert preamble[0].startswith("Shemá Ecosystem projects")
    assert preamble[2] == "Scope: every region"
    assert meta["confidential"].startswith("Confidential")


async def _two_withheld_and_one_clear(db_session) -> None:
    for project_id in ("sigilo-um", "sigilo-dois"):
        await seed(db_session, project_id, sensitive=True)
    await seed(db_session, "aberto-tres")


@pytest.mark.parametrize("role", ["strategist", "coordinator"])
async def test_coordination_is_told_how_many_were_withheld(
    client, db_session, shema_app, role
) -> None:
    await _two_withheld_and_one_clear(db_session)
    headers = await persona(db_session, shema_app, role)

    meta = document(await export(client, headers))["meta"]
    preamble = csv_preamble(await export(client, headers, "csv"))

    assert meta["locationsWithheld"] == 2
    assert meta["withheldNote"].startswith("2 projetos em países sensíveis")
    assert meta["withheldNote"] in preamble


@pytest.mark.parametrize("role", ["lab", "circle"])
async def test_nobody_else_is_told_anything_was_withheld(
    client, db_session, shema_app, role
) -> None:
    """GATE-04 decided the notice, not the bit: the rows still say they were withheld."""
    await _two_withheld_and_one_clear(db_session)
    headers = await persona(db_session, shema_app, role)

    exported = document(await export(client, headers))
    preamble = csv_preamble(await export(client, headers, "csv"))

    assert exported["meta"]["locationsWithheld"] is None
    assert exported["meta"]["withheldNote"] is None
    assert not any("recolhid" in line or "sensíve" in line for line in preamble)
    assert sum(row["locationWithheld"] for row in exported["projects"]) == 2


async def test_a_file_with_nothing_withheld_says_nothing_about_withholding(
    client, db_session, strategist
) -> None:
    """Not a line saying zero: *0 withheld* on every file is a sentence about nothing."""
    await seed(db_session, "aberto-so")

    meta = document(await export(client, strategist))["meta"]
    preamble = csv_preamble(await export(client, strategist, "csv"))

    assert meta["locationsWithheld"] is None and meta["withheldNote"] is None
    assert len(preamble) == 5


async def test_the_csv_neutralises_formulas_and_keeps_the_separator_inside_quotes(
    client, db_session, strategist
) -> None:
    project = await seed(
        db_session,
        "formula-vale",
        text="=HIPERLINK(1); e mais",
        visibility=ShemaPrayerVisibility.REDE,
    )
    project.language_name = '+Língua "Aspas"'
    await db_session.commit()

    lines = csv_lines(await export(client, strategist, "csv"))
    row = next(line for line in lines if line.startswith("formula-vale;"))

    assert '"\'+Língua ""Aspas"""' in row
    assert '"\'=HIPERLINK(1); e mais"' in row


async def test_every_export_is_logged_with_who_when_scope_and_what(
    client, db_session, coordinator, mixed, sensitive
) -> None:
    exported = document(await export(client, coordinator))
    meta = exported["meta"]
    kept, shared = mixed

    (entry,) = (await db_session.execute(select(ShemaExport))).scalars().all()

    assert entry.id == meta["exportId"]
    assert entry.exported_by_name == "Test User"
    assert entry.scope_key == HOME.value
    assert entry.format == "json"
    assert entry.created_at.isoformat().replace("+00:00", "Z") == meta["generatedAt"]
    assert entry.project_count == 3
    assert entry.withheld_count == 1
    assert sorted(entry.project_ids) == sorted([kept.id, shared.id, sensitive.id])
    assert all(request.startswith(shared.id) for request in entry.request_ids)
    assert len(entry.request_ids) == 2
    recorded = json.dumps([entry.project_ids, entry.request_ids], ensure_ascii=False)
    assert SHARED not in recorded and KEPT not in recorded


async def test_the_export_log_cannot_be_edited(client, db_session, strategist) -> None:
    await seed(db_session, "vale-do-registro")
    await export(client, strategist)
    (entry,) = (await db_session.execute(select(ShemaExport))).scalars().all()

    entry.project_count = 0
    with pytest.raises(Exception, match="append-only"):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.parametrize(
    ("role_key", "regions", "key"),
    [("globalStrategist", (), "global"), ("coordinator", (HOME, AWAY), "africa,other")],
    ids=["global", "two regions"],
)
async def test_the_export_log_and_the_eten_log_file_a_scope_under_one_key(
    client, db_session, shema_app, role_key, regions, key
) -> None:
    """The join an after-the-fact question makes — which reports and which files did this scope
    produce — holds only while the two logs spell a scope the same way."""
    headers = await person(db_session, shema_app, role_key, regions=regions)
    await seed(db_session, "vale-das-contas")
    await export(client, headers)
    report = await client.get(f"{PREFIX}/eten/report", params={"year": 2026}, headers=headers)
    assert report.status_code == 200, report.text

    exported = (await db_session.execute(select(ShemaExport.scope_key))).scalar_one()
    reported = (await db_session.execute(select(ShemaEtenReport.scope_key))).scalar_one()
    assert exported == reported == key


async def test_the_export_does_not_grow_its_queries_with_the_collection(
    client, db_session, test_engine, strategist
) -> None:
    """Statements, not milliseconds — ``test_projects.py``'s argument for the Projetos screen.

    A query per project under the file is the failure that would make a large export slow; the
    count is taken over five projects and over sixty-five, each with a shared request and a
    shared need, and it has to be the same.
    """
    statements: list[str] = []

    def record(conn, cursor, statement, parameters, context, executemany) -> None:
        statements.append(statement)

    async def seed_many(first: int, last: int) -> None:
        for number in range(first, last):
            project = await seed(
                db_session,
                f"vale-{number:03d}",
                text=f"{SHARED} {number}",
                visibility=ShemaPrayerVisibility.REDE,
            )
            await need(db_session, project, f"{SHARED_NEED} {number}", shared=True)

    async def count(fmt: str) -> int:
        statements.clear()
        event.listen(test_engine.sync_engine, "before_cursor_execute", record)
        try:
            await export(client, strategist, fmt)
        finally:
            event.remove(test_engine.sync_engine, "before_cursor_execute", record)
        return len(statements)

    await seed_many(0, 5)
    await export(client, strategist)
    small = {fmt: await count(fmt) for fmt in FORMATS}

    await seed_many(5, 65)
    large = {fmt: await count(fmt) for fmt in FORMATS}

    assert small == large
    assert all(value <= 10 for value in large.values()), large


def new_record(project_id: str, **fields: Any) -> dict[str, Any]:
    return {
        "id": project_id,
        "languageName": "Língua Chegada",
        "bridgeLanguage": "Português",
        "team": "Base Chegada",
        "objective": ["NT"],
        "location": "Vale Novo, Serra Clara",
        **fields,
    }


async def upload(client, headers, payload: Any) -> httpx.Response:
    content = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
    return await client.post(
        IMPORT, content=content, headers={**headers, "Content-Type": "application/json"}
    )


async def stored(db_session, project_id: str) -> ShemaProject | None:
    """The row as the database holds it now — the request shares this session."""
    stmt = (
        select(ShemaProject)
        .where(ShemaProject.id == project_id)
        .execution_options(populate_existing=True)
    )
    return (await db_session.execute(stmt)).scalar_one_or_none()


def refusal(response: httpx.Response, key: str) -> dict[str, Any]:
    assert response.status_code == 400, response.text
    body = response.json()
    assert body["key"] == key
    assert body["code"] == "BAD_REQUEST"
    return body


@pytest.mark.parametrize(
    "raw",
    [b"{nao e json", b"[NaN]", b"[1e400]", b"\xff\xfe", b"[" * 100_000 + b"]" * 100_000],
    ids=["broken", "NaN", "overflow", "not utf-8", "nested too deep"],
)
async def test_a_file_that_is_not_json_is_refused(client, coordinator, raw) -> None:
    """Including the inputs the reader itself chokes on — a refusal, never a 500."""
    refusal(await upload(client, coordinator, raw), "import_invalid_json")


async def test_an_empty_list_applies_nothing(client, db_session, coordinator) -> None:
    response = await upload(client, coordinator, [])

    assert response.status_code == 200, response.text
    assert response.json() == {"applied": 0, "ignoredFields": []}


async def test_a_file_that_is_not_a_list_is_refused(client, coordinator) -> None:
    refusal(await upload(client, coordinator, {"id": "sozinho"}), "import_not_list")


async def test_a_broken_record_refuses_the_whole_file_with_its_index(
    client, db_session, coordinator
) -> None:
    """By vocabulary, not by type: ``banana`` is a string and is not a status."""
    response = await upload(
        client,
        coordinator,
        [
            new_record("9d7f6424-9e4d-5c07-a972-e25bfb8590b8"),
            new_record("39c2ab35-4905-56a7-b825-17d2d783a09d", status="banana"),
        ],
    )

    body = refusal(response, "import_bad_record")
    assert body["index"] == 2
    assert ["status"] in [error["loc"] for error in body["errors"]]
    assert "banana" not in response.text
    assert await stored(db_session, "9d7f6424-9e4d-5c07-a972-e25bfb8590b8") is None


@pytest.mark.parametrize(
    "broken",
    [
        7,
        {"id": "sem-nome", "bridgeLanguage": "Português"},
        {**new_record("3eea1493-f769-57a2-97bd-19980473d7ea"), "campoQueNaoExiste": 1},
        {**new_record("06b7ee36-cbe4-54d0-ad75-88ffd1ef9e08"), "startDate": "31/12/2026"},
        {**new_record("f2ad579e-752f-540a-a337-f64fa3d3c524"), "coords": [1, "norte"]},
    ],
    ids=["not an object", "the four missing", "outside the contract", "a date", "coordinates"],
)
async def test_a_record_the_write_would_refuse_refuses_the_file(
    client, db_session, coordinator, broken
) -> None:
    response = await upload(
        client, coordinator, [new_record("9d7f6424-9e4d-5c07-a972-e25bfb8590b8"), broken]
    )

    assert refusal(response, "import_bad_record")["index"] == 2
    assert await stored(db_session, "9d7f6424-9e4d-5c07-a972-e25bfb8590b8") is None


async def test_a_duplicate_id_refuses_the_file(client, db_session, coordinator) -> None:
    response = await upload(
        client,
        coordinator,
        [
            new_record("d96e07b4-ea06-5d79-982b-5cc175bf900a"),
            new_record("d96e07b4-ea06-5d79-982b-5cc175bf900a", notes="outra"),
        ],
    )

    assert refusal(response, "import_duplicate_id")["id"] == "d96e07b4-ea06-5d79-982b-5cc175bf900a"
    assert await stored(db_session, "d96e07b4-ea06-5d79-982b-5cc175bf900a") is None


@pytest.mark.parametrize("kind", ["json", "csv", "rows", "a reduced record"])
async def test_the_exported_file_is_recognised_and_refused(
    client, db_session, coordinator, lab, sensitive, kind
) -> None:
    """By what the file holds, not by its name: the report, a row of it, or a payload that says
    it was reduced — importing any of them would overwrite the truth with the reduction."""
    if kind == "json":
        payload: Any = (await export(client, coordinator)).content
    elif kind == "csv":
        payload = (await export(client, coordinator, "csv")).content
    elif kind == "rows":
        payload = document(await export(client, coordinator))["projects"]
    else:
        read = await client.get(f"{PROJECTS}/{sensitive.id}", headers=lab)
        assert read.json()["readAs"] == "other"
        payload = [read.json()]

    refusal(await upload(client, coordinator, payload), "import_is_export")
    assert (await stored(db_session, sensitive.id)).location == PLACE


async def test_a_record_read_outside_the_prayer_audience_cannot_clear_its_request(
    client, db_session, coordinator, circle, mixed
) -> None:
    """Nothing of this record is withheld, and the Resource Circle's read of it is still a
    reduction: a request nobody authorized reads as ``""``. Imported, it would clear the request;
    the payload says it was not read for coordination, and that is enough to refuse it."""
    kept, _shared = mixed
    read = (await client.get(f"{PROJECTS}/{kept.id}", headers=circle)).json()
    assert (read["readAs"], read["locationWithheld"], read["prayerRequests"]) == (
        "other",
        False,
        "",
    )

    refusal(await upload(client, coordinator, [read]), "import_is_export")
    assert (await stored(db_session, kept.id)).prayer_requests == KEPT


@pytest.mark.parametrize("role", ["strategist", "coordinator"])
async def test_coordination_imports(client, db_session, shema_app, role) -> None:
    headers = await persona(db_session, shema_app, role)

    response = await upload(client, headers, [new_record("248d6309-da1a-515f-90e4-8a02b6cfc6ad")])

    assert response.status_code == 200, response.text
    assert await stored(db_session, "248d6309-da1a-515f-90e4-8a02b6cfc6ad") is not None


@pytest.mark.parametrize("role", ["lab", "circle"])
async def test_nobody_else_imports(client, db_session, shema_app, role) -> None:
    """Refused at the door, whatever the file holds — a record coordination could apply, or
    bytes that are not even JSON: the grant is answered before the file is looked at."""
    headers = await persona(db_session, shema_app, role)

    response = await upload(client, headers, [new_record("248d6309-da1a-515f-90e4-8a02b6cfc6ad")])

    assert response.status_code == 403, response.text
    assert response.json()["detail"].startswith("Projects are imported by the coordination")
    assert await stored(db_session, "248d6309-da1a-515f-90e4-8a02b6cfc6ad") is None
    assert (await upload(client, headers, b"{nao e json")).status_code == 403


async def test_the_file_is_read_off_the_event_loop(client, coordinator, monkeypatch) -> None:
    """Reading and checking the file grows with it, so it runs where the export's rows run."""
    module = importlib.import_module("app.services.shema.import_projects")
    read_import = module.read_import
    readers: list[int] = []

    def watched(raw: bytes) -> Any:
        readers.append(threading.get_ident())
        return read_import(raw)

    monkeypatch.setattr(module, "read_import", watched)
    response = await upload(
        client, coordinator, [new_record("7a467698-47bb-54a5-b03d-1aa2040ff99c")]
    )

    assert response.status_code == 200, response.text
    assert readers and threading.get_ident() not in readers


async def test_the_import_creates_and_updates_inside_the_scope(
    client, db_session, coordinator
) -> None:
    existing = await seed(db_session, "vale-antigo")

    response = await upload(
        client,
        coordinator,
        [
            new_record(existing.id, languageName="Língua Antiga", statusComments="revisto"),
            new_record("73513053-a3df-525b-9c9f-dc33980799fe"),
        ],
    )

    assert response.status_code == 200, response.text
    assert response.json()["applied"] == 2
    updated = await stored(db_session, existing.id)
    assert updated.status_comments == "revisto"
    assert updated.version == 2
    created = await stored(db_session, "73513053-a3df-525b-9c9f-dc33980799fe")
    assert created is not None and created.region_key == HOME
    authors = (
        await db_session.execute(
            select(ShemaRecordEdit.changed_by_name).where(ShemaRecordEdit.project_id == existing.id)
        )
    ).scalars()
    assert set(authors) == {"Test User"}


async def test_a_record_as_the_console_reads_it_goes_back_with_what_the_server_owns_ignored(
    client, db_session, coordinator
) -> None:
    project = await seed(db_session, "vale-de-volta")
    read = (await client.get(f"{PROJECTS}/{project.id}", headers=coordinator)).json()
    read["statusComments"] = "voltou pelo arquivo"

    response = await upload(client, coordinator, [read])

    assert response.status_code == 200, response.text
    ignored = set(response.json()["ignoredFields"])
    assert {"derived", "readAs", "locationWithheld", "progressHistory", "healthHistory"} <= ignored
    assert {"regionalCoordinator", "prayerVisibility", "completedDate"} <= ignored
    assert (await stored(db_session, project.id)).status_comments == "voltou pelo arquivo"


async def test_a_refusal_while_applying_leaves_nothing_behind(
    client, db_session, coordinator
) -> None:
    """The second record passes the file's check and is refused by the write path — a deadline
    before the start the row already holds — and the first, already flushed, goes with it: one
    commit or none."""
    existing = await seed(db_session, "vale-firme")
    existing.start_date = date(2026, 6, 1)
    await db_session.commit()

    response = await upload(
        client,
        coordinator,
        [
            new_record("e47d7b9f-1944-509c-a7be-f96419afcc1c"),
            new_record(existing.id, deadline="2026-01-01"),
        ],
    )

    assert response.status_code == 400, response.text
    assert response.json()["detail"].startswith("item 2 (vale-firme): deadline")
    assert await stored(db_session, "e47d7b9f-1944-509c-a7be-f96419afcc1c") is None
    assert (await stored(db_session, "vale-firme")).deadline is None


async def test_a_record_saved_meanwhile_refuses_the_file_with_who_changed_what(
    client, db_session, coordinator, monkeypatch
) -> None:
    """The version guard through the import: a save lands between the import's read and its
    write, and the answer is the record screen's own 409 — the version conflict with what it
    carries, the item named — not a bare conflict the console could only meet with a reload."""
    module = importlib.import_module("app.services.shema.import_projects")
    save_project = module.save_project
    existing = await seed(db_session, "vale-disputado")

    async def saved_meanwhile(db, scope, project_id, payload, **kwargs: Any) -> Any:
        project = await db.get(ShemaProject, project_id)
        assert await _bump_version(db, project, kwargs["expected_version"]) is not None
        return await save_project(db, scope, project_id, payload, **kwargs)

    monkeypatch.setattr(module, "save_project", saved_meanwhile)
    response = await upload(
        client,
        coordinator,
        [
            new_record("e47d7b9f-1944-509c-a7be-f96419afcc1c"),
            new_record(existing.id, statusComments="pelo arquivo"),
        ],
    )

    assert response.status_code == 409, response.text
    body = response.json()
    assert body["detail"].startswith("item 2 (vale-disputado): ")
    assert (body["expectedVersion"], body["currentVersion"]) == (1, 2)
    assert {"changedFields", "changedBy", "changedAt"} <= body.keys()
    assert await stored(db_session, "e47d7b9f-1944-509c-a7be-f96419afcc1c") is None
    assert (await stored(db_session, "vale-disputado")).status_comments != "pelo arquivo"


async def test_a_slug_that_exists_out_of_reach_refuses_the_file(
    client, db_session, coordinator
) -> None:
    await seed(db_session, "d23e9eca-0785-5afc-8d28-d4e99261de3d", region=AWAY)

    response = await upload(
        client,
        coordinator,
        [
            new_record("e47d7b9f-1944-509c-a7be-f96419afcc1c"),
            new_record("d23e9eca-0785-5afc-8d28-d4e99261de3d"),
        ],
    )

    assert response.status_code == 409, response.text
    assert await stored(db_session, "e47d7b9f-1944-509c-a7be-f96419afcc1c") is None
    assert (await stored(db_session, "d23e9eca-0785-5afc-8d28-d4e99261de3d")).region_key == AWAY


async def test_the_import_cannot_reach_a_pending_project(client, db_session, coordinator) -> None:
    """The import does not see a pending project either, so it cannot confirm, fill or correct
    one through a file — that is the Admin's act on the project. Its id reads as a new record,
    and the create finds the slug taken: the file is refused and nothing of it applied."""
    await pending(db_session, "1e19f041-2c6a-5a50-a0eb-62ad40ea87b7")

    response = await upload(
        client,
        coordinator,
        [
            new_record("e47d7b9f-1944-509c-a7be-f96419afcc1c"),
            new_record("1e19f041-2c6a-5a50-a0eb-62ad40ea87b7", statusComments="x"),
        ],
    )

    assert response.status_code == 409, response.text
    assert await stored(db_session, "e47d7b9f-1944-509c-a7be-f96419afcc1c") is None
    kept = await stored(db_session, "1e19f041-2c6a-5a50-a0eb-62ad40ea87b7")
    assert kept.pending_confirmation is True
    assert kept.status_comments == ""
    assert kept.version == 1


async def test_an_imported_request_arrives_unauthorized_whatever_the_file_claims(
    client, db_session, coordinator, circle
) -> None:
    claimed = "Orem por este pedido que o arquivo diz estar autorizado"

    response = await upload(
        client,
        coordinator,
        [
            new_record(
                "651694b6-9108-5448-96b3-1ef87eebdf36",
                prayerRequests=claimed,
                prayerVisibility="rede",
            )
        ],
    )

    assert response.status_code == 200, response.text
    assert "prayerVisibility" in response.json()["ignoredFields"]
    assert (
        await stored(db_session, "651694b6-9108-5448-96b3-1ef87eebdf36")
    ).prayer_visibility is None
    wall = await client.get(WALL, headers=circle)
    assert claimed not in wall.text
    for fmt in FORMATS:
        assert claimed not in text_of(await export(client, coordinator, fmt))


async def test_an_imported_need_arrives_unshared_and_unseen(
    client, db_session, coordinator
) -> None:
    need_text = "Orem pela ponte que o arquivo diz estar compartilhada"

    response = await upload(
        client,
        coordinator,
        [
            new_record(
                "c9f52ae0-4849-5db6-a6f1-7e7526deab92",
                needsItems=[
                    {
                        "category": "financial",
                        "description": need_text,
                        "prayerShared": True,
                        "acknowledged": True,
                    }
                ],
            )
        ],
    )

    assert response.status_code == 200, response.text
    ignored = set(response.json()["ignoredFields"])
    assert {"needsItems[].prayerShared", "needsItems[].acknowledged"} <= ignored
    (row,) = (
        await db_session.execute(
            select(ShemaNeed).where(ShemaNeed.project_id == "c9f52ae0-4849-5db6-a6f1-7e7526deab92")
        )
    ).scalars()
    assert row.prayer_shared is False
    assert row.acknowledged_at is None
    assert need_text not in text_of(await export(client, coordinator))


async def test_the_file_can_neither_publish_nor_withdraw_a_request(
    client, db_session, coordinator, mixed
) -> None:
    """The same text keeps the organisation's decision, whatever the file says about it; a new
    text is a new request, and it arrives unauthorized."""
    kept, shared = mixed

    response = await upload(
        client,
        coordinator,
        [
            new_record(kept.id, prayerRequests=KEPT, prayerVisibility="rede"),
            new_record(shared.id, prayerRequests=SHARED, prayerVisibility="coordenacao"),
        ],
    )
    assert response.status_code == 200, response.text
    assert (
        await stored(db_session, kept.id)
    ).prayer_visibility == ShemaPrayerVisibility.COORDENACAO
    assert (await stored(db_session, shared.id)).prayer_visibility == ShemaPrayerVisibility.REDE

    changed = "Orem por um pedido novo que chegou pelo arquivo"
    response = await upload(client, coordinator, [new_record(shared.id, prayerRequests=changed)])
    assert response.status_code == 200, response.text
    assert (await stored(db_session, shared.id)).prayer_visibility is None
    assert changed not in text_of(await export(client, coordinator))


async def test_the_import_never_lowers_the_sensitive_flag(
    client, db_session, coordinator, sensitive
) -> None:
    clear = await seed(db_session, "vale-claro")

    response = await upload(
        client,
        coordinator,
        [
            new_record(sensitive.id, location=PLACE, sensitiveCountry=False, statusComments="x"),
            new_record(clear.id, sensitiveCountry=True),
        ],
    )

    assert response.status_code == 200, response.text
    assert "sensitiveCountry" in response.json()["ignoredFields"]
    kept = await stored(db_session, sensitive.id)
    assert kept.sensitive_country is True
    assert kept.status_comments == "x"
    assert (await stored(db_session, clear.id)).sensitive_country is True


@pytest.mark.parametrize("exists", [True, False])
async def test_a_slug_the_importer_does_not_reach_is_refused_the_same_whether_it_exists(
    client, db_session, coordinator, exists
) -> None:
    """OBT-551: an import file is not a way to ask whether a project exists outside the scope.

    An id the importer reaches is saved; any other id would be created, and a new record takes
    a minted UUID — so a slug in another region and a slug that never existed meet the same
    sentence, naming only the item and the id the file itself carried.
    """
    if exists:
        await seed(db_session, "vale-alheio", region=AWAY)

    response = await upload(client, coordinator, [new_record("vale-alheio")])

    assert response.status_code == 400
    assert response.json()["detail"] == f"item 1 (vale-alheio): {MINTED_ID_REQUIRED}"
