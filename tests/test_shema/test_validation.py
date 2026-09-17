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

from app.db.models.shema_enums import ShemaPrayerVisibility
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


def test_a_visibility_the_vocabulary_does_not_have_is_refused_by_the_shape() -> None:
    """``publico`` is not one of the two, and the shape is where that has to be said.

    ``status`` and ``needs_pastoral_intervention`` beside it already carry their enums; a
    plain ``str`` here would let the payload through and let the database raise instead —
    on the one field this module argues the hardest about.
    """
    with pytest.raises(ValidationError):
        ShemaProjectUpdate(prayer_visibility="publico")
    assert ShemaProjectUpdate(prayer_visibility="rede").prayer_visibility is (
        ShemaPrayerVisibility.REDE
    )


@pytest.mark.parametrize("key", ["ywamBase", "ywam_base"])
def test_the_base_is_folded_into_the_column_it_shares_with_the_team(key: str) -> None:
    """BE-02 collapsed the two columns; FE-44 §5.1's *one input* is the key being folded."""
    patch = ShemaProjectUpdate(**{key: "YWAM Sydney"})
    assert patch.team == "YWAM Sydney"
    assert patch.model_fields_set == {"team"}


def test_the_base_and_the_team_disagreeing_is_refused_and_not_reconciled() -> None:
    """Picking one silently is how the drift BE-02 removed comes back."""
    with pytest.raises(ValidationError):
        ShemaProjectUpdate(ywamBase="YWAM Sydney", team="YWAM Porto Velho")


@pytest.mark.parametrize("wrong", [[], {}, 7], ids=["list", "dict", "number"])
def test_a_base_of_the_wrong_type_is_a_validation_error_and_not_a_crash(wrong: object) -> None:
    """A ``before`` validator is handed the raw body, and only ``ValueError`` becomes a 422.

    Comparing the two values is what keeps that true: gathering them into a set raises
    ``TypeError`` on anything unhashable, which Pydantic does not translate — so
    ``{"ywamBase": []}`` was answered with a 500 instead of the ``team`` type error it earns.
    """
    with pytest.raises(ValidationError):
        ShemaProjectUpdate(ywamBase=wrong)
