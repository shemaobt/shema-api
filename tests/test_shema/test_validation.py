"""The four fields a save is refused for, and the three keys the org chart owns.

Both rules are in ``app/models/shema.py`` and not in the database, and the reason is the
same fact in two directions: ``bridge_language`` is empty on all 127 export records and
``objective`` on 23, so a ``CHECK`` expressing *required to save* would refuse the seed on
its first row — while the console really does refuse a save that leaves one of the four
blank. The rule belongs to the write path, and this is where it is watched.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.shema import REQUIRED_TO_SAVE, ShemaProjectCreate, ShemaProjectUpdate

VALID = {
    "id": "afrikaans-kaaps",
    "language_name": "Afrikaans: Kaaps",
    "bridge_language": "Português",
    "team": "YWAM Sydney",
    "objective": ["Bíblia Completa"],
}


def test_a_create_needs_the_four_and_accepts_everything_else_empty() -> None:
    record = ShemaProjectCreate(**VALID)
    assert record.location is None
    assert record.deadline is None
    assert record.speaker_count is None


@pytest.mark.parametrize("missing", REQUIRED_TO_SAVE)
def test_a_create_without_one_of_the_four_is_refused(missing: str) -> None:
    payload = {k: v for k, v in VALID.items() if k != missing}
    with pytest.raises(ValidationError):
        ShemaProjectCreate(**payload)


@pytest.mark.parametrize("blank", REQUIRED_TO_SAVE)
def test_a_create_that_sends_one_of_the_four_empty_is_refused(blank: str) -> None:
    payload = dict(VALID)
    payload[blank] = [] if blank == "objective" else ""
    with pytest.raises(ValidationError):
        ShemaProjectCreate(**payload)


def test_the_fifth_field_is_not_required() -> None:
    """A schema that asks for ``location`` makes 127 existing records unsaveable."""
    assert len(REQUIRED_TO_SAVE) == 4
    assert "location" not in REQUIRED_TO_SAVE
    assert "deadline" not in REQUIRED_TO_SAVE
    assert "speaker_count" not in REQUIRED_TO_SAVE


def test_a_patch_may_touch_none_of_the_four() -> None:
    patch = ShemaProjectUpdate(status_comments="visitou a aldeia em maio")
    assert patch.language_name is None
    assert patch.status_comments == "visitou a aldeia em maio"


@pytest.mark.parametrize("blank", REQUIRED_TO_SAVE)
def test_a_patch_may_not_blank_one_of_the_four(blank: str) -> None:
    """Leaving it out is *unchanged*; sending it empty is the save the console refuses."""
    with pytest.raises(ValidationError):
        ShemaProjectUpdate(**{blank: [] if blank == "objective" else ""})


@pytest.mark.parametrize("key", ["regional_coordinator", "obtLabPerson", "resource_circle_person"])
def test_a_write_that_fills_a_role_holder_is_refused_by_name(key: str) -> None:
    """*Extra field not permitted* is true and useless to somebody holding the contract."""
    with pytest.raises(ValidationError) as raised:
        ShemaProjectUpdate(**{key: "Joana"})
    assert "org chart" in str(raised.value)


def test_a_write_may_not_invent_a_column() -> None:
    with pytest.raises(ValidationError):
        ShemaProjectUpdate(sensitivity_level="high")


def test_nothing_writes_the_derived_or_the_seeded_fields() -> None:
    """``region_key`` has one owner, and ``source`` is what a seed left behind."""
    fields = set(ShemaProjectCreate.model_fields)
    assert fields.isdisjoint(
        {"region_key", "source", "approved_units_unverified", "created_at", "updated_at"}
    )


def test_the_record_write_cannot_report_a_team_as_assessed() -> None:
    """The flat health fields are a projection; ``recordAssessment`` is their only writer."""
    fields = set(ShemaProjectCreate.model_fields)
    assert fields.isdisjoint(
        {
            "health_emotional",
            "health_relational",
            "health_spiritual",
            "health_physical",
            "health_assessment_date",
            "health_assessor",
            "health_notes",
        }
    )


def test_not_sending_a_prayer_request_is_not_erasing_it() -> None:
    """An unconditional write of ``""`` on every save deletes an existing request."""
    patch = ShemaProjectUpdate(status_comments="nada de novo")
    assert "prayer_requests" not in patch.model_dump(exclude_unset=True)
    assert patch.prayer_requests is None


def test_a_record_may_carry_more_translated_than_total() -> None:
    """``156/25`` is a real record. The scope is what is wrong in it, not the count."""
    patch = ShemaProjectUpdate(total_units=25, translated_units=156)
    assert patch.translated_units == 156
