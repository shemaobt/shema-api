"""A recording says where it came from.

The app never sends ``source`` and so writes ``raw``: audio the team captured in the field.
An importer outside the app says ``external`` and cites the published source. One mark on
the recording covers the audio, the classification and the storyteller link, so a reader
can tell a provisional, imported classification from one made beside the storyteller.
"""

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import RecordingSource
from app.models.oc_recording import (
    REFERENCE_NEEDS_EXTERNAL_SOURCE,
    RecordingCreate,
    RecordingResponse,
    RecordingUpdate,
)
from tests.baker import make_language, make_oc_taxonomy, make_project, make_user

pytest.importorskip("app.inngest")
recording_service = pytest.importorskip("app.services.oral_collector.recording_service")

ENOUGH = "a description long enough to say something"
CITATION = "SIL Language & Culture Archives 93407, Siko's Stories (2022), catalogue JAR0001"


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


def test_a_recording_the_app_sends_is_raw_without_saying_so() -> None:
    created = _create()

    assert created.source is RecordingSource.RAW
    assert created.source_reference is None


def test_an_importer_can_say_external_and_cite_the_source() -> None:
    created = _create(source="external", source_reference=CITATION)

    assert created.source is RecordingSource.EXTERNAL
    assert created.source_reference == CITATION


def test_a_third_kind_of_source_is_refused() -> None:
    with pytest.raises(ValidationError) as caught:
        _create(source="verified")

    assert "source" in str(caught.value)


def test_a_citation_on_a_raw_recording_is_refused() -> None:
    """A field recording has no published source to cite, so a reference without
    ``external`` is a contradiction, not a convenience."""
    with pytest.raises(ValidationError) as caught:
        _create(source_reference=CITATION)

    assert REFERENCE_NEEDS_EXTERNAL_SOURCE in str(caught.value)


def test_an_external_recording_may_leave_the_citation_blank() -> None:
    assert _create(source="external").source_reference is None


def test_an_update_that_does_not_mention_the_source_leaves_it_alone() -> None:
    update = RecordingUpdate(title="a new title")

    assert "source" not in update.model_fields_set
    assert update.model_dump(exclude_unset=True) == {"title": "a new title"}


def test_an_update_can_correct_a_row_to_external_with_its_citation() -> None:
    update = RecordingUpdate(source="external", source_reference=CITATION)

    assert update.model_dump(exclude_unset=True) == {
        "source": RecordingSource.EXTERNAL,
        "source_reference": CITATION,
    }


def test_an_update_that_sets_raw_and_a_citation_together_is_refused() -> None:
    with pytest.raises(ValidationError) as caught:
        RecordingUpdate(source="raw", source_reference=CITATION)

    assert REFERENCE_NEEDS_EXTERNAL_SOURCE in str(caught.value)


def test_the_published_schema_offers_exactly_the_two_sources() -> None:
    schema = RecordingCreate.model_json_schema()
    source = schema["properties"]["source"]
    enum = schema["$defs"][source["$ref"].rsplit("/", 1)[1]]["enum"]

    assert enum == ["raw", "external"]
    assert source["default"] == "raw"
    assert "source" not in schema["required"]


@pytest.fixture
async def seeded(db_session: AsyncSession) -> dict[str, str]:
    lang = await make_language(db_session)
    project = await make_project(db_session, lang.id)
    user = await make_user(db_session)
    genre, sub = await make_oc_taxonomy(db_session)
    return {"project_id": project.id, "user_id": user.id, "genre_id": genre.id, "sub_id": sub.id}


async def test_the_service_writes_raw_when_the_app_says_nothing(
    db_session: AsyncSession, seeded: dict[str, str]
) -> None:
    recording = await recording_service.create_recording(
        db_session,
        _create(
            project_id=seeded["project_id"],
            genre_id=seeded["genre_id"],
            subcategory_id=seeded["sub_id"],
        ),
        user_id=seeded["user_id"],
    )

    assert recording.source == RecordingSource.RAW
    assert recording.source_reference is None
    assert RecordingResponse.model_validate(recording).source == "raw"


async def test_the_service_keeps_an_external_source_and_its_citation(
    db_session: AsyncSession, seeded: dict[str, str]
) -> None:
    recording = await recording_service.create_recording(
        db_session,
        _create(
            project_id=seeded["project_id"],
            genre_id=seeded["genre_id"],
            subcategory_id=seeded["sub_id"],
            source="external",
            source_reference=CITATION,
        ),
        user_id=seeded["user_id"],
    )
    served = RecordingResponse.model_validate(recording)

    assert (served.source, served.source_reference) == ("external", CITATION)


async def test_an_update_can_turn_a_raw_row_into_an_external_one(
    db_session: AsyncSession, seeded: dict[str, str]
) -> None:
    recording = await recording_service.create_recording(
        db_session,
        _create(
            project_id=seeded["project_id"],
            genre_id=seeded["genre_id"],
            subcategory_id=seeded["sub_id"],
        ),
        user_id=seeded["user_id"],
    )

    updated = await recording_service.update_recording(
        db_session, recording.id, RecordingUpdate(source="external", source_reference=CITATION)
    )

    assert (updated.source, updated.source_reference) == ("external", CITATION)
