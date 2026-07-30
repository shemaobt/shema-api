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


@pytest.mark.asyncio
async def test_the_api_answers_422_and_locates_the_field() -> None:
    """Rejecting in the model is only half of it — what the client can act on is the
    response. FastAPI turns a field validator into a 422 whose `loc` names the field, so
    the app can put the message under the box the person is typing in rather than at the
    top of the form."""
    import httpx
    from fastapi import FastAPI
    from httpx import ASGITransport

    app = FastAPI()

    @app.post("/recordings")
    async def _create(payload: RecordingCreate) -> dict[str, str]:
        return {"description": payload.description}

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/recordings",
            json={
                "project_id": "p",
                "genre_id": "g",
                "subcategory_id": "s",
                "description": NOT_ENOUGH,
                "duration_seconds": 10.0,
                "file_size_bytes": 1024,
                "format": "m4a",
                "recorded_at": "2026-01-01T00:00:00Z",
            },
        )

    assert response.status_code == 422
    locations = [error["loc"] for error in response.json()["detail"]]
    assert ["body", "description"] in locations


def test_the_message_names_the_field_and_the_threshold() -> None:
    with pytest.raises(ValidationError) as caught:
        _create(description=NOT_ENOUGH)

    message = str(caught.value)
    assert "description" in message
    assert "20" in message
