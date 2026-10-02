"""OBT-563 — a sensitive project sits where the name its reader reads puts it, not its real name.

OBT-560 gave a sensitive project a public name and printed it to everybody but coordination; the
lists kept ordering by the real one. A reader who is not coordination could then place a project
by the name withheld from it: first in a list of ties, before a name that starts with *B*.
Daniel, 2/out/2026, chose to close it — ours, not Karina's.

The canary's real name sorts **first** and its public name **last**, so any path that still
orders by the real name puts it at the top and fails here. Three paths hand out an order: the
Projetos screen (its stable sorts keep ties in arrival order), the export and the ETEN report.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime

import pytest

from app.db.models.shema import ShemaProject
from app.db.models.shema_enums import ShemaRegionKey
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
from tests.baker import make_user

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
