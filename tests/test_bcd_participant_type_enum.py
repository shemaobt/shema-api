import pytest
from pydantic import ValidationError

from app.models.book_context import (
    BCDParticipantEntry,
    BCDPlace,
    ParticipantEntityType,
    ParticipantType,
    PlaceType,
)
from app.services.book_context.generation.schemas import ParticipantSchema


def _minimal_participant(**overrides):
    base = {
        "name": "Naomi",
        "entry_verse": {"chapter": 1, "verse": 1},
        "role_in_book": "protagonist",
    }
    base.update(overrides)
    return base


def _minimal_place(**overrides):
    base = {
        "name": "Bethlehem",
        "first_appears": {"chapter": 1, "verse": 1},
    }
    base.update(overrides)
    return base


class TestParticipantType:
    @pytest.mark.parametrize(
        "value",
        ["named", "unnamed", "group", "divine", "role"],
    )
    def test_accepts_every_enum_value(self, value):
        entry = BCDParticipantEntry.model_validate(_minimal_participant(type=value))
        assert entry.type == ParticipantType(value)

    @pytest.mark.parametrize(
        "value",
        ["location", "place", "animal", "object", "concept", ""],
    )
    def test_rejects_out_of_enum_values(self, value):
        with pytest.raises(ValidationError):
            BCDParticipantEntry.model_validate(_minimal_participant(type=value))

    def test_defaults_to_named(self):
        entry = BCDParticipantEntry.model_validate(_minimal_participant())
        assert entry.type == ParticipantType.NAMED

    def test_accepts_normalized_payload_with_legacy_type_marker(self):
        """Post-migration data carries `_legacy_type` alongside a valid `type`."""
        payload = _minimal_participant(type="named", _legacy_type="location")
        entry = BCDParticipantEntry.model_validate(payload)
        assert entry.type == ParticipantType.NAMED
        # extra=allow preserves the marker for downgrade restore
        assert entry.model_dump()["_legacy_type"] == "location"


class TestParticipantEntityType:
    @pytest.mark.parametrize("value", ["person", "person_common", "ambiguous"])
    def test_accepts_every_enum_value(self, value):
        entry = BCDParticipantEntry.model_validate(_minimal_participant(entity_type=value))
        assert entry.entity_type == ParticipantEntityType(value)

    @pytest.mark.parametrize(
        "value",
        ["place", "object", "animal", "group", ""],
    )
    def test_rejects_out_of_enum_values(self, value):
        with pytest.raises(ValidationError):
            BCDParticipantEntry.model_validate(_minimal_participant(entity_type=value))

    def test_defaults_to_person(self):
        entry = BCDParticipantEntry.model_validate(_minimal_participant())
        assert entry.entity_type == ParticipantEntityType.PERSON


class TestPlaceType:
    @pytest.mark.parametrize(
        "value",
        [
            "city",
            "country",
            "region",
            "district",
            "empire",
            "village",
            "mountain",
            "valley",
            "river",
            "well",
            "field",
            "road",
            "gate",
            "tower",
            "wall",
            "structure",
            "other",
        ],
    )
    def test_accepts_every_enum_value(self, value):
        place = BCDPlace.model_validate(_minimal_place(type=value))
        assert place.type == PlaceType(value)

    @pytest.mark.parametrize(
        "value",
        ["named", "person", "animal", "concept", "city/empire", "place", "building", "house"],
    )
    def test_rejects_out_of_enum_values(self, value):
        with pytest.raises(ValidationError):
            BCDPlace.model_validate(_minimal_place(type=value))

    def test_defaults_to_other(self):
        place = BCDPlace.model_validate(_minimal_place())
        assert place.type == PlaceType.OTHER

    def test_accepts_normalized_payload_with_legacy_type_marker(self):
        payload = _minimal_place(type="other", _legacy_type="weird_legacy_value")
        place = BCDPlace.model_validate(payload)
        assert place.type == PlaceType.OTHER
        assert place.model_dump()["_legacy_type"] == "weird_legacy_value"


class TestParticipantSchemaLLM:
    """Schema used as `output_schema` for the LLM in participants generation."""

    @pytest.mark.parametrize(
        "value",
        ["named", "unnamed", "group", "divine", "role"],
    )
    def test_accepts_every_enum_value(self, value):
        entry = ParticipantSchema.model_validate(_minimal_participant(type=value))
        assert entry.type == ParticipantType(value)

    @pytest.mark.parametrize(
        "value",
        ["location", "place", "animal", "object", "concept"],
    )
    def test_rejects_out_of_enum_values(self, value):
        with pytest.raises(ValidationError):
            ParticipantSchema.model_validate(_minimal_participant(type=value))

    @pytest.mark.parametrize("value", ["person", "person_common"])
    def test_entity_type_accepts_every_enum_value(self, value):
        entry = ParticipantSchema.model_validate(_minimal_participant(entity_type=value))
        assert entry.entity_type == ParticipantEntityType(value)

    def test_entity_type_rejects_out_of_enum(self):
        with pytest.raises(ValidationError):
            ParticipantSchema.model_validate(_minimal_participant(entity_type="place"))
