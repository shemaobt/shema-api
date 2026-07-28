"""Import the Terena "ruth" acousteme corpus into the backend for Beads.

Reads the corpus JSON produced by
``tripod-lab/backend/scripts/tokenize_ruth_pilot.py`` (keyed by audio basename
-> {units, timestamps, duration_sec, num_frames, source_object}), converts each
per-frame ``units`` array into RLE ``segments`` (what the Beads frontend
consumes), and stores one acousteme artifact per audio via
``acousteme_service.store_artifact`` — gzipping + uploading the stream to the
terena-pilot bucket and upserting the pointer row.

    uv run python scripts/import_ruth_acoustemes.py \
        --corpus gs://terena-pilot/acoustemes-raw/ruth_corpus.json

The audios themselves are already in gs://terena-pilot/ruth/; this only writes
the acousteme streams + DB rows. The Sound Necklace reads them through its own
project-scoped routes (the ungated /api/oc/acoustemes surface was retired in ENG-290).
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import math
import re
import unicodedata
from typing import Any

from google.cloud import storage

from app.core.database import AsyncSessionLocal
from app.services.oral_collector import acousteme_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
logger = logging.getLogger("import_ruth_acoustemes")

CODEBOOK_VERSION = "terena-xlsr53-k100-v1"
COLLECTION = "terena-ruth"
AUDIO_BUCKET = "terena-pilot"
HOP_SEC = acousteme_service.ACOUSTEME_HOP_SEC
# Must match oc_acousteme_artifacts.audio_id (String(128)).
AUDIO_ID_MAX_LEN = 128


def slugify(name: str, prefix: str = "ruth") -> str:
    """Stable ascii slug for an audio basename (handles spaces/accents).

    Capped at AUDIO_ID_MAX_LEN to fit oc_acousteme_artifacts.audio_id. Long
    names are truncated and suffixed with a digest of the original name, so the
    id stays unique and deterministic rather than silently colliding.
    """
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    ascii_name = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_name).strip("-").lower()
    slug = f"{prefix}-{ascii_name}" if ascii_name else prefix
    if len(slug) > AUDIO_ID_MAX_LEN:
        digest = hashlib.sha256(name.encode("utf-8")).hexdigest()[:8]
        slug = f"{slug[: AUDIO_ID_MAX_LEN - len(digest) - 1].rstrip('-')}-{digest}"
    return slug


def units_to_segments(units: list[int], duration_sec: float | None) -> list[dict[str, Any]]:
    """RLE-encode per-frame unit ids into contiguous {start, end, unit_id} runs.

    Frame duration is derived from the audio length (duration / num_frames) so
    the last segment ends exactly at duration_sec — no end-of-file drift when
    Beads seeks the audio. Falls back to the fixed 20 ms hop if duration is
    unknown.
    """
    segments: list[dict[str, Any]] = []
    if not units:
        return segments
    valid_dur = (
        duration_sec
        if (duration_sec and math.isfinite(duration_sec) and duration_sec > 0)
        else None
    )
    dt = (valid_dur / len(units)) if valid_dur else HOP_SEC
    run_start = 0
    for i in range(1, len(units) + 1):
        if i == len(units) or units[i] != units[run_start]:
            segments.append(
                {
                    "start": round(run_start * dt, 4),
                    "end": round(i * dt, 4),
                    "unit_id": int(units[run_start]),
                }
            )
            run_start = i
    if valid_dur:
        segments[-1]["end"] = round(valid_dur, 6)
    return segments


def load_corpus(corpus_uri: str) -> dict[str, Any]:
    if corpus_uri.startswith("gs://"):
        rest = corpus_uri[len("gs://") :]
        if "/" not in rest or not all(rest.split("/", 1)):
            raise ValueError(f"Invalid gs:// URI, expected gs://bucket/object: {corpus_uri}")
        bucket_name, obj = rest.split("/", 1)
        data = storage.Client().bucket(bucket_name).blob(obj).download_as_bytes()
        corpus: dict[str, Any] = json.loads(data)
        return corpus
    with open(corpus_uri) as f:
        loaded: dict[str, Any] = json.load(f)
        return loaded


async def import_corpus(corpus_uri: str, dry_run: bool, limit: int | None) -> None:
    corpus = load_corpus(corpus_uri)
    entries = list(corpus.items())
    if limit is not None:
        entries = entries[:limit]
    logger.info("Loaded %d corpus entries from %s", len(entries), corpus_uri)

    # Preflight slug collisions: distinct names can normalize to the same id
    # (e.g. "A B" / "A-B" / accent variants), and store_artifact upserts, so a
    # collision would silently overwrite an earlier stream. Fail before writing.
    by_slug: dict[str, str] = {}
    for name, _ in entries:
        slug = slugify(name)
        if slug in by_slug:
            raise ValueError(f"Slug collision: {name!r} and {by_slug[slug]!r} both map to {slug!r}")
        by_slug[slug] = name

    async with AsyncSessionLocal() as db:
        for name, entry in entries:
            audio_id = slugify(name)
            units = entry.get("units")
            if not isinstance(units, list) or not units:
                logger.warning("Skipping %s: missing or empty units", name)
                continue
            num_frames = len(units)
            segments = units_to_segments(units, entry.get("duration_sec"))
            audio_object = entry.get("source_object") or f"ruth/{name}.mp3"
            stream = {
                "duration_sec": entry.get("duration_sec"),
                "num_frames": num_frames,
                "segments": segments,
            }
            logger.info(
                "%s -> %s (%d frames, %d segments)%s",
                name,
                audio_id,
                num_frames,
                len(segments),
                " [dry-run]" if dry_run else "",
            )
            if dry_run:
                continue
            await acousteme_service.store_artifact(
                db,
                audio_id=audio_id,
                codebook_version=CODEBOOK_VERSION,
                stream=stream,
                bucket=AUDIO_BUCKET,
                audio_bucket=AUDIO_BUCKET,
                audio_object=audio_object,
                title=name,
                collection=COLLECTION,
            )
    logger.info("Done (%d entries)", len(entries))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--corpus",
        default="gs://terena-pilot/acoustemes-raw/ruth_corpus.json",
        help="Corpus JSON URI (gs:// or local path)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Log only; no uploads/DB writes")
    parser.add_argument("--limit", type=int, default=None, help="Only import the first N entries")
    args = parser.parse_args()
    if args.limit is not None and args.limit < 0:
        parser.error("--limit must be >= 0")
    asyncio.run(import_corpus(args.corpus, args.dry_run, args.limit))


if __name__ == "__main__":
    main()
