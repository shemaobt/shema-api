import json
from unittest.mock import patch

import pytest

from app.services.book_context.generation.nodes.participants import (
    _generate_batch,
    _parse_and_normalize_participants,
)

VALID_PARTICIPANT = {
    "name": "Naomi",
    "english_gloss": "pleasant",
    "entity_type": "person",
    "type": "named",
    "entry_verse": {"chapter": 1, "verse": 1},
    "role_in_book": "protagonist",
}


class TestParseAndNormalizeParticipants:
    def test_valid_payload_passes_through(self):
        raw = json.dumps({"participants": [VALID_PARTICIPANT]})
        result = _parse_and_normalize_participants(raw)
        assert result == [VALID_PARTICIPANT]

    def test_invalid_type_is_normalized_to_named(self):
        bad = {**VALID_PARTICIPANT, "type": "location"}
        raw = json.dumps({"participants": [bad]})
        result = _parse_and_normalize_participants(raw)
        assert result[0]["type"] == "named"
        assert result[0]["_legacy_type"] == "location"

    def test_invalid_entity_type_is_normalized_to_person(self):
        bad = {**VALID_PARTICIPANT, "entity_type": "group"}
        raw = json.dumps({"participants": [bad]})
        result = _parse_and_normalize_participants(raw)
        assert result[0]["entity_type"] == "person"
        assert result[0]["_legacy_entity_type"] == "group"

    def test_strips_markdown_fences(self):
        raw = "```json\n" + json.dumps({"participants": [VALID_PARTICIPANT]}) + "\n```"
        result = _parse_and_normalize_participants(raw)
        assert result == [VALID_PARTICIPANT]

    def test_handles_bare_list_fallback(self):
        """LLM occasionally returns the list directly instead of wrapping it."""
        raw = json.dumps([VALID_PARTICIPANT])
        result = _parse_and_normalize_participants(raw)
        assert result == [VALID_PARTICIPANT]

    def test_returns_empty_list_on_unparseable_payload(self):
        result = _parse_and_normalize_participants("not json at all")
        assert result == []


class TestGenerateBatchResilience:
    @pytest.fixture
    def state(self):
        return {
            "book_name": "Ruth",
            "structural_outline": {},
            "bhsa_summary": "",
        }

    @pytest.mark.asyncio
    async def test_falls_back_to_raw_parse_on_output_parser_exception(self, state):
        """LangChain's structured_output raises OutputParserException on bad payloads."""
        from langchain_core.exceptions import OutputParserException

        bad_payload_raw = json.dumps({"participants": [{**VALID_PARTICIPANT, "type": "location"}]})

        async def fake_call_llm(prompt, **kwargs):
            if kwargs.get("output_schema") is not None:
                raise OutputParserException("LLM emitted 'location' which is not in enum")
            return bad_payload_raw

        with patch(
            "app.services.book_context.generation.nodes.participants.call_llm",
            side_effect=fake_call_llm,
        ):
            result = await _generate_batch([], state, "{}", "[]")

        assert len(result) == 1
        assert result[0]["type"] == "named"
        assert result[0]["_legacy_type"] == "location"

    @pytest.mark.asyncio
    async def test_falls_back_to_raw_parse_on_pydantic_validation_error(self, state):
        """A bare ValidationError (defensive coverage) also triggers the fallback."""
        from pydantic import ValidationError

        bad_payload_raw = json.dumps({"participants": [{**VALID_PARTICIPANT, "type": "location"}]})

        async def fake_call_llm(prompt, **kwargs):
            if kwargs.get("output_schema") is not None:
                raise ValidationError.from_exception_data(
                    "ParticipantRegisterSchema", line_errors=[]
                )
            return bad_payload_raw

        with patch(
            "app.services.book_context.generation.nodes.participants.call_llm",
            side_effect=fake_call_llm,
        ):
            result = await _generate_batch([], state, "{}", "[]")

        assert len(result) == 1
        assert result[0]["type"] == "named"

    @pytest.mark.asyncio
    async def test_passes_through_when_structured_output_succeeds(self, state):
        """When the LLM returns a valid structured payload, the fallback is not used."""
        from app.services.book_context.generation.schemas import (
            ParticipantRegisterSchema,
            ParticipantSchema,
        )

        async def fake_call_llm(prompt, *, output_schema=None, settings=None):
            if output_schema is ParticipantRegisterSchema:
                return ParticipantRegisterSchema(
                    participants=[ParticipantSchema(**VALID_PARTICIPANT)]
                )
            raise AssertionError("fallback should not be triggered")

        with patch(
            "app.services.book_context.generation.nodes.participants.call_llm",
            side_effect=fake_call_llm,
        ):
            result = await _generate_batch([], state, "{}", "[]")

        assert len(result) == 1
        assert result[0]["type"] == "named"
        assert "_legacy_type" not in result[0]
