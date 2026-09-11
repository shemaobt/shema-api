"""``GET /api/shema/projects`` — and the one property the whole endpoint exists to hold.

**If the sidebar says 12 Crítica and the list shows 11, people stop trusting both numbers.**
That sentence is the issue's, and :func:`test_every_facet_count_is_what_clicking_it_returns`
is it written as a test: for **every option of every group** the response reports, apply that
option as a filter and assert the number of results equals the number the count promised. It
is not a spot check of a few facets — it is the whole cross product, re-requested, and it is
what makes *one query path feeds both* a fact rather than an intention.

The rest of the file is the four DoD lines around that one: the filters compose, the
derivations match wave-1 semantics (``tests/test_shema/test_parity.py`` is the other half of
this, over all 127 real records), the region scope and the sensitive-country rule reach the
**counts** and not only the results, and the window is a window over an ordered set.

**No account here is a platform admin.** ``require_app_access`` and ``require_role`` both
return early on ``is_platform_admin``, so a scope test written with one passes for the wrong
reason and would keep passing after the scope was deleted — ``conftest.py`` says so and this
file obeys it.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pytest

from app.db.models.shema import ShemaProject
from app.db.models.shema_enums import (
    ShemaHealthLevel,
    ShemaMediaKind,
    ShemaNeedStatus,
    ShemaNeedUrgency,
    ShemaProjectStatus,
    ShemaRegionKey,
)
from app.db.models.shema_media import ShemaMediaItem
from app.db.models.shema_need import ShemaNeed
from app.db.models.shema_progress import ShemaProgressEntry
from tests.test_shema.conftest import PREFIX, auth_header, make_scoped_user

PROJECTS = f"{PREFIX}/projects"

TODAY = date.today()
LONG_AGO = TODAY - timedelta(days=400)
A_WHILE_AGO = TODAY - timedelta(days=75)
RECENTLY = TODAY - timedelta(days=5)


async def make_project(
    db_session,
    project_id: str,
    *,
    region: ShemaRegionKey = ShemaRegionKey.SOUTH_AMERICA,
    location: str = "Brazil",
    sensitive: bool = False,
    **columns: Any,
) -> ShemaProject:
    """A project row with only what a test names set, and every other column at its default.

    ``conftest.make_shema_project`` sets three columns for the scope tests; this sets whatever
    a facet test needs and no more, which is ``docs/shema.md`` §7.4's *two absences* rule: a
    fixture that fills every field hides a default that is wrong, and the dominant state of
    this table really is *nobody has said anything yet*.
    """
    project = ShemaProject(
        id=project_id,
        language_name=columns.pop("language_name", project_id),
        region_key=region,
        location=location,
        sensitive_country=sensitive,
        **columns,
    )
    db_session.add(project)
    await db_session.commit()
    return project


async def add_need(
    db_session,
    project_id: str,
    *,
    category: str = "financial",
    urgency: ShemaNeedUrgency = ShemaNeedUrgency.LOW,
    status: ShemaNeedStatus = ShemaNeedStatus.OPEN,
    prayer_shared: bool = False,
    prayer_answered: bool = False,
) -> None:
    db_session.add(
        ShemaNeed(
            project_id=project_id,
            category=category,
            urgency=urgency,
            status=status,
            prayer_shared=prayer_shared,
            prayer_answered=prayer_answered,
        )
    )
    await db_session.commit()


async def add_progress(db_session, project_id: str, when: date) -> None:
    db_session.add(ShemaProgressEntry(project_id=project_id, entry_date=when))
    await db_session.commit()


async def add_photo(db_session, project_id: str, *, caption: str = "a photo") -> None:
    db_session.add(
        ShemaMediaItem(project_id=project_id, kind=ShemaMediaKind.PHOTO, caption=caption)
    )
    await db_session.commit()


@pytest.fixture()
async def collection(db_session, shema_app):
    """Eight projects that between them light up every facet group at least twice.

    Deliberately small and deliberately varied: the cross-product test below re-requests once
    per option, so the set has to be rich enough for the counts to be interesting and small
    enough for that to stay a second. The 127 real records are exercised by
    ``test_parity.py`` and by :func:`test_the_screens_real_query_load_is_one_pass_over_the_scope`.
    """
    await make_project(
        db_session,
        "guarani-mbya",
        location="Brazil",
        status=ShemaProjectStatus.EM_ANDAMENTO,
        total_units=100,
        translated_units=40,
        objective=["NT"],
        translation_type=["OBT"],
        financial_resources=["Seed Company"],
        vitality_status="Vital",
        team="YWAM Belem",
        in_eten=True,
        health_emotional=ShemaHealthLevel.CRITICA,
        last_updated=RECENTLY,
    )
    await add_progress(db_session, "guarani-mbya", RECENTLY)
    await add_need(db_session, "guarani-mbya", category="equipment", urgency=ShemaNeedUrgency.HIGH)
    await add_photo(db_session, "guarani-mbya")

    await make_project(
        db_session,
        "kaapor",
        location="Brazil",
        status=ShemaProjectStatus.EM_ANDAMENTO,
        total_units=100,
        translated_units=80,
        objective=["NT", "AT"],
        translation_type=["OMT"],
        financial_resources=["Innovation Lab"],
        vitality_status="Vital",
        team="YWAM Belem",
        health_emotional=ShemaHealthLevel.BOA,
        health_relational=ShemaHealthLevel.ATENCAO,
    )
    await add_progress(db_session, "kaapor", A_WHILE_AGO)
    await add_need(
        db_session,
        "kaapor",
        category="training",
        status=ShemaNeedStatus.FULFILLED,
        prayer_answered=True,
    )

    await make_project(
        db_session,
        "quechua-cusco",
        location="Peru",
        status=ShemaProjectStatus.PAUSADO,
        total_units=50,
        translated_units=10,
        objective=["Histórias"],
        team="YWAM Lima",
        vitality_status="Ameaçada",
        deadline=TODAY + timedelta(days=200),
    )
    await add_progress(db_session, "quechua-cusco", LONG_AGO)

    await make_project(
        db_session,
        "nahuatl-sierra",
        region=ShemaRegionKey.NORTH_AMERICA,
        location="Mexico",
        status=ShemaProjectStatus.CONCLUIDO,
        total_units=40,
        translated_units=40,
        objective=["NT"],
        team="YWAM Morelia",
        deadline=TODAY + timedelta(days=30),
    )

    await make_project(
        db_session,
        "coptic-delta",
        region=ShemaRegionKey.AFRICA,
        location="Egypt",
        sensitive=True,
        status=ShemaProjectStatus.EM_ANDAMENTO,
        total_units=100,
        translated_units=20,
        objective=["AT"],
        team="YWAM Egypt",
        language_name="Coptic Delta",
    )
    await add_progress(db_session, "coptic-delta", LONG_AGO)
    await add_need(db_session, "coptic-delta", category="security", prayer_shared=True)

    await make_project(
        db_session,
        "hausa-north",
        region=ShemaRegionKey.AFRICA,
        location="Sudan",
        status=ShemaProjectStatus.PLANEJADO,
        objective=["Bíblia Completa"],
        team="YWAM Khartoum",
    )

    await make_project(
        db_session,
        "tok-pisin-highlands",
        region=ShemaRegionKey.OCEANIA,
        location="Papua New Guinea",
        total_units=100,
        translated_units=80,
        team="YWAM Goroka",
        last_updated=RECENTLY,
    )

    await make_project(
        db_session,
        "bahasa-papua",
        region=ShemaRegionKey.ASIA,
        location="Indonesia",
        status=ShemaProjectStatus.CANCELADO,
        team="YWAM Sentani",
    )

    # The ninth is the shape most of this table really is: a language somebody typed in and
    # nothing else. All 127 export records arrive with every health dimension empty, 27 of the
    # 55 export columns empty on every row, and no progress history at all — so a fixture with
    # no thin record in it would test a database this product does not have.
    await make_project(
        db_session,
        "silent-record",
        region=ShemaRegionKey.OCEANIA,
        location="Fiji",
        team="YWAM Suva",
    )
    return db_session


@pytest.fixture()
async def reader(db_session, shema_app):
    """A ``globalStrategist``: every region, no admin flag, nothing else granted."""
    return await make_scoped_user(
        db_session, shema_app, email="global@shema.test", role_key="globalStrategist"
    )


async def fetch(client, db_session, user, **params: Any) -> dict[str, Any]:
    response = await client.get(
        PROJECTS, params=params, headers=await auth_header(db_session, user)
    )
    assert response.status_code == 200, response.text
    return response.json()


def ids(page: dict[str, Any]) -> list[str]:
    return [item["id"] for item in page["items"]]


async def test_with_no_parameters_it_is_still_the_whole_scoped_collection(
    client, db_session, collection, reader
) -> None:
    """FE-44 §9.1's frozen default, kept as the default rather than as a compatibility mode.

    Eight projects in, eight out, no window — so the console's own one-pass ``filterProjects``
    keeps working over ``items`` unchanged, and taking a page is something a caller asks for.
    """
    page = await fetch(client, db_session, reader)
    assert len(page["items"]) == 9
    assert page["total"] == page["matched"] == 9
    assert page["limit"] is None and page["offset"] == 0


async def test_the_counts_arrive_whether_or_not_anything_was_filtered(
    client, db_session, collection, reader
) -> None:
    """There is no request that returns the filter without the counts.

    That is FE-44 §9.1's *never the filter alone*, held by the response type rather than by a
    note: the sixteen groups, the four presets and the sixteen group totals are in every
    answer, including the unfiltered one.
    """
    for params in ({}, {"status": "em-andamento"}):
        page = await fetch(client, db_session, reader, **params)
        assert set(page["counts"]["groups"]) == {
            "status",
            "team",
            "health",
            "objective",
            "financial",
            "stale",
            "country",
            "continent",
            "vitality",
            "translationType",
            "needCategory",
            "eten",
            "sensitive",
            "progressRange",
            "hasMedia",
            "hasOpenNeeds",
        }
        assert set(page["counts"]["presets"]) == {"attention", "prayer", "celebrate", "recent"}
        assert set(page["counts"]["groupAll"]) == set(page["counts"]["groups"])


#: The query parameter each facet group is filtered by. Written out rather than derived so
#: that a group whose parameter is misspelled fails here instead of counting forever.
GROUP_PARAM = {
    "status": "status",
    "team": "team",
    "health": "health",
    "objective": "objective",
    "financial": "financial",
    "stale": "stale",
    "country": "country",
    "continent": "continent",
    "vitality": "vitality",
    "translationType": "translationType",
    "needCategory": "needCategory",
    "eten": "eten",
    "sensitive": "sensitive",
    "progressRange": "progressRange",
    "hasMedia": "hasMedia",
    "hasOpenNeeds": "hasOpenNeeds",
}


async def test_every_facet_count_is_what_clicking_it_returns(
    client, db_session, collection, reader
) -> None:
    """**The DoD's second line, over the whole cross product rather than a sample.**

    For every option of every one of the sixteen groups, re-request with that option applied
    and assert the list is exactly as long as the count said. A facet that over-counts promises
    results a click will not return; one that under-counts hides a project from the only filter
    that would have found it. Both are the failure the issue describes, and both are caught
    here for every option the response is willing to name.
    """
    page = await fetch(client, db_session, reader)
    checked = 0
    for group, options in page["counts"]["groups"].items():
        for option, promised in options.items():
            clicked = await fetch(client, db_session, reader, **{GROUP_PARAM[group]: option})
            assert clicked["matched"] == promised, (
                f"the sidebar promised {promised} for {group}={option} and the list returned "
                f"{clicked['matched']}"
            )
            checked += 1
    assert checked > 40, "the fixture stopped exercising the groups it was built to exercise"


async def test_every_preset_count_is_what_toggling_it_returns(
    client, db_session, collection, reader
) -> None:
    """The same property for the four presets, which are toggles rather than option lists."""
    page = await fetch(client, db_session, reader)
    for preset, promised in page["counts"]["presets"].items():
        clicked = await fetch(client, db_session, reader, presets=preset)
        assert clicked["matched"] == promised, f"preset {preset} promised {promised}"


async def test_a_count_beside_an_active_filter_is_still_what_clicking_it_returns(
    client, db_session, collection, reader
) -> None:
    """The half of the rule that a naïve implementation gets wrong.

    With ``continent=south-america`` already on, the counts in *other* groups must describe the
    filtered set — but the counts in the **continent** group itself must not, or every other
    region would show zero and the user could never leave the region they are in. That is
    *an option counts a record that passes every group except, at most, that one*, and it is
    checked from both sides: the status counts narrow, the continent counts do not.
    """
    page = await fetch(client, db_session, reader, continent="south-america")
    assert page["matched"] == 3

    for status, promised in page["counts"]["groups"]["status"].items():
        clicked = await fetch(client, db_session, reader, continent="south-america", status=status)
        assert clicked["matched"] == promised

    for continent, promised in page["counts"]["groups"]["continent"].items():
        clicked = await fetch(client, db_session, reader, continent=continent)
        assert clicked["matched"] == promised
    assert page["counts"]["groups"]["continent"]["africa"] == 2


async def test_the_group_all_row_is_the_count_with_that_group_cleared(
    client, db_session, collection, reader
) -> None:
    """``groupAll`` is what the *All* row of a group shows, and clearing it must agree."""
    page = await fetch(client, db_session, reader, continent="africa", status="em-andamento")
    cleared_status = await fetch(client, db_session, reader, continent="africa")
    assert page["counts"]["groupAll"]["status"] == cleared_status["matched"]
    cleared_continent = await fetch(client, db_session, reader, status="em-andamento")
    assert page["counts"]["groupAll"]["continent"] == cleared_continent["matched"]


async def test_filters_compose_across_every_kind_of_group(
    client, db_session, collection, reader
) -> None:
    """Any combination, and the combination narrows — the DoD's first line.

    Five groups of five different shapes at once: a stored enum, a derived value, a JSON
    array, a child-table join and free text. FE-12 established the full set and the server
    builds all of it, so a filter the current UI does not render still composes.
    """
    page = await fetch(
        client,
        db_session,
        reader,
        status="em-andamento",
        health="critica",
        objective="NT",
        needCategory="equipment",
        q="guarani",
    )
    assert ids(page) == ["guarani-mbya"]
    assert page["matched"] == 1
    assert page["total"] == 9, "total is the scope, never the filtered set"


async def test_an_unknown_option_returns_nothing_rather_than_refusing(
    client, db_session, collection, reader
) -> None:
    """A vocabulary the server does not police answers honestly instead of 422-ing.

    FE-44's Appendix A freezes the lists on the frontend; a server-side allowlist would be a
    second copy that refuses a value the day the client adds one. *Show me the projects whose
    objective is Xyz* has an honest answer and it is none.
    """
    page = await fetch(client, db_session, reader, objective="Xyz")
    assert page["items"] == [] and page["matched"] == 0 and page["total"] == 9


async def test_a_misspelled_parameter_is_refused_rather_than_ignored(
    client, db_session, collection, reader
) -> None:
    """The one thing the query model does police, and the reason it does.

    A filter that silently does not apply returns more rows than asked for, on a screen whose
    whole promise is that the numbers agree with the list. ``extra="forbid"`` turns that into
    an error message.
    """
    response = await client.get(
        PROJECTS,
        params={"contintent": "africa"},
        headers=await auth_header(db_session, reader),
    )
    assert response.status_code == 422


async def test_the_search_is_accent_and_case_blind(client, db_session, collection, reader) -> None:
    """*Purépecha* and *Purepecha* are one language; a coordinator should not have to know."""
    assert ids(await fetch(client, db_session, reader, q="BELEM")) == ["guarani-mbya", "kaapor"]
    assert ids(await fetch(client, db_session, reader, q="belém")) == ["guarani-mbya", "kaapor"]


async def test_the_derived_block_is_the_servers_answer_and_carries_wave_one_semantics(
    client, db_session, collection, reader
) -> None:
    """**The DoD's third line**: status, health and staleness, computed here.

    Four readings a reimplementer gets wrong alone, each on the record that shows it:
    a stored status **wins** over the derivation (``pausado`` at 20% is not ``em-andamento``);
    an unassessed record is ``na`` and never ``boa``; overall health is the **worst** of the
    dimensions, not the average; and a status that makes staleness meaningless answers
    ``null`` rather than ``em-dia``.
    """
    page = await fetch(client, db_session, reader)
    derived = {item["id"]: item["derived"] for item in page["items"]}

    assert derived["quechua-cusco"]["status"] == "pausado"
    assert derived["quechua-cusco"]["progress"] == 20
    assert derived["kaapor"]["status"] == "em-andamento", (
        "kaapor is 80% translated, which derives to final — and it carries a stored status, "
        "which wins"
    )
    assert derived["tok-pisin-highlands"]["status"] == "final", "same 80%, nothing stored"
    assert derived["silent-record"]["status"] == "nao-iniciado"
    assert derived["nahuatl-sierra"]["status"] == "concluido"

    assert derived["hausa-north"]["health"] == "na"
    assert derived["kaapor"]["health"] == "atencao"
    assert derived["guarani-mbya"]["health"] == "critica"

    assert derived["coptic-delta"]["stale"] == "critico"
    assert derived["kaapor"]["stale"] == "atencao"
    assert derived["guarani-mbya"]["stale"] == "em-dia"
    assert derived["hausa-north"]["stale"] is None
    assert derived["nahuatl-sierra"]["stale"] is None


async def test_sem_noticias_means_atencao_or_critico_and_not_the_middle_band(
    client, db_session, collection, reader
) -> None:
    """The filter named after the projects most out of contact must contain them.

    Before ``isNoNews`` existed on the frontend they were absent from it, because ``atencao``
    was read as the ``[60, 120)`` bucket. ``critico`` keeps exact matching, so the two filters
    are not the same filter.
    """
    no_news = await fetch(client, db_session, reader, stale="atencao")
    assert set(ids(no_news)) == {"kaapor", "coptic-delta", "quechua-cusco"}

    critical = await fetch(client, db_session, reader, stale="critico")
    assert set(ids(critical)) == {"coptic-delta", "quechua-cusco"}

    page = await fetch(client, db_session, reader)
    assert page["counts"]["groups"]["stale"]["atencao"] == 3
    assert page["counts"]["groups"]["stale"]["critico"] == 2


async def test_a_regional_scope_reaches_the_counts_and_not_only_the_results(
    client, db_session, collection, shema_app
) -> None:
    """**The DoD's fourth line, first half.** A count is the cheapest leak in the module.

    A coordinator scoped to Africa is told about two projects and about *two of everything
    else*: the continent facet names Africa and nothing beside it, the team facet names the
    two African bases and no others, and ``total`` is the size of their reach rather than of
    the table. A number does not look like data, which is why a query written for a badge is
    the one nobody thinks to scope.
    """
    coordinator = await make_scoped_user(
        db_session,
        shema_app,
        email="africa@shema.test",
        role_key="coordinator",
        regions=[ShemaRegionKey.AFRICA],
    )
    page = await fetch(client, db_session, coordinator)

    assert set(ids(page)) == {"coptic-delta", "hausa-north"}
    assert page["total"] == 2
    assert page["counts"]["groups"]["continent"] == {"africa": 2}
    assert set(page["counts"]["groups"]["team"]) == {"YWAM Egypt", "YWAM Khartoum"}
    assert page["counts"]["groupAll"]["status"] == 2

    asked_for_another_region = await fetch(
        client, db_session, coordinator, continent="south-america"
    )
    assert asked_for_another_region["items"] == []
    assert asked_for_another_region["counts"]["groups"]["continent"] == {"africa": 2}


async def test_a_regional_role_with_no_region_granted_reaches_nothing(
    client, db_session, collection, shema_app
) -> None:
    """The fail-closed floor, read through the counts as well as the list.

    ``app/services/access_request`` grants a role on approval and grants no region, so this is
    a real account shape and not a contrived one. Every count is zero or absent; none of them
    says how large the table is.
    """
    unscoped = await make_scoped_user(
        db_session, shema_app, email="unscoped@shema.test", role_key="obtLab", regions=[]
    )
    page = await fetch(client, db_session, unscoped)
    assert page["items"] == [] and page["total"] == 0 and page["matched"] == 0
    assert page["counts"]["groups"]["continent"] == {}
    assert page["counts"]["groups"]["team"] == {}
    assert set(page["counts"]["groups"]["health"].values()) == {0}


async def test_the_sensitive_country_rule_reaches_the_counts_and_not_only_the_results(
    client, db_session, collection, reader
) -> None:
    """**The DoD's fourth line, second half** — and the sharpest form of *they agree*.

    ``coptic-delta`` is in Egypt and flagged. Its card says ``africa`` where its country would
    be, its base is blank, and it plots at the region's centroid. The **country facet says the
    same thing**: there is no ``Egypt`` key to count it under, it is counted under ``africa``,
    and filtering by ``country=Egypt`` returns nothing while ``country=africa`` returns it. A
    facet cannot name a place the payload beside it withholds, because it is reading that
    payload.
    """
    page = await fetch(client, db_session, reader)
    card = next(item for item in page["items"] if item["id"] == "coptic-delta")

    assert card["locationWithheld"] is True
    assert card["location"] == "africa"
    assert card["team"] == ""
    assert card["coords"] == [20.0, 5.0]
    assert "Egypt" not in response_text(page)

    countries = page["counts"]["groups"]["country"]
    assert "Egypt" not in countries
    assert countries["africa"] == 1
    assert countries["Sudan"] == 1, "an unflagged African project keeps its own country"

    assert (await fetch(client, db_session, reader, country="Egypt"))["matched"] == 0
    assert ids(await fetch(client, db_session, reader, country="africa")) == ["coptic-delta"]
    assert page["counts"]["groups"]["sensitive"] == {"yes": 1, "no": 8}
    assert page["locationsWithheld"] == 1


async def test_a_withheld_note_is_absent_rather_than_zero(
    client, db_session, collection, reader
) -> None:
    """*0 locations withheld* is a sentence about the absence of sensitive projects.

    It answers a question nobody asked on every response, and the one time it is interesting is
    the one time it should not be said.
    """
    page = await fetch(client, db_session, reader, continent="south-america")
    assert page["locationsWithheld"] is None


async def test_the_search_cannot_be_used_to_confirm_a_withheld_country(
    client, db_session, collection, reader
) -> None:
    """A search is an output path and the cheapest one to forget.

    It returns no location at all — it returns whether a query *matched*, which a caller can
    read a country off. The haystack ``_redaction.py`` allows for a withheld project holds
    nothing it is not already willing to say in a payload.
    """
    assert (await fetch(client, db_session, reader, q="Egypt"))["matched"] == 0
    assert ids(await fetch(client, db_session, reader, q="coptic")) == ["coptic-delta"]
    assert ids(await fetch(client, db_session, reader, q="Sudan")) == ["hausa-north"]


async def test_the_window_is_a_window_over_an_ordered_set_and_the_counts_are_not_paged(
    client, db_session, collection, reader
) -> None:
    """**The DoD's first line, second half.** Paging is about the API not changing shape.

    The counts and both totals describe the filtered **set**; only ``items`` is the page. A
    ``LIMIT`` applied before the pass would count a page, and the sidebar would then describe
    whichever rows happened to be on screen.
    """
    whole = await fetch(client, db_session, reader, sort="name")
    first = await fetch(client, db_session, reader, sort="name", limit=3)
    second = await fetch(client, db_session, reader, sort="name", limit=3, offset=3)
    last = await fetch(client, db_session, reader, sort="name", limit=3, offset=6)

    assert ids(first) + ids(second) + ids(last) == ids(whole)
    assert len(first["items"]) == len(last["items"]) == 3
    for page in (first, second, last):
        assert page["total"] == 9 and page["matched"] == 9
        assert page["counts"] == whole["counts"]


async def test_an_offset_past_the_end_is_an_empty_page_and_not_an_error(
    client, db_session, collection, reader
) -> None:
    """A saved link to page 40 of a list that shrank is a page with nothing on it."""
    page = await fetch(client, db_session, reader, limit=3, offset=300)
    assert page["items"] == [] and page["matched"] == 9


@pytest.mark.parametrize(
    ("sort", "leading"),
    [
        ("name", ["bahasa-papua", "coptic-delta", "guarani-mbya"]),
        ("progress", ["nahuatl-sierra"]),
        ("health", ["kaapor", "guarani-mbya"]),
        ("deadline", ["nahuatl-sierra", "quechua-cusco"]),
    ],
)
async def test_the_five_orders_are_the_screens_five_orders(
    client, db_session, collection, reader, sort: str, leading: list[str]
) -> None:
    """Each order asserted where it actually decides something, and not where it ties.

    Ties fall back to the collection's own order, which is a property of the read below this
    and not of the sort — so a test that pinned the tail of ``progress`` would be pinning
    SQLite's collation of ``language_name`` and would fail for a reason that is not about
    sorting at all.

    ``name`` is the one worth reading twice: ``coptic-delta``'s language name is *Coptic
    Delta*, capitalised, and it files between *bahasa* and *guarani* rather than before both —
    which is ``localeCompare`` on the frontend and the reason this file does not sort by code
    point.
    """
    page = await fetch(client, db_session, reader, sort=sort)
    assert ids(page)[: len(leading)] == leading


async def test_a_blank_sorts_last_and_a_withheld_base_is_a_blank(
    client, db_session, collection, reader
) -> None:
    """``blanksLast``, and the record that makes it interesting here.

    Sorting blanks first puts the records with the least in them at the top of the busiest
    screen, which is where nobody is looking for them. ``coptic-delta`` has a base — *YWAM
    Egypt* — and the payload does not, because the base names the place (FE-44 §8.1 rule 3).
    So the order is over what the caller was actually given, which is the only order that can
    agree with what they see.
    """
    page = await fetch(client, db_session, reader, sort="team")
    assert ids(page)[0] == "guarani-mbya"
    assert ids(page)[-1] == "coptic-delta"
    assert page["items"][-1]["team"] == ""


async def test_an_unknown_sort_falls_back_instead_of_refusing(
    client, db_session, collection, reader
) -> None:
    """A saved view from a newer console must not 422 an older server."""
    page = await fetch(client, db_session, reader, sort="colour")
    assert page["sort"] == "deadline"
    assert len(page["items"]) == 9


async def test_the_payload_speaks_the_contracts_camel_case(
    client, db_session, collection, reader
) -> None:
    """The wire spelling this issue decided, checked on the fields most likely to drift."""
    card = next(
        item
        for item in (await fetch(client, db_session, reader))["items"]
        if item["id"] == "guarani-mbya"
    )
    for key in ("languageName", "translationType", "totalUnits", "locationWithheld", "hasMedia"):
        assert key in card
    for key in ("language_name", "search_text", "searchText", "latitude", "longitude"):
        assert key not in card
    assert set(card["derived"]) == {
        "status",
        "health",
        "stale",
        "progress",
        "priority",
        "healthScore",
        "daysSinceUpdate",
        "lastProgressUpdate",
        "region",
    }


def test_the_published_parameters_are_the_screens_own_url_parameters() -> None:
    """A saved view's link and a request to this endpoint are the same string.

    Read off the **OpenAPI document** and not off the model, because that document is what a
    generated client is written against: a server that accepts ``translationType`` while
    advertising ``translation_type`` is worse than either spelling alone, and the two halves
    are configured separately in Pydantic — so the failure is invisible at runtime and shows
    up the day somebody generates a client.

    The expected set is ``src/utils/filterSerialisation.ts``'s three free-text keys, thirteen
    enum keys, ``presets``, ``q`` and ``sort``, plus the window and the four presets as
    individual booleans — the one thing here the screen's URL does not write, kept because a
    single preset is a more natural thing for a non-browser caller to ask for than a
    one-element comma list.
    """
    from app.main import create_app

    spec = create_app().openapi()
    published = {
        parameter["name"] for parameter in spec["paths"]["/api/shema/projects"]["get"]["parameters"]
    }
    assert published == {
        "q",
        "sort",
        "presets",
        "limit",
        "offset",
        "team",
        "country",
        "vitality",
        "objective",
        "status",
        "health",
        "financial",
        "stale",
        "continent",
        "translationType",
        "eten",
        "sensitive",
        "progressRange",
        "needCategory",
        "hasMedia",
        "hasOpenNeeds",
        "attention",
        "prayer",
        "celebrate",
        "recent",
    }


async def seed_the_whole_export(db_session) -> int:
    """The 127 real records, plus a need and a progress entry each.

    The columns the screen reads, from the export's own values — **not** BE-16's importer,
    which owns the interpretation (the ``DD/MM/YYYY`` dates, the free-text ``sensitivity``,
    ``[0, 0]`` as *no coordinate*). What this needs from the export is its **shape**: 127 rows
    with real teams, real country strings and a realistic spread of statuses.
    """
    import json
    from pathlib import Path

    export = json.loads(
        (Path(__file__).parent / "shemaProjectsExport.json").read_text(encoding="utf-8")
    )
    for row in export:
        db_session.add(
            ShemaProject(
                id=row["id"],
                language_name=row["languageName"],
                location=row["location"],
                team=row["team"],
                objective=row["objective"],
                translation_type=row["translationType"],
                financial_resources=row["financialResources"],
                vitality_status=row["vitalityStatus"],
                total_units=row["totalUnits"],
                translated_units=row["translatedUnits"],
                status=ShemaProjectStatus(row["status"]),
                sensitive_country=bool(row["sensitiveCountry"]),
                region_key=ShemaRegionKey(_region_of(row["location"])),
            )
        )
    await db_session.commit()
    for row in export:
        db_session.add(ShemaProgressEntry(project_id=row["id"], entry_date=A_WHILE_AGO))
        db_session.add(
            ShemaNeed(
                project_id=row["id"],
                category="financial",
                urgency=ShemaNeedUrgency.MEDIUM,
                status=ShemaNeedStatus.OPEN,
            )
        )
    await db_session.commit()
    return len(export)


async def test_the_screens_real_query_load_does_not_grow_with_the_collection(
    client, db_session, test_engine, collection, reader
) -> None:
    """**The DoD's last line**, guarded by the shape of the work rather than by a stopwatch.

    The same request is timed twice for **statements, not milliseconds** — once over the nine
    records of the fixture and once with the export's 127 added to them — and the assertion is
    that the two numbers are the same. That is the failure worth catching here: a per-record
    query appearing under the pass. A wall-clock bound reports it only once the table is large
    enough and the machine quiet enough for it to show, which on a shared runner is neither
    reliably true nor reliably false.

    No magic constant, deliberately. What the number *is* depends on how many statements the
    authentication chain makes before the handler runs, which is the platform's and not this
    module's; what matters is that it does not move with the size of the collection.

    **One warm-up request before anything is measured**, and it is not a formality:
    ``require_app_access`` memoises an account's roles for ``AUTH_CACHE_TTL_SECONDS``, so the
    first request of a test pays two statements every later one does not. Measured cold, the
    numbers fall from eight to six between the two sizes — which reads as the collection
    getting *cheaper* as it grows, and would have hidden a real regression just as easily.

    The three requests are the ones the screen actually makes: the unfiltered collection, a
    composed filter, and a page. The page is in the list because a window taken before the pass
    would change the shape of the work as well as the answer.
    """
    from sqlalchemy import event

    statements: list[str] = []

    def record(conn, cursor, statement, parameters, context, executemany) -> None:
        statements.append(statement)

    async def count(**params: Any) -> tuple[int, dict[str, Any]]:
        statements.clear()
        event.listen(test_engine.sync_engine, "before_cursor_execute", record)
        try:
            page = await fetch(client, db_session, reader, **params)
        finally:
            event.remove(test_engine.sync_engine, "before_cursor_execute", record)
        return len(statements), page

    requests: dict[str, dict[str, Any]] = {
        "unfiltered": {},
        "filtered": {"status": "em-andamento", "stale": "atencao", "q": "a", "sort": "health"},
        "paged": {"limit": 24, "offset": 24},
    }
    await fetch(client, db_session, reader)  # warm the role cache; see the docstring
    small = {name: await count(**params) for name, params in requests.items()}
    assert small["unfiltered"][1]["total"] == 9

    seeded = await seed_the_whole_export(db_session)
    await fetch(client, db_session, reader)
    large = {name: await count(**params) for name, params in requests.items()}

    assert large["unfiltered"][1]["total"] == 9 + seeded == 136
    assert len(large["unfiltered"][1]["items"]) == 136
    assert 0 < large["filtered"][1]["matched"] < 136
    assert len(large["paged"][1]["items"]) == 24

    grew = {
        name: (small[name][0], large[name][0])
        for name in requests
        if small[name][0] != large[name][0]
    }
    assert grew == {}, (
        "the statement count moved between 9 records and 136, which is a query per record "
        f"appearing under the pass: {grew}"
    )
    assert all(count <= 10 for count, _page in large.values()), (
        "constant, but no longer small: this module's four reads plus the platform's "
        f"authentication chain, and nothing else — {[c for c, _ in large.values()]}"
    )


def _region_of(location: str) -> str:
    from app.utils.shema_derivations import get_region

    return get_region(location).value


def response_text(page: dict[str, Any]) -> str:
    import json

    return json.dumps(page, ensure_ascii=False)
