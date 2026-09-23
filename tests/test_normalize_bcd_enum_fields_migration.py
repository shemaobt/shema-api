import importlib.util
from pathlib import Path

import pytest

MIGRATION_PATH = (
    Path(__file__).resolve().parent.parent
    / "alembic"
    / "versions"
    / "20260522_0001_normalize_bcd_enum_fields.py"
)


@pytest.fixture(scope="module")
def migration():
    spec = importlib.util.spec_from_file_location("normalize_bcd_enum_fields", MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestNormalizeList:
    def test_legacy_value_is_replaced_and_marker_is_added(self, migration):
        items = [{"type": "location", "name": "X"}]
        changed = migration._normalize_list(
            items, "type", migration.VALID_PARTICIPANT_TYPES, "named"
        )
        assert changed is True
        assert items[0]["type"] == "named"
        assert items[0]["_legacy_type"] == "location"

    def test_valid_value_is_left_untouched(self, migration):
        items = [{"type": "named", "name": "X"}]
        changed = migration._normalize_list(
            items, "type", migration.VALID_PARTICIPANT_TYPES, "named"
        )
        assert changed is False
        assert items[0] == {"type": "named", "name": "X"}

    def test_is_idempotent_on_second_run(self, migration):
        items = [{"type": "location", "name": "X"}]
        migration._normalize_list(items, "type", migration.VALID_PARTICIPANT_TYPES, "named")
        changed = migration._normalize_list(
            items, "type", migration.VALID_PARTICIPANT_TYPES, "named"
        )
        assert changed is False
        assert items[0]["type"] == "named"
        assert items[0]["_legacy_type"] == "location"

    def test_skips_non_dict_entries(self, migration):
        items = [None, "string", 42, {"type": "named"}]
        changed = migration._normalize_list(
            items, "type", migration.VALID_PARTICIPANT_TYPES, "named"
        )
        assert changed is False

    def test_handles_missing_field_as_invalid(self, migration):
        items = [{"name": "X"}]
        changed = migration._normalize_list(
            items, "type", migration.VALID_PARTICIPANT_TYPES, "named"
        )
        assert changed is True
        assert items[0]["type"] == "named"
        assert items[0]["_legacy_type"] is None

    def test_returns_false_for_non_list_input(self, migration):
        assert (
            migration._normalize_list(None, "type", migration.VALID_PARTICIPANT_TYPES, "named")
            is False
        )
        assert (
            migration._normalize_list(
                "not a list", "type", migration.VALID_PARTICIPANT_TYPES, "named"
            )
            is False
        )


class TestRestoreLegacyList:
    def test_legacy_value_is_restored(self, migration):
        items = [{"type": "named", "_legacy_type": "location", "name": "X"}]
        changed = migration._restore_legacy_list(items)
        assert changed is True
        assert items[0]["type"] == "location"
        assert "_legacy_type" not in items[0]

    def test_entry_without_marker_is_untouched(self, migration):
        items = [{"type": "named", "name": "X"}]
        changed = migration._restore_legacy_list(items)
        assert changed is False
        assert items[0] == {"type": "named", "name": "X"}

    def test_restores_both_type_and_entity_type(self, migration):
        items = [
            {
                "type": "named",
                "_legacy_type": "location",
                "entity_type": "person",
                "_legacy_entity_type": "place",
            }
        ]
        changed = migration._restore_legacy_list(items)
        assert changed is True
        assert items[0]["type"] == "location"
        assert items[0]["entity_type"] == "place"
        assert "_legacy_type" not in items[0]
        assert "_legacy_entity_type" not in items[0]


class TestRoundTrip:
    """Upgrade then downgrade should leave each entry exactly as it started."""

    def test_round_trip_preserves_original_payload(self, migration):
        original = [
            {"type": "location", "entity_type": "place", "name": "Bethlehem"},
            {"type": "named", "entity_type": "person", "name": "Naomi"},
            {"type": "weird_legacy", "entity_type": "group", "name": "Z"},
        ]
        working = [dict(entry) for entry in original]

        migration._normalize_list(working, "type", migration.VALID_PARTICIPANT_TYPES, "named")
        migration._normalize_list(
            working,
            "entity_type",
            migration.VALID_PARTICIPANT_ENTITY_TYPES,
            "person",
        )

        # Markers preserve originals
        assert working[0]["_legacy_type"] == "location"
        assert working[0]["_legacy_entity_type"] == "place"
        assert "_legacy_type" not in working[1]
        assert "_legacy_entity_type" not in working[1]
        assert working[2]["_legacy_type"] == "weird_legacy"
        assert working[2]["_legacy_entity_type"] == "group"

        migration._restore_legacy_list(working)

        assert working == original


class TestLoadJson:
    def test_returns_list_unchanged(self, migration):
        items = [{"a": 1}]
        assert migration._load_json(items) is items

    def test_returns_dict_unchanged(self, migration):
        items = {"a": 1}
        assert migration._load_json(items) is items

    def test_returns_none_unchanged(self, migration):
        assert migration._load_json(None) is None

    def test_parses_string_payload(self, migration):
        assert migration._load_json('[{"type": "named"}]') == [{"type": "named"}]
