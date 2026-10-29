"""OBT-563 — a sensitive project sits where the name its reader reads puts it, not its real name.

OBT-560 gave a sensitive project a public name and printed it to everybody but coordination; the
lists kept ordering by the real one. A reader who is not coordination could then place a project
by the name withheld from it: first in a list of ties, before a name that starts with *B*.
Daniel, 2/out/2026, chose to close it — ours, not Karina's.

The canary's real name sorts **first** and its public name **last**, so any path that still
orders by the real name puts it at the top and fails here. Three paths hand out an order: the
Projetos screen (its stable sorts keep ties in arrival order), the export and the ETEN report.

**OBT-657 — and the name the reader reads is the one the console prints.** With no public name a
withheld project carries the region key, which the console prints as *Projeto sensível — África*
in Portuguese and *Sensitive project — Africa* in English; ordered by the key, the line sat before
*Afrikaans*. The second half of this file seeds names A to P and three such projects: *Purépecha*
falls between the two labels, and South America and Asia swap places between the languages, so
only an order by the printed name, in the language the console states, passes in both.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import select

from app.db.models.shema import ShemaProject
from app.db.models.shema_enums import ShemaRegionKey
from app.db.models.shema_eten import ShemaEtenReport
from app.models.shema_prayer import PulseLanguage
from app.models.shema_projects import ShemaProjectQuery
from app.models.shema_transfer import ExportFormat
from app.services.shema import (
    NO_COORDINATION,
    RegionScope,
    browse_projects,
    eten_report,
    export_projects,
    readership,
)
from app.utils.shema_printed_names import PRINTED_NAMES, VENDORED_FROM
from tests.baker import make_user
from tests.test_shema.conftest import PREFIX, auth_header, make_scoped_user

GLOBAL = RegionScope(global_=True, regions=frozenset())
COORDINATION = readership(GLOBAL, set(), platform_admin=True)
TODAY = date(2026, 10, 2)

SENSITIVE = "sigilosa"
REAL = "Aaa Sigilosa"
PUBLIC = "Zeta"
OPEN = {"aberta-b": "Bbb Aberta", "aberta-m": "Mmm Aberta"}


@pytest.fixture()
async def projects(db_session) -> None:
    rows = [
        ShemaProject(
            id=SENSITIVE,
            language_name=REAL,
            public_language_name=PUBLIC,
            sensitive_country=True,
            in_eten=True,
            bridge_language="Portugues",
            team="",
            region_key=ShemaRegionKey.OTHER,
        ),
        *(
            ShemaProject(
                id=project_id,
                language_name=name,
                in_eten=True,
                bridge_language="Portugues",
                team="",
                region_key=ShemaRegionKey.OTHER,
            )
            for project_id, name in OPEN.items()
        ),
    ]
    db_session.add_all(rows)
    await db_session.commit()


async def _screen(db_session, reading) -> list[str]:
    page = await browse_projects(
        db_session, GLOBAL, ShemaProjectQuery(), readership=reading, today=TODAY
    )
    return [card.id for card in page.items]


async def test_obt_lab_finds_the_sensitive_project_where_its_public_name_puts_it(
    db_session, projects
) -> None:
    """No project has a deadline, so the default sort is all ties: the tiebreak is the order."""
    assert await _screen(db_session, NO_COORDINATION) == ["aberta-b", "aberta-m", SENSITIVE]


async def test_coordination_still_reads_the_real_name_order(db_session, projects) -> None:
    assert await _screen(db_session, COORDINATION) == [SENSITIVE, "aberta-b", "aberta-m"]


async def test_the_name_sort_follows_the_name_the_reader_reads(db_session, projects) -> None:
    page = await browse_projects(
        db_session, GLOBAL, ShemaProjectQuery(sort="name"), readership=NO_COORDINATION, today=TODAY
    )
    assert [card.id for card in page.items] == ["aberta-b", "aberta-m", SENSITIVE]


async def test_the_export_orders_its_rows_by_the_name_it_prints(db_session, projects) -> None:
    """Every row leaves ``outside``, a coordinator's export included."""
    user = await make_user(db_session, email="exporta@ordem.test")
    exported = await export_projects(
        db_session,
        GLOBAL,
        readership=COORDINATION,
        user=user,
        file_format=ExportFormat.JSON,
        language=PulseLanguage.PT_BR,
        now=datetime(2026, 10, 2, tzinfo=UTC),
    )
    rows = json.loads(exported.body)["projects"]
    assert [row["id"] for row in rows] == ["aberta-b", "aberta-m", SENSITIVE]
    assert REAL not in exported.body


async def test_the_eten_report_orders_its_lines_by_the_name_it_prints(db_session, projects) -> None:
    """No line has credits or progress, so the name is what orders them."""
    user = await make_user(db_session, email="eten@ordem.test")
    report = await eten_report(db_session, GLOBAL, 2027, user=user, today=TODAY)
    assert [line.project_id for line in report.snapshots] == ["aberta-b", "aberta-m", SENSITIVE]


async def test_a_card_with_no_name_still_sorts_after_the_named_ones(db_session, projects) -> None:
    """``sort_key`` puts blanks last; the tiebreak must not undo it on the default sort."""
    db_session.add(
        ShemaProject(
            id="sem-nome",
            language_name="",
            bridge_language="Portugues",
            team="",
            region_key=ShemaRegionKey.OTHER,
        )
    )
    await db_session.commit()
    assert await _screen(db_session, NO_COORDINATION) == [
        "aberta-b",
        "aberta-m",
        SENSITIVE,
        "sem-nome",
    ]


AFRICA_UNNAMED = "sensivel-africa"
ASIA_UNNAMED = "sensivel-asia"
SOUTH_AMERICA_UNNAMED = "sensivel-sul"

#: Names A to P, as the DoD asks, each in Africa. *Purépecha* sorts after *Projeto sensível* and
#: before *Sensitive project*, which is what tells the two languages apart.
NAMED = {
    "aberta-afrikaans": "Afrikaans Kaaps",
    "aberta-luganda": "Luganda",
    "aberta-makua": "Makua",
    "aberta-pme": "pme-projetos-2",
    "aberta-purepecha": "Purépecha",
}

#: Withheld, no public name: each reaches everybody but coordination as its region key. The real
#: names sort first, so an order by them would show at the top.
UNNAMED = {
    AFRICA_UNNAMED: (ShemaRegionKey.AFRICA, "Aaa Real Africana"),
    ASIA_UNNAMED: (ShemaRegionKey.ASIA, "Aab Real Asiática"),
    SOUTH_AMERICA_UNNAMED: (ShemaRegionKey.SOUTH_AMERICA, "Aac Real Sulista"),
}

#: Where the printed names put them: *Projeto sensível — África · — América do Sul · — Ásia*
#: before *Purépecha*; *Sensitive project — Africa · — Asia · — South America* after it.
AS_PRINTED = {
    PulseLanguage.PT_BR: [
        "aberta-afrikaans",
        "aberta-luganda",
        "aberta-makua",
        "aberta-pme",
        AFRICA_UNNAMED,
        SOUTH_AMERICA_UNNAMED,
        ASIA_UNNAMED,
        "aberta-purepecha",
    ],
    PulseLanguage.EN: [
        "aberta-afrikaans",
        "aberta-luganda",
        "aberta-makua",
        "aberta-pme",
        "aberta-purepecha",
        AFRICA_UNNAMED,
        ASIA_UNNAMED,
        SOUTH_AMERICA_UNNAMED,
    ],
}

#: By the keys the lines carry — the order the finding saw on screen, *africa* before *Afrikaans*,
#: and the one the record keeps.
AS_CARRIED = [
    AFRICA_UNNAMED,
    "aberta-afrikaans",
    ASIA_UNNAMED,
    "aberta-luganda",
    "aberta-makua",
    "aberta-pme",
    "aberta-purepecha",
    SOUTH_AMERICA_UNNAMED,
]

BOTH_LANGUAGES = pytest.mark.parametrize("language", list(PulseLanguage), ids=str)


@pytest.fixture()
async def printed(db_session) -> None:
    rows = [
        ShemaProject(
            id=project_id,
            language_name=name,
            in_eten=True,
            bridge_language="Portugues",
            team="",
            region_key=ShemaRegionKey.AFRICA,
        )
        for project_id, name in NAMED.items()
    ]
    rows += [
        ShemaProject(
            id=project_id,
            language_name=real,
            sensitive_country=True,
            in_eten=True,
            bridge_language="Portugues",
            team="",
            region_key=region,
        )
        for project_id, (region, real) in UNNAMED.items()
    ]
    db_session.add_all(rows)
    await db_session.commit()


@BOTH_LANGUAGES
async def test_the_eten_report_puts_unnamed_sensitive_lines_where_their_printed_names_put_them(
    db_session, printed, language
) -> None:
    """No credits and no readings, so the name orders every line — as the console prints it."""
    user = await make_user(db_session, email=f"eten-{language}@impresso.test")
    report = await eten_report(db_session, GLOBAL, 2027, user=user, today=TODAY, language=language)
    assert [line.project_id for line in report.snapshots] == AS_PRINTED[language]


@BOTH_LANGUAGES
async def test_the_projects_list_puts_unnamed_sensitive_cards_where_their_printed_names_put_them(
    db_session, printed, language
) -> None:
    """For the OBT Lab, in the name order and in the default one, where every card ties."""
    for sort in ("name", "deadline"):
        page = await browse_projects(
            db_session,
            GLOBAL,
            ShemaProjectQuery(sort=sort),
            readership=NO_COORDINATION,
            today=TODAY,
            language=language,
        )
        assert [card.id for card in page.items] == AS_PRINTED[language], sort


@BOTH_LANGUAGES
async def test_coordination_reads_the_real_name_order_whatever_the_language(
    db_session, printed, language
) -> None:
    page = await browse_projects(
        db_session,
        GLOBAL,
        ShemaProjectQuery(sort="name"),
        readership=COORDINATION,
        today=TODAY,
        language=language,
    )
    assert [card.id for card in page.items] == [*UNNAMED, *NAMED]


async def test_a_report_read_in_both_languages_is_recorded_once_by_the_names_it_carries(
    db_session, printed
) -> None:
    """The record keeps the data, not the form: the reader's language reorders only the answer."""
    user = await make_user(db_session, email="eten-registro@impresso.test")
    answers = [
        await eten_report(db_session, GLOBAL, 2027, user=user, today=TODAY, language=language)
        for language in (PulseLanguage.PT_BR, PulseLanguage.EN, PulseLanguage.PT_BR)
    ]
    rows = list((await db_session.execute(select(ShemaEtenReport))).scalars())
    assert len(rows) == 1
    assert {answer.report_id for answer in answers} == {rows[0].id}
    assert [line.project_id for line in answers[1].snapshots] == AS_PRINTED[PulseLanguage.EN]
    assert [line["project_id"] for line in rows[0].content["snapshots"]] == AS_CARRIED


async def test_the_console_states_its_language_in_a_header_on_both_reads(
    client, db_session, shema_app, printed
) -> None:
    """Regional accounts, neither an admin. No header, or one that is not English, is Portuguese."""
    regions = [ShemaRegionKey.AFRICA, ShemaRegionKey.ASIA, ShemaRegionKey.SOUTH_AMERICA]
    coordinator = await make_scoped_user(
        db_session, shema_app, email="coord@impresso.test", role_key="coordinator", regions=regions
    )
    obt_lab = await make_scoped_user(
        db_session, shema_app, email="lab@impresso.test", role_key="obtLab", regions=regions
    )
    reads = (
        (f"{PREFIX}/eten/report", {"year": 2027}, coordinator, "snapshots", "projectId"),
        (f"{PREFIX}/projects", {"sort": "name"}, obt_lab, "items", "id"),
    )
    stated = (
        ({}, PulseLanguage.PT_BR),
        ({"X-Shema-Language": "en"}, PulseLanguage.EN),
        ({"X-Shema-Language": "pt-BR"}, PulseLanguage.PT_BR),
        ({"X-Shema-Language": "fr"}, PulseLanguage.PT_BR),
    )
    for path, params, user, field, key in reads:
        headers = await auth_header(db_session, user)
        for header, language in stated:
            response = await client.get(path, params=params, headers={**headers, **header})
            assert response.status_code == 200, response.text
            ids = [row[key] for row in response.json()[field]]
            assert ids == AS_PRINTED[language], (path, header)


def test_the_language_is_a_header_and_never_a_parameter_of_the_address() -> None:
    """The list's query is the screen's own address (``test_projects.py``); a language is not."""
    from app.main import create_app

    spec = create_app().openapi()
    for path in (f"{PREFIX}/projects", f"{PREFIX}/eten/report"):
        stated = {
            (parameter["name"], parameter["in"])
            for parameter in spec["paths"][path]["get"]["parameters"]
            if "lang" in parameter["name"].lower()
        }
        assert stated == {("X-Shema-Language", "header")}, path


def test_the_printed_names_cover_every_region_in_both_languages() -> None:
    """The vendored file says what the console prints for every region, in each of its languages."""
    assert len(VENDORED_FROM) == 40
    assert set(PRINTED_NAMES) == {language.value for language in PulseLanguage}
    regions = {region.value for region in ShemaRegionKey}
    for names in PRINTED_NAMES.values():
        assert set(names) == regions
        assert not regions & set(names.values())
    assert PRINTED_NAMES["pt-BR"]["africa"] == "Projeto sensível — África"
    assert PRINTED_NAMES["en"]["africa"] == "Sensitive project — Africa"
