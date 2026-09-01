import pytest

from app.services.book_context.compute_entry_brief import (
    _build_established_items,
    compute_entry_brief,
)
from app.services.meaning_map.generator import _format_entry_brief
from tests.baker import make_bcd, make_bible_book, make_pericope, make_user

SAMPLE_BCD_DATA = {
    "participant_register": [
        {
            "name": "Elimelech",
            "type": "named",
            "entry_verse": {"chapter": 1, "verse": 1},
            "role_in_book": "supporting",
            "relationships": [],
            "arc": [{"at": {"chapter": 1, "verse": 1}, "state": "alive"}],
            "status_at_end": "dead",
        },
    ],
    "discourse_threads": [
        {
            "label": "Famine",
            "opened_at": {"chapter": 1, "verse": 1},
            "resolved_at": None,
            "question": "Will the famine end?",
            "status_by_episode": [],
        },
    ],
    "places": [
        {
            "name": "Bethlehem",
            "english_gloss": "House of Bread",
            "first_appears": {"chapter": 1, "verse": 1},
            "type": "city",
            "meaning_and_function": "hometown, promised land",
        },
        {
            "name": "Moab",
            "english_gloss": "",
            "first_appears": {"chapter": 1, "verse": 1},
            "type": "country",
            "meaning_and_function": "exile",
        },
        {
            "name": "Boaz's field",
            "first_appears": {"chapter": 2, "verse": 3},
            "type": "field",
            "meaning_and_function": "provision",
        },
    ],
    "objects": [
        {
            "name": "grain",
            "first_appears": {"chapter": 2, "verse": 2},
            "what_it_is": "harvested barley",
        },
        {
            "name": "sandal",
            "first_appears": {"chapter": 4, "verse": 7},
            "what_it_is": "symbol of transfer of rights",
        },
    ],
    "institutions": [
        {
            "name": "gleaning rights",
            "first_invoked": {"chapter": 2, "verse": 2},
            "what_it_is": "right of the poor to gather leftover grain",
        },
    ],
}


def test_build_established_items_includes_places():
    items = _build_established_items(
        participants=[],
        threads=[],
        institutions=[],
        places=[
            {
                "name": "Bethlehem",
                "english_gloss": "House of Bread",
                "first_appears": {"chapter": 1, "verse": 1},
                "meaning_and_function": "hometown",
            },
        ],
    )
    place_items = [i for i in items if i.category == "place"]
    assert len(place_items) == 1
    assert place_items[0].name == "Bethlehem"
    assert place_items[0].english_gloss == "House of Bread"
    assert place_items[0].description == "hometown"


def test_build_established_items_includes_objects():
    items = _build_established_items(
        participants=[],
        threads=[],
        institutions=[],
        objects=[
            {
                "name": "grain",
                "first_appears": {"chapter": 2, "verse": 2},
                "what_it_is": "harvested barley",
            },
        ],
    )
    obj_items = [i for i in items if i.category == "object"]
    assert len(obj_items) == 1
    assert obj_items[0].name == "grain"
    assert obj_items[0].description == "harvested barley"


def test_build_established_items_all_categories():
    items = _build_established_items(
        participants=[
            {"name": "Naomi", "entry_verse": {"chapter": 1, "verse": 2}, "arc": []},
        ],
        threads=[
            {"label": "Famine", "opened_at": {"chapter": 1, "verse": 1}, "status_by_episode": []},
        ],
        institutions=[
            {
                "name": "gleaning",
                "first_invoked": {"chapter": 2, "verse": 2},
                "what_it_is": "right",
            },
        ],
        places=[
            {
                "name": "Bethlehem",
                "first_appears": {"chapter": 1, "verse": 1},
                "meaning_and_function": "home",
            },
        ],
        objects=[
            {"name": "grain", "first_appears": {"chapter": 2, "verse": 2}, "what_it_is": "food"},
        ],
    )
    categories = {i.category for i in items}
    assert categories == {"participant", "event", "institution", "place", "object"}


@pytest.mark.asyncio
async def test_entry_brief_places_in_established_items(db_session):
    user = await make_user(db_session, email="eb_places@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    await make_bcd(db_session, book.id, user.id, status="approved", **SAMPLE_BCD_DATA)
    await make_pericope(
        db_session,
        book.id,
        chapter_start=1,
        verse_start=1,
        chapter_end=1,
        verse_end=5,
        reference="Ruth 1:1-5",
    )
    p2 = await make_pericope(
        db_session,
        book.id,
        chapter_start=2,
        verse_start=1,
        chapter_end=2,
        verse_end=7,
        reference="Ruth 2:1-7",
    )

    brief = await compute_entry_brief(db_session, p2.id)

    categories = {i.category for i in brief.established_items}
    assert "place" in categories
    place_names = [i.name for i in brief.established_items if i.category == "place"]
    assert "Bethlehem" in place_names
    assert "Moab" in place_names

    assert "Boaz's field" not in place_names


@pytest.mark.asyncio
async def test_entry_brief_objects_in_established_items(db_session):
    user = await make_user(db_session, email="eb_objects@test.com")
    book = await make_bible_book(
        db_session,
        name="Ruth",
        abbreviation="Rth",
        order=8,
        chapter_count=4,
    )
    await make_bcd(db_session, book.id, user.id, status="approved", **SAMPLE_BCD_DATA)
    await make_pericope(
        db_session,
        book.id,
        chapter_start=1,
        verse_start=1,
        chapter_end=1,
        verse_end=5,
        reference="Ruth 1:1-5",
    )
    p2 = await make_pericope(
        db_session,
        book.id,
        chapter_start=2,
        verse_start=4,
        chapter_end=2,
        verse_end=10,
        reference="Ruth 2:4-10",
    )

    brief = await compute_entry_brief(db_session, p2.id)

    obj_items = [i for i in brief.established_items if i.category == "object"]
    obj_names = [i.name for i in obj_items]
    assert "grain" in obj_names

    assert "sandal" not in obj_names


def test_format_entry_brief_includes_places():
    brief = {
        "established_items": [],
        "participants": [],
        "active_threads": [],
        "places": [
            {
                "name": "Bethlehem",
                "english_gloss": "House of Bread",
                "meaning_and_function": "home",
            },
        ],
        "objects": [],
        "institutions": [],
    }
    result = _format_entry_brief(brief)
    assert "Known Places at Entry" in result
    assert "Bethlehem (House of Bread)" in result
    assert "home" in result


def test_format_entry_brief_includes_objects():
    brief = {
        "established_items": [],
        "participants": [],
        "active_threads": [],
        "places": [],
        "objects": [
            {"name": "grain", "what_it_is": "harvested barley"},
        ],
        "institutions": [],
    }
    result = _format_entry_brief(brief)
    assert "Known Objects at Entry" in result
    assert "grain" in result
    assert "harvested barley" in result


def test_format_entry_brief_includes_institutions():
    brief = {
        "established_items": [],
        "participants": [],
        "active_threads": [],
        "places": [],
        "objects": [],
        "institutions": [
            {"name": "gleaning rights", "what_it_is": "right of the poor"},
        ],
    }
    result = _format_entry_brief(brief)
    assert "Known Institutions at Entry" in result
    assert "gleaning rights" in result


def test_format_entry_brief_includes_english_gloss():
    brief = {
        "established_items": [
            {
                "category": "participant",
                "name": "Naomi",
                "english_gloss": "Pleasant",
                "description": "protagonist",
                "verse_reference": "1:2",
            },
        ],
        "participants": [],
        "active_threads": [],
    }
    result = _format_entry_brief(brief)
    assert "Naomi (Pleasant)" in result


def test_format_entry_brief_no_gloss():
    brief = {
        "established_items": [
            {
                "category": "event",
                "name": "Famine",
                "english_gloss": "",
                "description": "a famine",
                "verse_reference": "1:1",
            },
        ],
        "participants": [],
        "active_threads": [],
    }
    result = _format_entry_brief(brief)

    assert "Famine:" in result
    assert "()" not in result
