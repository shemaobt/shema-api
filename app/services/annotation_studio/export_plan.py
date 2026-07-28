"""Pure export-planning algorithm — the heart of the studio.

Turns stored recordings and sort assignments into the exact CSV rows and the
set of audio files the analysis notebooks consume. No I/O, no DB, no ffmpeg:
this is a deterministic pure function so it can be unit-tested directly against
the notebook contract.

Verified contract (`experiments/xeus_layerwise_annotated.py`):
  * Tier A: words with < 5 instances are dropped by the notebook, so we drop
    them here too and report the count.
  * Tier B: the notebook computes `n_same x n_different` triplets with no
    balancing, so we emit a balanced `same`/`different` set (~60/60).
  * Tier C: `clip_id` is matched without extension; onset uses first-half
    features, coda second-half; only confident (non-null) assignments count.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from itertools import combinations

SAME = "same"
DIFFERENT = "different"

MIN_INSTANCES_PER_WORD = 5
SAME_PER_SIDE_PER_PAIR = 2
DIFF_PER_PAIR = 2


@dataclass(frozen=True)
class TierARecordingInput:
    export_filename: str
    word_label: str
    speaker_label: str


@dataclass(frozen=True)
class TierBPairInput:
    pair_number: int
    a_files: tuple[str, ...]
    b_files: tuple[str, ...]


@dataclass(frozen=True)
class SortAssignmentInput:
    clip_id: str
    group_label: str


@dataclass(frozen=True)
class ExportInputs:
    tier_a: tuple[TierARecordingInput, ...] = ()
    tier_b: tuple[TierBPairInput, ...] = ()
    onset_normal: tuple[SortAssignmentInput, ...] = ()
    coda_normal: tuple[SortAssignmentInput, ...] = ()
    onset_reliability: tuple[SortAssignmentInput, ...] = ()
    coda_reliability: tuple[SortAssignmentInput, ...] = ()


@dataclass(frozen=True)
class ExportPlan:
    tier_a_rows: list[tuple[str, str, str]]
    tier_b_rows: list[tuple[str, str, str]]
    onset_rows: list[tuple[str, str]]
    coda_rows: list[tuple[str, str]]
    included_tier_a_files: set[str]
    included_tier_b_files: set[str]
    included_tier_c_clip_ids: set[str]
    manifest: dict


def _stride_sample(items: list, n: int) -> list:
    if n >= len(items):
        return list(items)
    if n <= 0:
        return []
    step = len(items) / n
    return [items[int(i * step)] for i in range(n)]


def _plan_tier_a(recs: tuple[TierARecordingInput, ...]) -> tuple[list, set, dict]:
    counts = Counter(r.word_label for r in recs)
    kept = {word for word, count in counts.items() if count >= MIN_INSTANCES_PER_WORD}
    rows = sorted(
        ((r.export_filename, r.word_label, r.speaker_label) for r in recs if r.word_label in kept),
        key=lambda row: (row[1], row[2], row[0]),
    )
    included = {row[0] for row in rows}
    manifest = {
        "words_total": len(counts),
        "words_kept": len(kept),
        "words_dropped_lt5": len(counts) - len(kept),
        "recordings": len(rows),
        "speakers": len({row[2] for row in rows}),
    }
    return rows, included, manifest


def _plan_tier_b(pairs: tuple[TierBPairInput, ...]) -> tuple[list, set, dict]:
    same: list[tuple[str, str, str]] = []
    diff: list[tuple[str, str, str]] = []
    for pair in pairs:
        for side_files in (sorted(pair.a_files), sorted(pair.b_files)):
            for file_a, file_b in list(combinations(side_files, 2))[:SAME_PER_SIDE_PER_PAIR]:
                same.append((file_a, file_b, SAME))
        cross = [(a, b) for a in sorted(pair.a_files) for b in sorted(pair.b_files)]
        for file_a, file_b in cross[:DIFF_PER_PAIR]:
            diff.append((file_a, file_b, DIFFERENT))

    n = min(len(same), len(diff))
    same_balanced = _stride_sample(same, n)
    diff_balanced = _stride_sample(diff, n)

    rows: list[tuple[str, str, str]] = []
    for i in range(n):
        rows.append(same_balanced[i])
        rows.append(diff_balanced[i])

    included = {file for row in rows for file in (row[0], row[1])}
    manifest = {
        "pairs": len(pairs),
        "same_rows": len(same_balanced),
        "diff_rows": len(diff_balanced),
        "triplets": len(same_balanced) * len(diff_balanced),
    }
    return rows, included, manifest


def _plan_sort_rows(assignments: tuple[SortAssignmentInput, ...]) -> list[tuple[str, str]]:
    return sorted((a.clip_id, a.group_label) for a in assignments)


def compute_agreement(
    normal: tuple[SortAssignmentInput, ...],
    reliability: tuple[SortAssignmentInput, ...],
) -> dict | None:
    normal_map = {a.clip_id: a.group_label for a in normal}
    reliability_map = {a.clip_id: a.group_label for a in reliability}
    common = set(normal_map) & set(reliability_map)
    if not common:
        return None
    matches = sum(1 for clip in common if normal_map[clip] == reliability_map[clip])
    return {"n_compared": len(common), "agreement_pct": matches / len(common)}


def build_export_plan(inputs: ExportInputs) -> ExportPlan:
    tier_a_rows, included_a, manifest_a = _plan_tier_a(inputs.tier_a)
    tier_b_rows, included_b, manifest_b = _plan_tier_b(inputs.tier_b)
    onset_rows = _plan_sort_rows(inputs.onset_normal)
    coda_rows = _plan_sort_rows(inputs.coda_normal)

    included_c = {row[0] for row in onset_rows} | {row[0] for row in coda_rows}

    manifest_c = {
        "clips": len(included_c),
        "onset_assigned": len(onset_rows),
        "coda_assigned": len(coda_rows),
        "onset_agreement": compute_agreement(inputs.onset_normal, inputs.onset_reliability),
        "coda_agreement": compute_agreement(inputs.coda_normal, inputs.coda_reliability),
    }

    tiers = []
    if tier_a_rows:
        tiers.append("A")
    if tier_b_rows:
        tiers.append("B")
    if onset_rows or coda_rows:
        tiers.append("C")

    manifest = {
        "tiers": tiers,
        "tier_a": manifest_a,
        "tier_b": manifest_b,
        "tier_c": manifest_c,
    }

    return ExportPlan(
        tier_a_rows=tier_a_rows,
        tier_b_rows=tier_b_rows,
        onset_rows=onset_rows,
        coda_rows=coda_rows,
        included_tier_a_files=included_a,
        included_tier_b_files=included_b,
        included_tier_c_clip_ids=included_c,
        manifest=manifest,
    )
