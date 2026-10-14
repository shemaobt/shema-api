"""OBT-585: the coordination sees the Pulse's image on the inbox, before it imports.

Until the import the photo is a ``ShemaIntakeImage`` and no media item, so neither the record
nor the item's link can serve it. ``GET /forms/submissions/{id}/image/link`` does, behind four
gates in the item's order — scope, object, the leader's box standing in for the decision nobody
has recorded, and the reader — and the detail says, as a flag and never a URL, whether that call
would answer. Held here per gate and per role (coordination, OBT Lab, Resource Circle), on a
withheld and on a cleared project, with the bucket a fake that records what it signed: no URL is
ever stored, and the surfaces that must keep not knowing the row — ficha, card, export, wall,
Pulse — are checked once more before the import.

No account here is an installation admin: they pass every guard, and a refusal asserted with one
would pass for the wrong reason.
"""

from __future__ import annotations

import logging
from typing import Any

import pytest
from sqlalchemy import select

from app.db.models.shema_enums import ShemaRegionKey
from app.db.models.shema_form import ShemaIntakeImage, ShemaSubmission
from app.services.oral_collector import gcs_utils
from tests.test_shema.conftest import PREFIX, auth_header, make_scoped_user, make_shema_project

PROJECTS = f"{PREFIX}/projects"
SUBMISSIONS = f"{PREFIX}/forms/submissions"
LINKS = f"{PREFIX}/intake-links"
EXPORT = f"{PREFIX}/export/projects"
WALL = f"{PREFIX}/prayer/requests"
PULSE = f"{PREFIX}/prayer/pulse"
HERE = ShemaRegionKey.SOUTH_AMERICA
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
DESCRIPTION = "LEGENDA-SIGILOSA a equipe no vale"
FILE_NAME = "equipe no vale.jpg"


class FakeBucket:
    def __init__(self) -> None:
        self.uploaded: list[str] = []
        self.signed: list[tuple[str, str, int]] = []

    async def upload(self, bucket: str, key: str, data: bytes, content_type: str) -> str:
        self.uploaded.append(key)
        return f"gs://{bucket}/{key}"

    async def sign(
        self,
        bucket: str,
        key: str,
        *,
        expiry_minutes: int = 15,
        response_content_type: str | None = None,
    ) -> str:
        self.signed.append((bucket, key, expiry_minutes))
        return f"https://signed.example/{key}?minutes={expiry_minutes}"


@pytest.fixture()
def bucket(monkeypatch) -> FakeBucket:
    fake = FakeBucket()
    monkeypatch.setattr(gcs_utils, "upload_gcs_object", fake.upload)
    monkeypatch.setattr(gcs_utils, "generate_signed_download_url", fake.sign)
    return fake


async def _headers(db_session, shema_app, role: str, *, regions=(HERE,), tag: str = ""):
    user = await make_scoped_user(
        db_session,
        shema_app,
        email=f"{role.lower()}{tag}-{'-'.join(r.value for r in regions)}@pendente.test",
        role_key=role,
        regions=list(regions),
    )
    return await auth_header(db_session, user)


async def _project(db_session, project_id: str = "guarani-mbya", *, sensitive: bool = False):
    record = await make_shema_project(
        db_session, project_id=project_id, region_key=HERE, language_name="Guarani Mbyá"
    )
    record.location = "Brazil, Vale"
    record.sensitive_country = sensitive
    await db_session.commit()
    return record


async def _pulse(
    client,
    db_session,
    headers,
    *,
    authorized: bool | None = True,
    with_image: bool = True,
    period: str = "2026-09",
) -> tuple[str, str | None]:
    """A Pulse through the link, with its image uploaded first; returns ``(submission, image)``."""
    before = set((await db_session.execute(select(ShemaSubmission.id))).scalars())
    minted = await client.post(LINKS, json={"projectId": "guarani-mbya"}, headers=headers)
    assert minted.status_code == 201, minted.text
    token = minted.json()["token"]
    answers: dict[str, Any] = {"submittedBy": "Kuaray", "period": period}
    image_id = None
    if with_image:
        stored = await client.post(
            f"{PREFIX}/intake/{token}/image",
            content=JPEG,
            headers={"Content-Type": "image/jpeg", "X-File-Name": FILE_NAME},
        )
        assert stored.status_code == 201, stored.text
        image_id = stored.json()["id"]
        answers.update({"image": image_id, "imageDescription": DESCRIPTION})
        if authorized is not None:
            answers["imageAuthorized"] = authorized
    accepted = await client.post(
        f"{PREFIX}/intake/{token}", json={"definitionVersion": 1, "answers": answers}
    )
    assert accepted.status_code == 202, accepted.text
    after = set((await db_session.execute(select(ShemaSubmission.id))).scalars())
    [submission_id] = after - before
    return submission_id, image_id


def _link(submission_id: str) -> str:
    return f"{SUBMISSIONS}/{submission_id}/image/link"


async def _detail(client, submission_id: str, headers) -> dict[str, Any]:
    res = await client.get(f"{SUBMISSIONS}/{submission_id}", headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


# --- the happy path, and the flag that announces it ------------------------------------------


async def test_the_coordination_gets_the_link_and_the_detail_says_there_is_one_to_ask_for(
    client, db_session, shema_app, bucket
) -> None:
    await _project(db_session)
    headers = await _headers(db_session, shema_app, "coordinator")
    submission_id, image_id = await _pulse(client, db_session, headers)
    image = await db_session.get(ShemaIntakeImage, image_id)
    assert image is not None

    detail = await _detail(client, submission_id, headers)
    res = await client.get(_link(submission_id), headers=headers)

    assert detail["pendingImage"] is True and detail["answers"]["image"] == image_id
    assert "signed.example" not in str(detail) and image.storage_key not in str(detail)
    assert res.status_code == 200, res.text
    assert res.json() == {
        "url": f"https://signed.example/{image.storage_key}?minutes=15",
        "expiresInMinutes": 15,
    }
    assert res.headers["cache-control"] == "private, no-store"
    assert bucket.signed == [("shema-private", image.storage_key, 15)]


async def test_a_url_is_never_written_anywhere(client, db_session, shema_app, bucket) -> None:
    """Minted per call: two calls sign twice, and no row and no payload holds the address."""
    await _project(db_session)
    headers = await _headers(db_session, shema_app, "coordinator")
    submission_id, image_id = await _pulse(client, db_session, headers)

    first = await client.get(_link(submission_id), headers=headers)
    second = await client.get(_link(submission_id), headers=headers)

    assert first.status_code == second.status_code == 200
    assert len(bucket.signed) == 2
    submission = await db_session.get(ShemaSubmission, submission_id)
    image = await db_session.get(ShemaIntakeImage, image_id)
    assert submission is not None and image is not None
    assert "signed.example" not in submission.archived_payload
    assert not image.storage_key.startswith("http")


# --- gate two: an object to serve --------------------------------------------------------------


async def test_a_pulse_with_no_image_has_nothing_to_serve(
    client, db_session, shema_app, bucket
) -> None:
    await _project(db_session)
    headers = await _headers(db_session, shema_app, "coordinator")
    submission_id, _ = await _pulse(client, db_session, headers, with_image=False)

    detail = await _detail(client, submission_id, headers)
    res = await client.get(_link(submission_id), headers=headers)

    assert detail["pendingImage"] is False
    assert res.status_code == 404, res.text
    assert bucket.signed == []


async def test_once_imported_the_pulse_is_no_longer_pending_and_the_record_serves_the_photo(
    client, db_session, shema_app, bucket
) -> None:
    """After the import the photo is the record's, under the decision the import recorded — and
    a withdrawal may since have reversed it, which this route must not bypass."""
    project = await _project(db_session)
    headers = await _headers(db_session, shema_app, "coordinator")
    submission_id, _ = await _pulse(client, db_session, headers)
    record = await client.get(f"{PROJECTS}/{project.id}", headers=headers)
    imported = await client.post(
        f"{SUBMISSIONS}/{submission_id}/import",
        headers={**headers, "If-Match": record.headers["ETag"]},
    )
    assert imported.status_code == 200, imported.text

    detail = await _detail(client, submission_id, headers)
    pending = await client.get(_link(submission_id), headers=headers)
    [photo] = (await client.get(f"{PROJECTS}/{project.id}", headers=headers)).json()["mediaPhotos"]
    item = await client.get(f"{PROJECTS}/{project.id}/media/{photo['id']}/link", headers=headers)

    assert detail["pendingImage"] is False
    assert pending.status_code == 404, pending.text
    assert item.status_code == 200, item.text
    assert len(bucket.signed) == 1


async def test_a_submission_outside_the_scope_is_not_found(
    client, db_session, shema_app, bucket
) -> None:
    await _project(db_session)
    submission_id, _ = await _pulse(
        client, db_session, await _headers(db_session, shema_app, "coordinator")
    )

    res = await client.get(
        _link(submission_id),
        headers=await _headers(
            db_session, shema_app, "coordinator", regions=(ShemaRegionKey.AFRICA,)
        ),
    )

    assert res.status_code == 404, res.text
    assert bucket.signed == []


# --- gate three: the leader's box ------------------------------------------------------------


@pytest.mark.parametrize("authorized", [False, None], ids=["unchecked", "absent"])
async def test_without_the_leaders_box_the_image_is_undecided_and_refused(
    client, db_session, shema_app, bucket, authorized
) -> None:
    """Daniel, 14/oct/2026: before the import the box is the decision; unchecked or absent is
    undecided, refused like it — the one reading the import also uses."""
    await _project(db_session)
    headers = await _headers(db_session, shema_app, "coordinator")
    submission_id, image_id = await _pulse(client, db_session, headers, authorized=authorized)

    detail = await _detail(client, submission_id, headers)
    res = await client.get(_link(submission_id), headers=headers)

    assert detail["pendingImage"] is False and detail["answers"]["image"] == image_id
    assert res.status_code == 403, res.text
    assert "signed.example" not in res.text
    assert bucket.signed == []


async def test_the_box_and_the_reader_refuse_with_one_sentence_and_two_log_lines(
    client, db_session, shema_app, bucket, caplog
) -> None:
    """One Pulse on a withheld project, its box ticked: the OBT Lab is refused by the reader
    gate. Another project's Pulse with the box unchecked: the coordination is refused by the
    box. Same sentence on the wire; two lines in the log, the reader on the first only, and no
    place name in either record."""
    caplog.set_level(logging.WARNING, logger="app.services.shema.pending_image_download_url")
    await _project(db_session, sensitive=True)
    ours = await _headers(db_session, shema_app, "coordinator")
    lab = await _headers(db_session, shema_app, "obtLab")
    checked, _ = await _pulse(client, db_session, ours, period="2026-08")
    unchecked, _ = await _pulse(client, db_session, ours, authorized=False, period="2026-09")

    by_reader = await client.get(_link(checked), headers=lab)
    by_box = await client.get(_link(unchecked), headers=ours)

    assert by_reader.status_code == by_box.status_code == 403
    assert by_reader.json() == by_box.json()
    lines = [r for r in caplog.records if r.name == "app.services.shema.pending_image_download_url"]
    assert [r.getMessage() for r in lines] == [
        "shema file refused: the reader is not the coordination of a withheld project",
        "shema file refused: not shared with this audience",
    ]
    assert lines[0].shema_reader == "other"  # type: ignore[attr-defined]
    assert not hasattr(lines[1], "shema_reader")
    for line in lines:
        assert "Vale" not in str(vars(line)) and "Brazil" not in str(vars(line))
    assert bucket.signed == []


# --- gate four: the reader, on a withheld and on a cleared project ---------------------------


@pytest.mark.parametrize("role", ["obtLab", "resourceCircle"])
async def test_on_a_withheld_project_the_answer_does_not_depend_on_what_the_pulse_holds(
    client, db_session, shema_app, bucket, role
) -> None:
    """The Crivo's finding on the first cut (14/oct/2026): with the object gate before the
    reader's, an OBT Lab in the scope got 404 for a Pulse without a photo and 403 for one with
    it, and could learn Pulse by Pulse which ones carry a photograph the detail hides. Reader
    first: a Pulse without a photo, one with a photo and one already imported answer the same
    403, byte for byte, and the detail shows no pending image for any of them. The Resource
    Circle reads the answers (OBT-571) and had nothing to learn; it rides the same gate."""
    project = await _project(db_session, sensitive=True)
    ours = await _headers(db_session, shema_app, "coordinator")
    theirs = await _headers(db_session, shema_app, role)
    bare, _ = await _pulse(client, db_session, ours, with_image=False, period="2026-07")
    with_photo, _ = await _pulse(client, db_session, ours, period="2026-08")
    imported, _ = await _pulse(client, db_session, ours, period="2026-09")
    record = await client.get(f"{PROJECTS}/{project.id}", headers=ours)
    applied = await client.post(
        f"{SUBMISSIONS}/{imported}/import", headers={**ours, "If-Match": record.headers["ETag"]}
    )
    assert applied.status_code == 200, applied.text

    answers = [
        await client.get(_link(submission_id), headers=theirs)
        for submission_id in (bare, with_photo, imported)
    ]
    details = [
        await _detail(client, submission_id, theirs)
        for submission_id in (bare, with_photo, imported)
    ]

    assert [res.status_code for res in answers] == [403, 403, 403]
    assert len({res.text for res in answers}) == 1
    assert [detail["pendingImage"] for detail in details] == [False, False, False]
    assert bucket.signed == []


async def test_an_unknown_submission_is_logged_under_its_own_key(
    client, db_session, shema_app, bucket, caplog
) -> None:
    """The Crivo's note: ``refuse_out_of_scope`` records what it is given as
    ``shema_project_id``, and a submission's id there breaks the join by project. The line is
    written here with the submission under its own key and no project id invented."""
    caplog.set_level(logging.WARNING, logger="app.services.shema.pending_image_download_url")
    await _project(db_session)
    submission_id, _ = await _pulse(
        client, db_session, await _headers(db_session, shema_app, "coordinator")
    )
    elsewhere = await _headers(
        db_session, shema_app, "coordinator", regions=(ShemaRegionKey.AFRICA,)
    )

    outside = await client.get(_link(submission_id), headers=elsewhere)
    unknown = await client.get(_link("no-such-submission"), headers=elsewhere)

    assert outside.status_code == unknown.status_code == 404
    assert outside.json() == unknown.json()
    lines = [r for r in caplog.records if "found no row" in r.getMessage()]
    assert [getattr(r, "shema_submission_id", None) for r in lines] == [
        submission_id,
        "no-such-submission",
    ]
    assert all(not hasattr(r, "shema_project_id") for r in lines)
    assert all(r.shema_scope_regions == ["africa"] for r in lines)  # type: ignore[attr-defined]


@pytest.mark.parametrize("role", ["obtLab", "resourceCircle"])
async def test_on_a_withheld_project_only_the_coordination_is_shown_a_pending_image(
    client, db_session, shema_app, bucket, role
) -> None:
    """Daniel, 9/oct/2026, option b, unchanged: the OBT Lab reads the detail with ``answers``
    ``{}`` and ``answersWithheld`` (OBT-556) and no pending image; the Resource Circle reads the
    truth of the record and not these bytes. Neither gets a link; the coordination gets both."""
    await _project(db_session, sensitive=True)
    ours = await _headers(db_session, shema_app, "coordinator")
    theirs = await _headers(db_session, shema_app, role)
    submission_id, _ = await _pulse(client, db_session, ours)

    their_detail = await _detail(client, submission_id, theirs)
    their_link = await client.get(_link(submission_id), headers=theirs)
    our_detail = await _detail(client, submission_id, ours)
    our_link = await client.get(_link(submission_id), headers=ours)

    assert their_detail["pendingImage"] is False
    assert "signed.example" not in str(their_detail)
    if role == "obtLab":
        # OBT-556: the reduction — no answer at all, the description included.
        assert (their_detail["answers"], their_detail["answersWithheld"]) == ({}, True)
    else:
        # OBT-571: the Resource Circle reads the record's truth, the description included —
        # what it does not get is the photograph, and the flag says so.
        assert their_detail["answers"]["imageDescription"] == DESCRIPTION
    assert their_link.status_code == 403, their_link.text
    assert "signed.example" not in their_link.text
    assert our_detail["pendingImage"] is True
    assert our_link.status_code == 200, our_link.text
    assert len(bucket.signed) == 1


@pytest.mark.parametrize("role", ["coordinator", "obtLab", "resourceCircle"])
async def test_on_a_cleared_project_every_reader_of_the_inbox_gets_the_link(
    client, db_session, shema_app, bucket, role
) -> None:
    await _project(db_session)
    submission_id, _ = await _pulse(
        client, db_session, await _headers(db_session, shema_app, "coordinator", tag="-minter")
    )
    headers = await _headers(db_session, shema_app, role)

    detail = await _detail(client, submission_id, headers)
    res = await client.get(_link(submission_id), headers=headers)

    assert detail["pendingImage"] is True
    assert res.status_code == 200, res.text
    assert res.json()["expiresInMinutes"] == 15


# --- the surfaces that must keep not knowing the row ------------------------------------------


async def test_before_the_import_no_surface_of_the_record_knows_the_image(
    client, db_session, shema_app, bucket
) -> None:
    project = await _project(db_session)
    headers = await _headers(db_session, shema_app, "coordinator")
    _submission_id, image_id = await _pulse(client, db_session, headers)
    image = await db_session.get(ShemaIntakeImage, image_id)
    assert image is not None
    circle = await _headers(db_session, shema_app, "resourceCircle")

    record = (await client.get(f"{PROJECTS}/{project.id}", headers=headers)).json()
    page = (await client.get(PROJECTS, headers=headers)).json()
    others = [
        (await client.get(WALL, headers=headers)).text,
        (await client.get(EXPORT, params={"format": "json"}, headers=headers)).text,
        (await client.get(EXPORT, params={"format": "csv"}, headers=headers)).text,
        (await client.get(PULSE, headers=circle)).text,
    ]

    assert record["mediaPhotos"] in (None, [])
    assert next(c for c in page["items"] if c["id"] == project.id)["hasMedia"] is False
    for text in others:
        assert image.storage_key not in text and FILE_NAME not in text
        assert DESCRIPTION not in text and "signed.example" not in text
    assert bucket.signed == []
