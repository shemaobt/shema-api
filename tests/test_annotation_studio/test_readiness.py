from __future__ import annotations

from app.services.annotation_studio.readiness_service import compute_readiness
from tests.baker import make_language
from tests.test_annotation_studio.conftest import (
    add_sort,
    add_tier_a_recording,
    add_tier_b_recording,
    make_clip,
    make_pair,
    make_speaker,
    make_word,
)


async def test_tier_a_words_ready_counts_only_words_with_min_stored(db_session):
    lang = await make_language(db_session, code="taa")
    speaker = await make_speaker(db_session, lang.id, "speaker1")

    ready_word = await make_word(db_session, lang.id, "w001")
    for i in range(5):  # MIN_INSTANCES_PER_WORD = 5 stored takes → ready
        await add_tier_a_recording(
            db_session, ready_word.id, speaker.id, i, stored=True, key=f"taa/a/r{i}"
        )
    short_word = await make_word(db_session, lang.id, "w002")
    for i in range(2):  # below threshold
        await add_tier_a_recording(
            db_session, short_word.id, speaker.id, i, stored=True, key=f"taa/a/s{i}"
        )
    # A pending take must not count toward instances or readiness.
    await add_tier_a_recording(
        db_session, short_word.id, speaker.id, 9, stored=False, key="taa/a/pending"
    )

    out = await compute_readiness(db_session, lang.id)
    assert out["tier_a"]["words_total"] == 2
    assert out["tier_a"]["words_ready"] == 1
    assert out["tier_a"]["instances"] == 7  # 5 + 2 stored, pending excluded


async def test_tier_b_pair_ready_needs_both_sides(db_session):
    lang = await make_language(db_session, code="tbb")

    ready_pair = await make_pair(db_session, lang.id, 1)
    for side in ("a", "b"):
        for i in range(5):  # REPS_PER_SIDE = 5 per side
            await add_tier_b_recording(
                db_session, ready_pair.id, side, i, stored=True, key=f"tbb/{side}{i}"
            )
    half_pair = await make_pair(db_session, lang.id, 2)
    for i in range(5):  # only side a → not ready
        await add_tier_b_recording(
            db_session, half_pair.id, "a", i, stored=True, key=f"tbb/half{i}"
        )

    out = await compute_readiness(db_session, lang.id)
    assert out["tier_b"]["pairs"] == 2
    assert out["tier_b"]["pairs_ready"] == 1
    assert out["tier_b"]["recordings"] == 15


async def test_tier_c_sorted_split_by_dimension(db_session):
    lang = await make_language(db_session, code="tcc")
    clip1 = await make_clip(db_session, lang.id, 1, stored=True, key="tcc/c1")
    clip2 = await make_clip(db_session, lang.id, 2, stored=True, key="tcc/c2")
    await make_clip(db_session, lang.id, 3, stored=False, key="tcc/c3")  # pending, excluded

    await add_sort(db_session, clip1.id, "onset", "normal", "group-1")
    await add_sort(db_session, clip2.id, "coda", "normal", "group-2")
    # Unlabeled / reliability-round assignments must not count.
    await add_sort(db_session, clip1.id, "coda", "normal", None)
    await add_sort(db_session, clip2.id, "onset", "reliability", "group-x")

    out = await compute_readiness(db_session, lang.id)
    assert out["tier_c"]["clips"] == 2  # only stored clips
    assert out["tier_c"]["onset_sorted"] == 1
    assert out["tier_c"]["coda_sorted"] == 1
