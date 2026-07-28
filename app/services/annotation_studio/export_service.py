from __future__ import annotations

import csv
import io
import json
import zipfile
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.as_enums import AsExportStatus as ExportStatus
from app.core.as_enums import AsSortDimension as SortDimension
from app.core.as_enums import AsSortRound as SortRound
from app.core.as_enums import AsUploadStatus as UploadStatus
from app.db.models.as_export import AsExport
from app.db.models.as_speaker import AsSpeaker
from app.db.models.as_tier_a import AsTierARecording, AsTierAWord
from app.db.models.as_tier_b import AsTierBPair, AsTierBRecording
from app.db.models.as_tier_c import AsTierCClip, AsTierCSortAssignment
from app.services.annotation_studio import storage
from app.services.annotation_studio.common import get_or_404
from app.services.annotation_studio.export_plan import (
    ExportInputs,
    ExportPlan,
    SortAssignmentInput,
    TierARecordingInput,
    TierBPairInput,
    build_export_plan,
)
from app.services.annotation_studio.naming import export_bundle_key
from app.services.language.get_language_or_404 import get_language_or_404


def _csv_text(header: list[str], rows: list[tuple]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    writer.writerows(rows)
    return buffer.getvalue()


def _config_hint(root: str, plan: ExportPlan) -> dict:
    hint: dict[str, str] = {"output_dir": "./results_layerwise_annotated/"}
    if plan.tier_a_rows:
        hint["tier_a_dir"] = f"{root}/tier_a_words"
        hint["tier_a_csv"] = f"{root}/repeated_words.csv"
    if plan.tier_b_rows:
        hint["tier_b_dir"] = f"{root}/tier_b_pairs"
        hint["tier_b_csv"] = f"{root}/minimal_pairs.csv"
    if plan.onset_rows or plan.coda_rows:
        hint["tier_c_clips_dir"] = f"{root}/tier_c_clips"
        if plan.onset_rows:
            hint["tier_c_onsets_csv"] = f"{root}/onset_groups.csv"
        if plan.coda_rows:
            hint["tier_c_codas_csv"] = f"{root}/coda_groups.csv"
    return hint


def _assemble_zip(
    code: str,
    plan: ExportPlan,
    a_map: dict[str, str],
    b_map: dict[str, str],
    c_map: dict[str, tuple[str, str]],
) -> bytes:
    root = f"{code}_export"
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            f"{root}/repeated_words.csv",
            _csv_text(["file", "word_label", "speaker"], plan.tier_a_rows),
        )
        zf.writestr(
            f"{root}/minimal_pairs.csv",
            _csv_text(["file_a", "file_b", "same_phoneme"], plan.tier_b_rows),
        )
        if plan.onset_rows:
            zf.writestr(
                f"{root}/onset_groups.csv",
                _csv_text(["clip_id", "onset_group"], plan.onset_rows),
            )
        if plan.coda_rows:
            zf.writestr(
                f"{root}/coda_groups.csv",
                _csv_text(["clip_id", "coda_group"], plan.coda_rows),
            )
        for filename in sorted(plan.included_tier_a_files):
            zf.writestr(f"{root}/tier_a_words/{filename}", storage.get_bytes(a_map[filename]))
        for filename in sorted(plan.included_tier_b_files):
            zf.writestr(f"{root}/tier_b_pairs/{filename}", storage.get_bytes(b_map[filename]))
        for clip_id in sorted(plan.included_tier_c_clip_ids):
            filename, key = c_map[clip_id]
            zf.writestr(f"{root}/tier_c_clips/{filename}", storage.get_bytes(key))
        manifest = {
            **plan.manifest,
            "language_code": code,
            "notebook_config": _config_hint(root, plan),
        }
        zf.writestr(f"{root}/manifest.json", json.dumps(manifest, indent=2))
    return out.getvalue()


async def _gather(
    db: AsyncSession, language_id: str
) -> tuple[ExportInputs, dict[str, str], dict[str, str], dict[str, tuple[str, str]]]:
    tier_a_rows = await db.execute(
        select(AsTierARecording, AsTierAWord, AsSpeaker)
        .join(AsTierAWord, AsTierARecording.word_id == AsTierAWord.id)
        .join(AsSpeaker, AsTierARecording.speaker_id == AsSpeaker.id)
        .where(
            AsTierAWord.language_id == language_id,
            AsTierARecording.upload_status == UploadStatus.STORED.value,
        )
    )
    tier_a: list[TierARecordingInput] = []
    a_map: dict[str, str] = {}
    for rec, word, speaker in tier_a_rows.all():
        # word_label is the researcher-readable gloss when set, else the auto slug (word001);
        # this is both the export <5-instance grouping key and the notebook's grouping label.
        tier_a.append(
            TierARecordingInput(rec.export_filename, word.gloss or word.label, speaker.label)
        )
        a_map[rec.export_filename] = rec.storage_key

    pairs = (
        (
            await db.execute(
                select(AsTierBPair)
                .where(AsTierBPair.language_id == language_id)
                .order_by(AsTierBPair.pair_number)
            )
        )
        .scalars()
        .all()
    )
    b_recs = await db.execute(
        select(AsTierBRecording)
        .join(AsTierBPair, AsTierBRecording.pair_id == AsTierBPair.id)
        .where(
            AsTierBPair.language_id == language_id,
            AsTierBRecording.upload_status == UploadStatus.STORED.value,
        )
    )
    by_pair: dict[str, dict[str, list]] = defaultdict(lambda: {"a": [], "b": []})
    b_map: dict[str, str] = {}
    for rec in b_recs.scalars().all():
        by_pair[rec.pair_id][rec.side].append(rec)
        b_map[rec.export_filename] = rec.storage_key
    tier_b: list[TierBPairInput] = []
    for pair in pairs:
        group = by_pair.get(pair.id)
        if not group:
            continue
        a_files = tuple(r.export_filename for r in sorted(group["a"], key=lambda r: r.rep_index))
        b_files = tuple(r.export_filename for r in sorted(group["b"], key=lambda r: r.rep_index))
        tier_b.append(TierBPairInput(pair.pair_number, a_files, b_files))

    sort_rows = await db.execute(
        select(AsTierCSortAssignment, AsTierCClip)
        .join(AsTierCClip, AsTierCSortAssignment.clip_id == AsTierCClip.id)
        .where(
            AsTierCClip.language_id == language_id,
            AsTierCClip.upload_status == UploadStatus.STORED.value,
        )
    )
    onset_n, coda_n, onset_r, coda_r = [], [], [], []
    c_map: dict[str, tuple[str, str]] = {}
    for assignment, clip in sort_rows.all():
        if assignment.group_label is None:
            continue
        item = SortAssignmentInput(clip.export_clip_id, assignment.group_label)
        c_map[clip.export_clip_id] = (clip.export_filename, clip.storage_key)
        is_onset = assignment.dimension == SortDimension.ONSET.value
        is_normal = assignment.round == SortRound.NORMAL.value
        if is_onset and is_normal:
            onset_n.append(item)
        elif not is_onset and is_normal:
            coda_n.append(item)
        elif is_onset:
            onset_r.append(item)
        else:
            coda_r.append(item)

    inputs = ExportInputs(
        tier_a=tuple(tier_a),
        tier_b=tuple(tier_b),
        onset_normal=tuple(onset_n),
        coda_normal=tuple(coda_n),
        onset_reliability=tuple(onset_r),
        coda_reliability=tuple(coda_r),
    )
    return inputs, a_map, b_map, c_map


async def list_exports(db: AsyncSession, language_id: str) -> list[AsExport]:
    rows = await db.execute(
        select(AsExport)
        .where(AsExport.language_id == language_id)
        .order_by(AsExport.created_at.desc())
    )
    return list(rows.scalars().all())


async def get_export(db: AsyncSession, export_id: str) -> AsExport:
    return await get_or_404(db, AsExport, export_id, "Export")


async def delete_export(db: AsyncSession, export_id: str) -> None:
    export = await get_or_404(db, AsExport, export_id, "Export")
    bundle_key = export.bundle_key
    await db.delete(export)
    await db.commit()
    # Delete the bundle after the commit so a failed commit can't orphan the row.
    if bundle_key:
        storage.delete(bundle_key)


async def download_url(db: AsyncSession, export_id: str) -> str | None:
    """A signed GET URL for the finished bundle, or None if not ready."""
    export = await get_or_404(db, AsExport, export_id, "Export")
    if export.status != ExportStatus.READY.value or not export.bundle_key:
        return None
    return storage.presign_get(export.bundle_key)


async def build_export(db: AsyncSession, language_id: str, created_by: str | None) -> AsExport:
    language = await get_language_or_404(db, language_id)
    inputs, a_map, b_map, c_map = await _gather(db, language_id)
    plan = build_export_plan(inputs)

    export = AsExport(
        language_id=language_id,
        status=ExportStatus.BUILDING.value,
        created_by=created_by,
    )
    db.add(export)
    await db.commit()
    await db.refresh(export)

    try:
        data = await run_in_threadpool(_assemble_zip, language.code, plan, a_map, b_map, c_map)
        bundle_key = export_bundle_key(language.code, export.id)
        await run_in_threadpool(storage.put_object, bundle_key, data, "application/zip")
        export.status = ExportStatus.READY.value
        export.bundle_key = bundle_key
        export.manifest_json = json.dumps(plan.manifest)
        export.tiers_included = ",".join(plan.manifest["tiers"])
        export.size_bytes = len(data)
    except Exception as exc:
        export.status = ExportStatus.FAILED.value
        export.error_reason = str(exc)
    await db.commit()
    await db.refresh(export)
    return export
