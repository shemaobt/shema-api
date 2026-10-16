"""The one-shot script that gives the hours' recordings the duration measured on their file.

The script runs as Henok runs it, against the suite's database. The bucket is an in-memory
fake holding real audio made by ffmpeg, so the server's own ffprobe measurement reads it. The
assertions read the printed report and the rows afterwards.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import pytest
from google.api_core.exceptions import NotFound
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.enums import SplittingStatus, UploadStatus
from app.db.models.oc_genre import OC_Genre, OC_Subcategory
from app.db.models.oc_recording import OC_Recording
from app.services.oral_collector import gcs_utils
from scripts import fix_recording_durations
from tests.baker import (
    make_language,
    make_oc_recording,
    make_oc_taxonomy,
    make_project,
)
from tests.oral_collector_harness import PRODUCTION_BUCKET, STAGING_BUCKET


def a_tone(seconds: float) -> bytes:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "tone.wav"
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-f",
                "lavfi",
                "-i",
                f"sine=duration={seconds}:sample_rate=8000",
                str(out),
            ],
            check=True,
        )
        return out.read_bytes()


class FakeBucket:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}
        self.reads: list[tuple[str, str]] = []

    async def download(self, bucket_name: str, blob_name: str) -> bytes:
        self.reads.append((bucket_name, blob_name))
        try:
            return self.objects[(bucket_name, blob_name)]
        except KeyError:
            raise NotFound(f"No such object: {bucket_name}/{blob_name}") from None


@pytest.fixture()
def bucket(monkeypatch: pytest.MonkeyPatch) -> FakeBucket:
    fake = FakeBucket()
    monkeypatch.setattr(get_settings(), "gcs_oc_bucket", STAGING_BUCKET)
    monkeypatch.setattr(gcs_utils, "download_gcs_object", fake.download)
    return fake


class Seeder:
    def __init__(
        self, db: AsyncSession, bucket: FakeBucket, genre: OC_Genre, sub: OC_Subcategory
    ) -> None:
        self.db = db
        self.bucket = bucket
        self.genre = genre
        self.sub = sub
        self.count = 0

    async def a_project(self, name: str) -> str:
        self.count += 1
        language = await make_language(self.db, name=f"Língua {name}", code=f"l{self.count}")
        project = await make_project(self.db, language.id, name=name)
        return project.id

    async def a_recording(
        self,
        project_id: str,
        *,
        stored: float,
        file_seconds: float | None,
        upload_status: str = UploadStatus.VERIFIED,
        splitting_status: str = SplittingStatus.NONE,
        split_from_id: str | None = None,
        with_address: bool = True,
    ) -> OC_Recording:
        self.count += 1
        blob = f"{project_id}/recording-{self.count}.wav"
        recording = await make_oc_recording(
            self.db,
            project_id,
            self.genre.id,
            self.sub.id,
            title=f"recording {self.count}",
            duration_seconds=stored,
            gcs_url=f"https://storage.googleapis.com/{PRODUCTION_BUCKET}/{blob}"
            if with_address
            else None,
            upload_status=upload_status,
            splitting_status=splitting_status,
        )
        if split_from_id is not None:
            recording.split_from_id = split_from_id
            await self.db.commit()
        if file_seconds is not None:
            self.bucket.objects[(STAGING_BUCKET, blob)] = a_tone(file_seconds)
        return recording


@pytest.fixture()
async def seed(db_session: AsyncSession, bucket: FakeBucket) -> Seeder:
    genre, sub = await make_oc_taxonomy(db_session)
    return Seeder(db_session, bucket, genre, sub)


async def stored_now(db: AsyncSession, recording: OC_Recording) -> float:
    row = await db.execute(
        select(OC_Recording.duration_seconds)
        .where(OC_Recording.id == recording.id)
        .execution_options(populate_existing=True)
    )
    return row.scalar_one()


async def a_run(capsys: pytest.CaptureFixture[str], *argv: str) -> str:
    status = await fix_recording_durations.run(list(argv))
    out = capsys.readouterr().out
    assert status == 0, out
    return out


def lines_naming(out: str, *tokens: str) -> list[str]:
    return [line for line in out.splitlines() if all(token in line for token in tokens)]


def the_line_naming(out: str, *tokens: str) -> str:
    found = lines_naming(out, *tokens)
    assert len(found) == 1, f"{tokens} are on {len(found)} lines of:\n{out}"
    return found[0]


async def two_divergent_and_one_correct(seed: Seeder) -> dict[str, OC_Recording | str]:
    first = await seed.a_project("Projeto Um")
    wrong_in_first = await seed.a_recording(first, stored=1894.0, file_seconds=2)
    right_in_first = await seed.a_recording(first, stored=3.0, file_seconds=3)
    second = await seed.a_project("Projeto Dois")
    wrong_in_second = await seed.a_recording(second, stored=3600.0, file_seconds=1)
    return {
        "first": first,
        "second": second,
        "wrong_in_first": wrong_in_first,
        "right_in_first": right_in_first,
        "wrong_in_second": wrong_in_second,
    }


async def test_a_dry_run_lists_the_two_divergent_recordings_with_stored_and_measured_durations_and_each_projects_hours_before_and_after_and_writes_nothing(  # noqa: E501
    seed: Seeder, db_session: AsyncSession, capsys: pytest.CaptureFixture[str]
) -> None:
    rows = await two_divergent_and_one_correct(seed)

    out = await a_run(capsys)

    wrong_in_first = the_line_naming(out, rows["wrong_in_first"].id)
    assert rows["first"] in wrong_in_first
    assert "1894.0" in wrong_in_first and "2.0" in wrong_in_first
    wrong_in_second = the_line_naming(out, rows["wrong_in_second"].id)
    assert rows["second"] in wrong_in_second
    assert "3600.0" in wrong_in_second and "1.0" in wrong_in_second
    assert not lines_naming(out, rows["right_in_first"].id)

    first_hours = the_line_naming(out, "hours", rows["first"])
    assert f"{round((1894 + 3) / 3600, 2):.2f}" in first_hours
    assert f"{round((2 + 3) / 3600, 2):.2f}" in first_hours
    second_hours = the_line_naming(out, "hours", rows["second"])
    assert f"{round(3600 / 3600, 2):.2f}" in second_hours
    assert f"{round(1 / 3600, 2):.2f}" in second_hours

    assert await stored_now(db_session, rows["wrong_in_first"]) == 1894.0
    assert await stored_now(db_session, rows["wrong_in_second"]) == 3600.0


async def test_a_write_run_gives_the_two_divergent_recordings_their_measured_duration_and_leaves_the_correct_one_as_it_was(  # noqa: E501
    seed: Seeder, db_session: AsyncSession, capsys: pytest.CaptureFixture[str]
) -> None:
    rows = await two_divergent_and_one_correct(seed)

    out = await a_run(capsys, "--write")

    assert await stored_now(db_session, rows["wrong_in_first"]) == 2.0
    assert await stored_now(db_session, rows["wrong_in_second"]) == 1.0
    assert await stored_now(db_session, rows["right_in_first"]) == 3.0
    assert the_line_naming(out, "written").split()[-1] == "2"


async def test_a_second_write_run_changes_no_row_and_finds_nothing_divergent(
    seed: Seeder, db_session: AsyncSession, capsys: pytest.CaptureFixture[str]
) -> None:
    rows = await two_divergent_and_one_correct(seed)
    await a_run(capsys, "--write")

    out = await a_run(capsys, "--write")

    for name in ("wrong_in_first", "wrong_in_second", "right_in_first"):
        assert not lines_naming(out, rows[name].id)
    assert the_line_naming(out, "divergent").split()[-1] == "0"
    assert the_line_naming(out, "written").split()[-1] == "0"
    assert await stored_now(db_session, rows["wrong_in_first"]) == 2.0
    assert await stored_now(db_session, rows["wrong_in_second"]) == 1.0
    assert await stored_now(db_session, rows["right_in_first"]) == 3.0


async def test_a_recording_whose_file_is_missing_is_listed_as_unreadable_and_left_as_it_is(
    seed: Seeder, db_session: AsyncSession, capsys: pytest.CaptureFixture[str]
) -> None:
    project = await seed.a_project("Projeto Um")
    missing = await seed.a_recording(project, stored=1894.0, file_seconds=None)

    out = await a_run(capsys, "--write")

    assert "unreadable" in the_line_naming(out, missing.id)
    assert await stored_now(db_session, missing) == 1894.0


async def test_a_recording_stored_at_120_seconds_whose_file_measures_119_4_is_neither_listed_nor_changed(  # noqa: E501
    seed: Seeder, db_session: AsyncSession, capsys: pytest.CaptureFixture[str]
) -> None:
    project = await seed.a_project("Projeto Um")
    rounding = await seed.a_recording(project, stored=120.0, file_seconds=119.4)

    out = await a_run(capsys, "--write")

    assert not lines_naming(out, rounding.id)
    assert await stored_now(db_session, rounding) == 120.0


async def test_a_recording_archived_after_a_split_and_one_whose_upload_failed_are_neither_measured_nor_listed_and_the_splits_segments_are_measured_on_their_own_files(  # noqa: E501
    seed: Seeder, db_session: AsyncSession, capsys: pytest.CaptureFixture[str]
) -> None:
    project = await seed.a_project("Projeto Um")
    parent = await seed.a_recording(
        project,
        stored=1894.0,
        file_seconds=2,
        splitting_status=SplittingStatus.ARCHIVED_AFTER_SPLIT,
    )
    first_segment = await seed.a_recording(
        project, stored=1000.0, file_seconds=1, split_from_id=parent.id
    )
    second_segment = await seed.a_recording(
        project, stored=894.0, file_seconds=1, split_from_id=parent.id
    )
    failed = await seed.a_recording(
        project, stored=1894.0, file_seconds=2, upload_status=UploadStatus.UPLOAD_FAILED
    )

    out = await a_run(capsys, "--write")

    assert not lines_naming(out, parent.id)
    assert not lines_naming(out, failed.id)
    read = {blob for _bucket, blob in seed.bucket.reads}
    assert gcs_utils.blob_name_from_url(parent.gcs_url) not in read
    assert gcs_utils.blob_name_from_url(failed.gcs_url) not in read
    assert await stored_now(db_session, parent) == 1894.0
    assert await stored_now(db_session, failed) == 1894.0
    assert "1000.0" in the_line_naming(out, first_segment.id)
    assert "894.0" in the_line_naming(out, second_segment.id)
    assert await stored_now(db_session, first_segment) == 1.0
    assert await stored_now(db_session, second_segment) == 1.0


async def test_a_counted_recording_with_no_file_address_is_listed_as_unreadable_never_zeroed(
    seed: Seeder, db_session: AsyncSession, capsys: pytest.CaptureFixture[str]
) -> None:
    project = await seed.a_project("Projeto Um")
    no_address = await seed.a_recording(
        project, stored=1894.0, file_seconds=None, with_address=False
    )

    out = await a_run(capsys, "--write")

    assert "unreadable" in the_line_naming(out, no_address.id)
    assert await stored_now(db_session, no_address) == 1894.0


async def test_without_ffprobe_the_script_stops_before_reading_anything_and_says_why(
    seed: Seeder,
    db_session: AsyncSession,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project = await seed.a_project("Projeto Um")
    wrong = await seed.a_recording(project, stored=1894.0, file_seconds=2)
    monkeypatch.setenv("PATH", str(tmp_path))

    status = await fix_recording_durations.run(["--write"])

    captured = capsys.readouterr()
    assert status != 0
    assert "ffprobe" in captured.err
    assert seed.bucket.reads == []
    assert await stored_now(db_session, wrong) == 1894.0


async def test_the_run_names_the_bucket_it_reads(
    seed: Seeder, capsys: pytest.CaptureFixture[str]
) -> None:
    project = await seed.a_project("Projeto Um")
    await seed.a_recording(project, stored=1894.0, file_seconds=2)

    out = await a_run(capsys)

    assert STAGING_BUCKET in out.splitlines()[0]
    assert {bucket_name for bucket_name, _blob in seed.bucket.reads} == {STAGING_BUCKET}
