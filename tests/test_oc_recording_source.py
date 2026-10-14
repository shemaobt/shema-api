"""A recording says where it came from.

The app never sends ``source`` and so writes ``raw``: audio the team captured in the field.
An importer outside the app says ``external`` and cites the published source. One mark on
the recording covers the audio, the classification and the storyteller link, so a reader
can tell a provisional, imported classification from one made beside the storyteller.
"""

from datetime import UTC, datetime

import inngest
import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import RecordingSource, SplittingStatus
from app.core.exceptions import SourceReferenceOnRawRecordingError
from app.db.models.oc_recording import OC_Recording
from app.models.oc_recording import (
    REFERENCE_NEEDS_EXTERNAL_SOURCE,
    RecordingCreate,
    RecordingResponse,
    RecordingUpdate,
    SplitSegment,
)
from tests.baker import (
    make_language,
    make_oc_recording,
    make_oc_taxonomy,
    make_project,
    make_user,
)

pytest.importorskip("app.inngest")
from app.inngest.audio_splitting import persist_split_segments
from app.inngest.schemas import SegmentResult, SplitRequestedPayload, SplitSegmentData
from app.services.oral_collector import recording_service, split_service

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


async def test_an_update_cannot_slip_a_citation_onto_a_raw_row(
    db_session: AsyncSession, seeded: dict[str, str]
) -> None:
    """The schema cannot see the stored row when the payload mentions one field alone;
    the service can, and refuses the row it would otherwise store."""
    recording = await recording_service.create_recording(
        db_session,
        _create(
            project_id=seeded["project_id"],
            genre_id=seeded["genre_id"],
            subcategory_id=seeded["sub_id"],
        ),
        user_id=seeded["user_id"],
    )

    with pytest.raises(SourceReferenceOnRawRecordingError):
        await recording_service.update_recording(
            db_session, recording.id, RecordingUpdate(source_reference=CITATION)
        )


async def test_an_update_cannot_turn_an_external_row_raw_while_its_citation_stays(
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

    with pytest.raises(SourceReferenceOnRawRecordingError):
        await recording_service.update_recording(
            db_session, recording.id, RecordingUpdate(source="raw")
        )

    back_to_raw = await recording_service.update_recording(
        db_session, recording.id, RecordingUpdate(source="raw", source_reference=None)
    )
    assert (back_to_raw.source, back_to_raw.source_reference) == ("raw", None)


async def test_a_split_request_snapshots_the_source_into_the_event(
    db_session: AsyncSession, seeded: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    parent = await make_oc_recording(
        db_session,
        seeded["project_id"],
        seeded["genre_id"],
        seeded["sub_id"],
        user_id=seeded["user_id"],
        gcs_url="https://example.com/parent.m4a",
        duration_seconds=60.0,
    )
    parent.source = RecordingSource.EXTERNAL
    parent.source_reference = CITATION
    await db_session.commit()

    captured: list[inngest.Event] = []

    async def fake_send(event: inngest.Event) -> list[str]:
        captured.append(event)
        return []

    monkeypatch.setattr(split_service.inngest_client, "send", fake_send)

    await split_service.request_split(
        db_session,
        parent.id,
        [SplitSegment(start_seconds=0.0, end_seconds=10.0)],
        seeded["user_id"],
    )

    assert captured[0].data["source"] == "external"
    assert captured[0].data["source_reference"] == CITATION


async def test_every_segment_of_an_external_recording_is_external_with_the_same_citation(
    db_session: AsyncSession, seeded: dict[str, str]
) -> None:
    parent = await make_oc_recording(
        db_session,
        seeded["project_id"],
        seeded["genre_id"],
        seeded["sub_id"],
        user_id=seeded["user_id"],
        gcs_url="https://example.com/parent.m4a",
        duration_seconds=60.0,
        splitting_status=SplittingStatus.SPLITTING,
    )
    payload = SplitRequestedPayload(
        recording_id=parent.id,
        user_id=seeded["user_id"],
        segments=[
            SplitSegmentData(
                start_seconds=float(i) * 10.0,
                end_seconds=float(i + 1) * 10.0,
                genre_id=seeded["genre_id"],
                subcategory_id=seeded["sub_id"],
                register_id=None,
            )
            for i in range(2)
        ],
        project_id=seeded["project_id"],
        format="m4a",
        title="Parent story",
        recorded_at=datetime.now(UTC).isoformat(),
        description=ENOUGH,
        source="external",
        source_reference=CITATION,
    )
    results = [
        SegmentResult(
            id=f"child-{i}",
            gcs_url=f"https://example.com/child-{i}.m4a",
            duration_seconds=10.0,
            file_size_bytes=10_000,
            index=i,
        )
        for i in range(2)
    ]

    new_ids = await persist_split_segments(db_session, payload, results)

    for child_id in new_ids:
        child = await db_session.get(OC_Recording, child_id)
        assert child is not None
        assert (child.source, child.source_reference) == ("external", CITATION)


def test_a_split_event_from_before_the_field_existed_still_parses_as_raw() -> None:
    """An in-flight event replayed by Inngest after the deploy carries no source; its
    parent was written by the app, so raw is its true value."""
    payload = SplitRequestedPayload(
        recording_id="r",
        user_id="u",
        segments=[],
        project_id="p",
        format="m4a",
        title="t",
        recorded_at=datetime.now(UTC).isoformat(),
    )

    assert (payload.source, payload.source_reference) == ("raw", None)
