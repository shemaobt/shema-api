import json
from unittest.mock import patch

import pytest

from app.services.book_context.generation.nodes.context_sections import (
    _generate_place_batch,
    _parse_and_normalize_context_sections,
    _parse_and_normalize_places,
    generate_context_sections,
)

VALID_PLACE = {
    "name": "Bethlehem",
    "english_gloss": "house of bread",
    "entity_type": "place",
    "first_appears": {"chapter": 1, "verse": 1},
    "type": "city",
}


class TestParseAndNormalizePlaces:
    def test_valid_payload_passes_through(self):
        raw = json.dumps({"places": [VALID_PLACE]})
        result = _parse_and_normalize_places(raw)
        assert result == [VALID_PLACE]

    def test_invalid_type_is_normalized_to_other(self):
        bad = {**VALID_PLACE, "type": "city/empire"}
        raw = json.dumps({"places": [bad]})
        result = _parse_and_normalize_places(raw)
        assert result[0]["type"] == "other"
        assert result[0]["_legacy_type"] == "city/empire"

    def test_strips_markdown_fences(self):
        raw = "```json\n" + json.dumps({"places": [VALID_PLACE]}) + "\n```"
        result = _parse_and_normalize_places(raw)
        assert result == [VALID_PLACE]

    def test_handles_bare_list_fallback(self):
        raw = json.dumps([VALID_PLACE])
        result = _parse_and_normalize_places(raw)
        assert result == [VALID_PLACE]

    def test_returns_empty_list_on_unparseable_payload(self):
        result = _parse_and_normalize_places("garbage payload")
        assert result == []


class TestParseAndNormalizeContextSections:
    def test_valid_payload_preserves_all_fields(self):
        payload = {
            "theological_spine": "covenant fidelity",
            "places": [VALID_PLACE],
            "objects": [{"name": "manna"}],
            "institutions": [{"name": "priesthood"}],
            "genre_context": {"primary_genre": "narrative"},
            "maintenance_notes": {"generation_notes": "ok"},
        }
        result = _parse_and_normalize_context_sections(json.dumps(payload))
        assert result["theological_spine"] == "covenant fidelity"
        assert result["places"] == [VALID_PLACE]
        assert result["objects"] == [{"name": "manna"}]
        assert result["institutions"] == [{"name": "priesthood"}]
        assert result["genre_context"] == {"primary_genre": "narrative"}
        assert result["maintenance_notes"] == {"generation_notes": "ok"}

    def test_invalid_place_type_is_normalized(self):
        payload = {
            "theological_spine": "x",
            "places": [{**VALID_PLACE, "type": "garden/mythic"}],
        }
        result = _parse_and_normalize_context_sections(json.dumps(payload))
        assert result["places"][0]["type"] == "other"
        assert result["places"][0]["_legacy_type"] == "garden/mythic"

    def test_returns_empty_skeleton_on_unparseable_payload(self):
        result = _parse_and_normalize_context_sections("not json")
        assert result["theological_spine"] == ""
        assert result["places"] == []
        assert result["objects"] == []
        assert result["institutions"] == []


class TestGeneratePlaceBatchResilience:
    @pytest.mark.asyncio
    async def test_falls_back_on_output_parser_exception(self):
        from langchain_core.exceptions import OutputParserException

        bad_raw = json.dumps({"places": [{**VALID_PLACE, "type": "city/empire"}]})

        async def fake_call_llm(prompt, **kwargs):
            if kwargs.get("output_schema") is not None:
                raise OutputParserException("LLM emitted 'city/empire' which is not in enum")
            return bad_raw

        with patch(
            "app.services.book_context.generation.nodes.context_sections.call_llm",
            side_effect=fake_call_llm,
        ):
            result = await _generate_place_batch([], "Ruth")

        assert len(result) == 1
        assert result[0]["type"] == "other"
        assert result[0]["_legacy_type"] == "city/empire"


class TestGenerateContextSectionsResilience:
    @pytest.mark.asyncio
    async def test_small_path_falls_back_on_invalid_place(self):
        from langchain_core.exceptions import OutputParserException

        state = {
            "book_name": "Ruth",
            "genre": "narrative",
            "structural_outline": {},
            "discourse_threads": [],
            "bhsa_summary": "",
            "bhsa_entities": [],
            "bhsa_common_nouns": [],
            "participant_register": [],
        }
        fallback_payload = {
            "theological_spine": "loyalty across boundary",
            "places": [{**VALID_PLACE, "type": "city/empire"}],
            "objects": [],
            "institutions": [],
            "genre_context": {},
            "maintenance_notes": {},
        }

        async def fake_call_llm(prompt, **kwargs):
            if kwargs.get("output_schema") is not None:
                raise OutputParserException("invalid place type")
            return json.dumps(fallback_payload)

        with patch(
            "app.services.book_context.generation.nodes.context_sections.call_llm",
            side_effect=fake_call_llm,
        ):
            result = await generate_context_sections(state)

        assert result["theological_spine"] == "loyalty across boundary"
        assert result["places"][0]["type"] == "other"
        assert result["places"][0]["_legacy_type"] == "city/empire"
