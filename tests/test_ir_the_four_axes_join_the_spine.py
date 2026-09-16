import pytest

from app.core.exceptions import ValidationError
from app.services.internalization_room.canon.elements import ElementKind, elements_for
from app.services.internalization_room.canon.parse_map import MAPS_DIR, load_map, parse_map

P01 = "P01"


def test_the_four_level_one_sections_of_the_map_are_read() -> None:
    meaning_map = load_map(P01)

    assert meaning_map.arc_prose.startswith("The passage opens wide, on a whole era")
    assert meaning_map.context_prose.startswith("This is where the book of Ruth begins")
    assert meaning_map.tone_prose.startswith("The tone is held-in and plain")
    assert meaning_map.function_prose.startswith("The passage opens the book by laying out")
    assert meaning_map.function_prose.endswith("how the emptying began.")


@pytest.mark.parametrize(
    "heading",
    ["### 2.2 Context", "### 2.3 Emotion / Tone / Pace", "### 2.4 Communicative Function"],
)
def test_a_map_missing_a_level_one_section_is_refused_like_one_missing_its_arc(
    heading: str,
) -> None:
    text = (MAPS_DIR / "P01-Ruth-1-1-5.md").read_text().replace(heading, "### 2.9 Something")

    with pytest.raises(ValidationError, match=r"Level-1 \w+ prose not found"):
        parse_map(text, source="P01-holed")


def test_the_four_axes_open_the_necklace_and_belong_to_no_scene() -> None:
    first_four = elements_for(P01)[:4]

    assert [element.key for element in first_four] == ["arc", "context", "tone", "function"]
    assert [element.kind for element in first_four] == [
        ElementKind.ARC,
        ElementKind.CONTEXT,
        ElementKind.TONE,
        ElementKind.FUNCTION,
    ]
    assert [element.label for element in first_four] == [
        "Level-1 arc",
        "Level-1 context",
        "Level-1 tone",
        "Level-1 function",
    ]
    assert all(element.scene is None for element in first_four)


def test_each_axis_carries_its_own_section_of_the_map_as_detail() -> None:
    by_key = {element.key: element for element in elements_for(P01)}

    assert by_key["arc"].detail.startswith("The passage opens wide, on a whole era")
    assert by_key["context"].detail.startswith("This is where the book of Ruth begins")
    assert "never says God did any of it" in by_key["tone"].detail
    assert by_key["function"].detail.endswith("how the emptying began.")
    assert by_key["scene:1"].detail == ""
