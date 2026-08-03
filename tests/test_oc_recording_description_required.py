"""A recording carries a description that says something (ENG-354).

The rule itself lives in tests/test_recording_description_rule.py. This is about where it
bites: which requests it rejects, which it lets through, and which rows it deliberately
leaves alone.
"""

import pytest
from pydantic import ValidationError

from app.models.oc_recording import RecordingCreate, RecordingUpdate

ENOUGH = "a description long enough to say something"
NOT_ENOUGH = "too short"


def _create(**overrides: object) -> RecordingCreate:
    payload: dict[str, object] = {
        "project_id": "p",
        "genre_id": "g",
        "subcategory_id": "s",
        "description": ENOUGH,
        "duration_seconds": 10.0,
        "file_size_bytes": 1024,
        "format": "m4a",
        "recorded_at": "2026-01-01T00:00:00Z",
    }
    payload.update(overrides)
    return RecordingCreate(**payload)  # type: ignore[arg-type]


def test_a_new_recording_needs_a_description() -> None:
    with pytest.raises(ValidationError) as caught:
        _create(description=None)

    assert "description" in str(caught.value)


def test_a_new_recording_needs_the_description_field_at_all() -> None:
    """Omitting it must not be a way around the rule the way passing null is not."""
    payload = {
        "project_id": "p",
        "genre_id": "g",
        "subcategory_id": "s",
        "duration_seconds": 10.0,
        "file_size_bytes": 1024,
        "format": "m4a",
        "recorded_at": "2026-01-01T00:00:00Z",
    }

    with pytest.raises(ValidationError) as caught:
        RecordingCreate(**payload)  # type: ignore[arg-type]

    assert "description" in str(caught.value)


def test_a_short_description_is_rejected_on_create() -> None:
    with pytest.raises(ValidationError) as caught:
        _create(description=NOT_ENOUGH)

    assert "description" in str(caught.value)


def test_a_sufficient_description_is_accepted_on_create() -> None:
    assert _create().description == ENOUGH


def test_a_short_description_is_rejected_on_update() -> None:
    with pytest.raises(ValidationError) as caught:
        RecordingUpdate(description=NOT_ENOUGH)

    assert "description" in str(caught.value)


def test_clearing_a_description_is_rejected_on_update() -> None:
    """Null would otherwise be the way to get back to a recording with no description,
    which is the state the rule exists to prevent."""
    with pytest.raises(ValidationError):
        RecordingUpdate(description=None)


def test_an_update_that_does_not_mention_the_description_is_left_alone() -> None:
    """This is the whole of the grandfathering. Rows written before the rule keep short
    or absent descriptions, and editing anything else about them must not fail — there is
    no migration and no NOT NULL, so the old data is still out there."""
    update = RecordingUpdate(title="a new title")

    assert "description" not in update.model_fields_set
    assert update.model_dump(exclude_unset=True) == {"title": "a new title"}


def test_the_published_schema_does_not_offer_a_null_it_would_reject() -> None:
    """The generated contract is what a client is built from, so a type it advertises and
    then refuses is the same defect this rule exists to close, moved from the length to
    the schema: the caller sends what the contract allows and takes a 422 that the
    contract never mentioned.

    `description` stays optional on update — omitting it is how you edit a grandfathered
    recording without touching the field — but it is not nullable, because null is the
    one value the validator will not accept.
    """
    for model in (RecordingCreate, RecordingUpdate):
        schema = model.model_json_schema()["properties"]["description"]

        assert schema.get("type") == "string", model.__name__
        assert "anyOf" not in schema, model.__name__


def test_the_description_is_required_to_create_and_optional_to_update() -> None:
    """The asymmetry is the grandfathering, stated in the contract rather than only in a
    validator: a new recording must carry one, an edit of an old one need not mention it."""
    assert "description" in RecordingCreate.model_json_schema()["required"]
    assert "description" not in RecordingUpdate.model_json_schema().get("required", [])


def test_the_message_names_the_field_and_the_threshold() -> None:
    with pytest.raises(ValidationError) as caught:
        _create(description=NOT_ENOUGH)

    message = str(caught.value)
    assert "description" in message
    assert "20" in message
