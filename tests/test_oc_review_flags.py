"""Review flags on recordings (ENG-373).

The flags are persisted, not derived on read, so the thing worth testing is not that the
rule computes correctly once — it is that the stored value still tells the truth after
every write path the server has. Each integration test below drives a real service
function and asserts the state a client would actually receive afterwards.
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import ReviewFlagCode
from app.db.models.oc_recording import OC_Recording
from app.models.oc_recording import RecordingCreate, RecordingUpdate
from app.services.oral_collector.review_flags import (
    UNCLASSIFIED_GENRE_ID,
    recompute_review_flags,
)
from tests.baker import (
    make_language,
    make_oc_recording,
    make_oc_storyteller,
    make_oc_taxonomy_with_sentinel,
    make_project,
    make_user,
)
from tests.test_oc_recording_description_rule import SHARED_VECTOR

pytest.importorskip("app.inngest")

SUFFICIENT = "a description long enough to satisfy the rule"
INSUFFICIENT = "too short"


async def _seed_project(db: AsyncSession) -> str:
    lang = await make_language(db)
    project = await make_project(db, lang.id)
    return project.id


def _codes(recording: OC_Recording) -> set[str]:
    return {flag["code"] for flag in recording.review_flags}


# --- what the rule decides -------------------------------------------------------------


async def test_the_unclassified_sentinel_genre_counts_as_missing_classification(
    db_session: AsyncSession,
) -> None:
    await make_oc_taxonomy_with_sentinel(db_session)
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    recording = await make_oc_recording(
        db_session,
        project_id,
        UNCLASSIFIED_GENRE_ID,
        UNCLASSIFIED_GENRE_ID,
        user_id=user.id,
        register_id="formal",
    )

    recompute_review_flags(recording)

    assert ReviewFlagCode.MISSING_CLASSIFICATION in _codes(recording)


async def test_a_null_register_counts_as_missing_classification(db_session: AsyncSession) -> None:
    genre, sub = await make_oc_taxonomy_with_sentinel(db_session)
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    recording = await make_oc_recording(
        db_session,
        project_id,
        genre.id,
        sub.id,
        user_id=user.id,
        register_id=None,
    )

    recompute_review_flags(recording)

    assert ReviewFlagCode.MISSING_CLASSIFICATION in _codes(recording)


async def test_an_empty_register_counts_as_missing_classification(db_session: AsyncSession) -> None:
    genre, sub = await make_oc_taxonomy_with_sentinel(db_session)
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    recording = await make_oc_recording(
        db_session,
        project_id,
        genre.id,
        sub.id,
        user_id=user.id,
        register_id="",
    )

    recompute_review_flags(recording)

    assert ReviewFlagCode.MISSING_CLASSIFICATION in _codes(recording)


async def test_a_short_description_is_flagged(db_session: AsyncSession) -> None:
    genre, sub = await make_oc_taxonomy_with_sentinel(db_session)
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    recording = await make_oc_recording(
        db_session,
        project_id,
        genre.id,
        sub.id,
        user_id=user.id,
        description=INSUFFICIENT,
    )

    recompute_review_flags(recording)

    assert ReviewFlagCode.INSUFFICIENT_DESCRIPTION in _codes(recording)


@pytest.mark.parametrize(("name", "text", "_expected"), SHARED_VECTOR)
async def test_the_shared_vector_clears_the_description_flag(
    db_session: AsyncSession, name: str, text: str, _expected: int
) -> None:
    genre, sub = await make_oc_taxonomy_with_sentinel(db_session)
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    recording = await make_oc_recording(
        db_session,
        project_id,
        genre.id,
        sub.id,
        user_id=user.id,
        description=text,
    )

    recompute_review_flags(recording)

    assert ReviewFlagCode.INSUFFICIENT_DESCRIPTION not in _codes(recording), name


#: Nineteen clusters, and more than nineteen code points. Anything that counts code points
#: or UTF-16 units reads these as long enough and fails to flag them, which is the direction
#: the shared vector cannot detect: every row of that table over-counts to a number still
#: above the threshold. Each unit below is one grapheme cluster made of several code points.
JUST_BELOW_THRESHOLD = [
    ("devanagari_with_matras", "कि" * 19),
    ("emoji_zwj_family", "\U0001f468‍\U0001f469‍\U0001f467" * 19),
]


@pytest.mark.parametrize(("name", "text"), JUST_BELOW_THRESHOLD)
async def test_a_description_just_under_the_threshold_is_flagged(
    db_session: AsyncSession, name: str, text: str
) -> None:
    genre, sub = await make_oc_taxonomy_with_sentinel(db_session)
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    recording = await make_oc_recording(
        db_session,
        project_id,
        genre.id,
        sub.id,
        user_id=user.id,
        description=text,
    )

    recompute_review_flags(recording)

    assert ReviewFlagCode.INSUFFICIENT_DESCRIPTION in _codes(recording), name


async def test_a_recording_missing_everything_carries_all_three_flags(
    db_session: AsyncSession,
) -> None:
    await make_oc_taxonomy_with_sentinel(db_session)
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    recording = await make_oc_recording(
        db_session,
        project_id,
        UNCLASSIFIED_GENRE_ID,
        UNCLASSIFIED_GENRE_ID,
        user_id=user.id,
        register_id=None,
        storyteller_id=None,
        description=None,
    )

    recompute_review_flags(recording)

    assert [flag["code"] for flag in recording.review_flags] == [
        ReviewFlagCode.MISSING_CLASSIFICATION,
        ReviewFlagCode.INSUFFICIENT_DESCRIPTION,
        ReviewFlagCode.MISSING_STORYTELLER,
    ]


async def test_a_complete_recording_carries_no_flags(db_session: AsyncSession) -> None:
    genre, sub = await make_oc_taxonomy_with_sentinel(db_session)
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    storyteller = await make_oc_storyteller(
        db_session,
        project_id,
        external_acceptance_confirmed=True,
        created_by_user_id=user.id,
    )
    recording = await make_oc_recording(
        db_session,
        project_id,
        genre.id,
        sub.id,
        user_id=user.id,
        register_id="formal",
        storyteller_id=storyteller.id,
        description=SUFFICIENT,
    )

    recompute_review_flags(recording)

    assert recording.review_flags == []


# --- the flags survive every write path -------------------------------------------------


async def test_creating_a_recording_computes_its_flags(db_session: AsyncSession) -> None:
    from app.services.oral_collector import recording_service

    genre, sub = await make_oc_taxonomy_with_sentinel(db_session)
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)

    recording = await recording_service.create_recording(
        db_session,
        RecordingCreate(
            project_id=project_id,
            genre_id=genre.id,
            subcategory_id=sub.id,
            register_id="formal",
            description=SUFFICIENT,
            title="Fresh",
            duration_seconds=12.0,
            file_size_bytes=2048,
            format="m4a",
            recorded_at=datetime.now(UTC),
        ),
        user.id,
    )

    assert _codes(recording) == {ReviewFlagCode.MISSING_STORYTELLER}


async def test_creating_a_fully_specified_recording_carries_no_flags(
    db_session: AsyncSession,
) -> None:
    from app.services.oral_collector import recording_service

    genre, sub = await make_oc_taxonomy_with_sentinel(db_session)
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    storyteller = await make_oc_storyteller(
        db_session,
        project_id,
        external_acceptance_confirmed=True,
        created_by_user_id=user.id,
    )

    recording = await recording_service.create_recording(
        db_session,
        RecordingCreate(
            project_id=project_id,
            genre_id=genre.id,
            subcategory_id=sub.id,
            register_id="formal",
            storyteller_id=storyteller.id,
            description=SUFFICIENT,
            title="Complete",
            duration_seconds=12.0,
            file_size_bytes=2048,
            format="m4a",
            recorded_at=datetime.now(UTC),
        ),
        user.id,
    )

    assert recording.review_flags == []


async def test_classifying_a_recording_clears_its_classification_flag(
    db_session: AsyncSession,
) -> None:
    from app.services.oral_collector import recording_service

    genre, sub = await make_oc_taxonomy_with_sentinel(db_session)
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    recording = await make_oc_recording(
        db_session,
        project_id,
        UNCLASSIFIED_GENRE_ID,
        UNCLASSIFIED_GENRE_ID,
        user_id=user.id,
        description=SUFFICIENT,
    )
    recompute_review_flags(recording)
    await db_session.commit()
    assert ReviewFlagCode.MISSING_CLASSIFICATION in _codes(recording)

    updated = await recording_service.update_recording(
        db_session,
        recording.id,
        RecordingUpdate(genre_id=genre.id, subcategory_id=sub.id, register_id="formal"),
    )

    assert _codes(updated) == {ReviewFlagCode.MISSING_STORYTELLER}


async def test_assigning_a_storyteller_clears_its_flag(db_session: AsyncSession) -> None:
    from app.services.oral_collector import recording_service

    genre, sub = await make_oc_taxonomy_with_sentinel(db_session)
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    storyteller = await make_oc_storyteller(
        db_session,
        project_id,
        external_acceptance_confirmed=True,
        created_by_user_id=user.id,
    )
    recording = await make_oc_recording(
        db_session,
        project_id,
        genre.id,
        sub.id,
        user_id=user.id,
        register_id="formal",
        description=SUFFICIENT,
    )
    recompute_review_flags(recording)
    await db_session.commit()
    assert ReviewFlagCode.MISSING_STORYTELLER in _codes(recording)

    updated = await recording_service.update_recording(
        db_session, recording.id, RecordingUpdate(storyteller_id=storyteller.id)
    )

    assert _codes(updated) == set()


async def test_improving_the_description_clears_its_flag(db_session: AsyncSession) -> None:
    from app.services.oral_collector import recording_service

    genre, sub = await make_oc_taxonomy_with_sentinel(db_session)
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    recording = await make_oc_recording(
        db_session,
        project_id,
        genre.id,
        sub.id,
        user_id=user.id,
        register_id="formal",
        description=INSUFFICIENT,
    )
    recompute_review_flags(recording)
    await db_session.commit()
    assert ReviewFlagCode.INSUFFICIENT_DESCRIPTION in _codes(recording)

    updated = await recording_service.update_recording(
        db_session, recording.id, RecordingUpdate(description=SUFFICIENT)
    )

    assert _codes(updated) == {ReviewFlagCode.MISSING_STORYTELLER}


async def test_dropping_the_storyteller_raises_the_flag_again(db_session: AsyncSession) -> None:
    from app.services.oral_collector import recording_service

    genre, sub = await make_oc_taxonomy_with_sentinel(db_session)
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    storyteller = await make_oc_storyteller(
        db_session,
        project_id,
        external_acceptance_confirmed=True,
        created_by_user_id=user.id,
    )
    recording = await make_oc_recording(
        db_session,
        project_id,
        genre.id,
        sub.id,
        user_id=user.id,
        register_id="formal",
        storyteller_id=storyteller.id,
        description=SUFFICIENT,
    )
    recompute_review_flags(recording)
    await db_session.commit()
    assert recording.review_flags == []

    updated = await recording_service.update_recording(
        db_session, recording.id, RecordingUpdate(storyteller_id=None)
    )

    assert _codes(updated) == {ReviewFlagCode.MISSING_STORYTELLER}


async def test_clearing_the_register_raises_the_classification_flag_again(
    db_session: AsyncSession,
) -> None:
    from app.services.oral_collector import recording_service

    genre, sub = await make_oc_taxonomy_with_sentinel(db_session)
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    storyteller = await make_oc_storyteller(
        db_session,
        project_id,
        external_acceptance_confirmed=True,
        created_by_user_id=user.id,
    )
    recording = await make_oc_recording(
        db_session,
        project_id,
        genre.id,
        sub.id,
        user_id=user.id,
        register_id="formal",
        storyteller_id=storyteller.id,
        description=SUFFICIENT,
    )
    recompute_review_flags(recording)
    await db_session.commit()
    assert recording.review_flags == []

    updated = await recording_service.update_recording(
        db_session, recording.id, RecordingUpdate(register_id=None)
    )

    assert _codes(updated) == {ReviewFlagCode.MISSING_CLASSIFICATION}


async def test_an_unrelated_update_leaves_the_flags_telling_the_truth(
    db_session: AsyncSession,
) -> None:
    from app.services.oral_collector import recording_service

    genre, sub = await make_oc_taxonomy_with_sentinel(db_session)
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    recording = await make_oc_recording(
        db_session,
        project_id,
        genre.id,
        sub.id,
        user_id=user.id,
        register_id=None,
        description=SUFFICIENT,
    )
    recompute_review_flags(recording)
    await db_session.commit()

    updated = await recording_service.update_recording(
        db_session, recording.id, RecordingUpdate(title="a different title")
    )

    assert _codes(updated) == {
        ReviewFlagCode.MISSING_CLASSIFICATION,
        ReviewFlagCode.MISSING_STORYTELLER,
    }


async def test_deleting_a_storyteller_flags_the_recordings_it_leaves_behind(
    db_session: AsyncSession,
) -> None:
    from app.services.oral_collector import storyteller_service

    genre, sub = await make_oc_taxonomy_with_sentinel(db_session)
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    storyteller = await make_oc_storyteller(
        db_session,
        project_id,
        external_acceptance_confirmed=True,
        created_by_user_id=user.id,
    )
    recording = await make_oc_recording(
        db_session,
        project_id,
        genre.id,
        sub.id,
        user_id=user.id,
        register_id="formal",
        storyteller_id=storyteller.id,
        description=SUFFICIENT,
    )
    recompute_review_flags(recording)
    await db_session.commit()
    assert recording.review_flags == []

    await storyteller_service.delete_storyteller(db_session, storyteller.id, user.id)

    await db_session.refresh(recording)
    assert recording.storyteller_id is None
    assert ReviewFlagCode.MISSING_STORYTELLER in _codes(recording)


async def test_split_segments_carry_flags_of_their_own(db_session: AsyncSession) -> None:
    from app.inngest.audio_splitting import persist_split_segments
    from app.inngest.schemas import SegmentResult, SplitRequestedPayload, SplitSegmentData

    genre, sub = await make_oc_taxonomy_with_sentinel(db_session)
    user = await make_user(db_session)
    project_id = await _seed_project(db_session)
    parent = await make_oc_recording(
        db_session,
        project_id,
        genre.id,
        sub.id,
        user_id=user.id,
        register_id="formal",
        description=SUFFICIENT,
        title="Parent",
    )

    payload = SplitRequestedPayload(
        recording_id=parent.id,
        user_id=user.id,
        segments=[
            SplitSegmentData(
                start_seconds=0.0,
                end_seconds=5.0,
                genre_id=UNCLASSIFIED_GENRE_ID,
                subcategory_id=UNCLASSIFIED_GENRE_ID,
                register_id=None,
            )
        ],
        project_id=project_id,
        format="m4a",
        title="Parent",
        recorded_at=datetime.now(UTC).isoformat(),
        description=SUFFICIENT,
        storyteller_id=None,
    )
    new_ids = await persist_split_segments(
        db_session,
        payload,
        [
            SegmentResult(
                id="11111111-1111-1111-1111-111111111111",
                gcs_url="gs://bucket/child.m4a",
                duration_seconds=5.0,
                file_size_bytes=512,
                index=0,
            )
        ],
    )

    child = await db_session.get(OC_Recording, new_ids[0])
    assert child is not None
    assert _codes(child) == {
        ReviewFlagCode.MISSING_CLASSIFICATION,
        ReviewFlagCode.MISSING_STORYTELLER,
    }
