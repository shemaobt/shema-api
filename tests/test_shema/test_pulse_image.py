"""OBT-578: the Pulso Mensal carries an image, a description and an authorization of its use.

Karina, via Daniel, 6/oct/2026: *"pulso mensal: acrescentar um campo para adicionar imagem e uma
descrição com um campo de autorização de uso de imagem."* Daniel approved the five answers on
8/oct/2026 (the PR lists them with their author). What is held here, in the order the image
travels: the upload through the link (three formats, one ceiling, proof by the bytes), the
Pulse that names it, the import that mints the record's photo with the leader's answer as its
authorization — and then **every output**, each proving that without the authorization the
image appears nowhere: the ficha and the card before the import, the signed URL, the prayer
wall, the Prayer Pulse, the export, and the archived Pulse after the coordination withdraws.

No account here is an installation admin: they pass every guard, and a refusal asserted with
one would pass for the wrong reason. The bucket is a fake that records what was written and
what was signed — ``gcs_utils`` without a bucket, the ``test_privacy.py`` mould.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from sqlalchemy import select

from app.db.models.shema_enums import ShemaRegionKey
from app.db.models.shema_form import ShemaIntakeImage, ShemaSubmission
from app.db.models.shema_media import ShemaMediaItem
from app.models.shema_privacy import ShemaAudience
from app.services.oral_collector import gcs_utils
from app.services.shema import media_download_url
from app.services.shema._intake_image_rules import MAX_IMAGE_BYTES
from app.services.shema._scope import region_scope
from app.utils.shema_forms import IMAGE_ANSWERS
from tests.test_shema.conftest import (
    PREFIX,
    auth_header,
    make_scoped_user,
    make_shema_project,
)

LINKS = f"{PREFIX}/intake-links"
PROJECTS = f"{PREFIX}/projects"
SUBMISSIONS = f"{PREFIX}/forms/submissions"
EXPORT = f"{PREFIX}/export/projects"
WALL = f"{PREFIX}/prayer/requests"
PULSE = f"{PREFIX}/prayer/pulse"
APP_KEY = "shema"

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
WEBP = b"RIFF" + b"\x00\x00\x00\x00" + b"WEBP" + b"\x00" * 64
DESCRIPTION = "LEGENDA-SIGILOSA a equipe no vale"
FILE_NAME = "equipe no vale.jpg"


class FakeBucket:
    """``gcs_utils`` without a bucket: what was uploaded, and what was signed."""

    def __init__(self) -> None:
        self.uploaded: list[tuple[str, str, bytes, str]] = []
        self.signed: list[tuple[str, str]] = []

    async def upload(self, bucket: str, key: str, data: bytes, content_type: str) -> str:
        self.uploaded.append((bucket, key, data, content_type))
        return f"gs://{bucket}/{key}"

    async def sign(
        self,
        bucket: str,
        key: str,
        *,
        expiry_minutes: int = 15,
        response_content_type: str | None = None,
    ) -> str:
        self.signed.append((bucket, key))
        return f"https://signed.example/{key}?minutes={expiry_minutes}"


@pytest.fixture()
def bucket(monkeypatch) -> FakeBucket:
    fake = FakeBucket()
    monkeypatch.setattr(gcs_utils, "upload_gcs_object", fake.upload)
    monkeypatch.setattr(gcs_utils, "generate_signed_download_url", fake.sign)
    return fake


@pytest.fixture()
async def coordinator(db_session, shema_app):
    return await make_scoped_user(
        db_session,
        shema_app,
        email="coordenacao@pulso.test",
        role_key="coordinator",
        regions=[ShemaRegionKey.SOUTH_AMERICA],
    )


@pytest.fixture()
async def headers(db_session, coordinator):
    return await auth_header(db_session, coordinator)


async def _project(db_session, project_id: str = "guarani-mbya", *, sensitive: bool = False):
    record = await make_shema_project(
        db_session,
        project_id=project_id,
        region_key=ShemaRegionKey.SOUTH_AMERICA,
        language_name="Guarani Mbyá",
    )
    record.location = "Brazil, Vale"
    record.sensitive_country = sensitive
    await db_session.commit()
    return record


@pytest.fixture()
async def project(db_session):
    return await _project(db_session)


def answers(**overrides: Any) -> dict[str, Any]:
    return {"submittedBy": "Kuaray", "period": "2026-09", **overrides}


async def a_link(client, headers, project_id: str = "guarani-mbya") -> dict[str, Any]:
    response = await client.post(LINKS, json={"projectId": project_id}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def upload(client, token: str, data: bytes = JPEG, content_type: str = "image/jpeg"):
    return await client.post(
        f"{PREFIX}/intake/{token}/image",
        content=data,
        headers={"Content-Type": content_type, "X-File-Name": FILE_NAME},
    )


async def submit(client, token: str, **extra: Any):
    return await client.post(
        f"{PREFIX}/intake/{token}",
        json={"definitionVersion": 1, "answers": answers(**extra)},
    )


async def _submission(db_session) -> ShemaSubmission:
    return (await db_session.execute(select(ShemaSubmission))).scalar_one()


async def _import(client, headers, submission_id: str):
    record = await client.get(f"{PROJECTS}/guarani-mbya", headers=headers)
    return await client.post(
        f"{SUBMISSIONS}/{submission_id}/import",
        headers={**headers, "If-Match": record.headers["ETag"]},
    )


async def a_pulse_with_image(
    client, db_session, headers, *, authorized: bool | None = True, data: bytes = JPEG
) -> tuple[str, str]:
    """Upload, then the Pulse naming the upload; returns ``(image_id, submission_id)``."""
    link = await a_link(client, headers)
    stored = await upload(client, link["token"], data)
    assert stored.status_code == 201, stored.text
    extra: dict[str, Any] = {"image": stored.json()["id"], "imageDescription": DESCRIPTION}
    if authorized is not None:
        extra["imageAuthorized"] = authorized
    accepted = await submit(client, link["token"], **extra)
    assert accepted.status_code == 202, accepted.text
    return stored.json()["id"], (await _submission(db_session)).id


# --- the upload -----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("data", "content_type"),
    [(JPEG, "image/jpeg"), (PNG, "image/png"), (WEBP, "image/webp"), (JPEG, "image/jpg")],
    ids=["jpeg", "png", "webp", "jpg-alias"],
)
async def test_the_three_formats_are_taken_and_proven_by_their_bytes(
    client, db_session, headers, project, bucket, data, content_type
) -> None:
    """Daniel, 8/oct/2026: JPEG, PNG and WebP. The row keeps a key and never a URL; the key is
    scoped to the row's id and carries neither the file's name nor the project's slug."""
    link = await a_link(client, headers)

    response = await upload(client, link["token"], data, content_type)

    assert response.status_code == 201, response.text
    body = response.json()
    assert set(body) == {"id", "fileName", "contentType"}
    assert body["fileName"] == FILE_NAME
    row = (await db_session.execute(select(ShemaIntakeImage))).scalar_one()
    assert row.id == body["id"] and row.storage_key.startswith(f"shema/media/{row.id}/")
    assert "guarani" not in row.storage_key and FILE_NAME not in row.storage_key
    assert not row.storage_key.startswith("http")
    assert [(b, k) for b, k, _d, _c in bucket.uploaded] == [("shema-private", row.storage_key)]
    assert row.submission_id is None and row.media_item_id is None


@pytest.mark.parametrize(
    ("data", "content_type", "said"),
    [
        (b"<svg xmlns='http://www.w3.org/2000/svg'/>", "image/svg+xml", "Unsupported image type"),
        (PNG, "image/jpeg", "does not match the declared type"),
        (JPEG, "image/avif", "Unsupported image type"),
        (b"", "image/jpeg", "empty"),
        (JPEG, None, "Content-Type"),
    ],
    ids=["svg", "png-declared-jpeg", "avif", "empty", "no-type"],
)
async def test_an_image_the_bytes_do_not_prove_is_refused_and_nothing_is_kept(
    client, db_session, headers, project, bucket, data, content_type, said
) -> None:
    link = await a_link(client, headers)
    extra = {} if content_type is None else {"Content-Type": content_type}

    response = await client.post(
        f"{PREFIX}/intake/{link['token']}/image",
        content=data,
        headers=extra if content_type is not None else {"Content-Type": ""},
    )

    assert response.status_code == 400, response.text
    assert said in response.json()["detail"]
    assert bucket.uploaded == []
    assert (await db_session.execute(select(ShemaIntakeImage))).scalars().all() == []


async def test_an_image_past_the_ceiling_is_refused_before_it_is_read_whole(
    client, db_session, headers, project, bucket
) -> None:
    link = await a_link(client, headers)

    response = await upload(client, link["token"], JPEG + b"\x00" * MAX_IMAGE_BYTES)

    assert response.status_code == 413
    assert bucket.uploaded == []


async def test_a_dead_link_takes_no_image(client, db_session, headers, project, bucket) -> None:
    link = await a_link(client, headers)
    revoked = await client.post(f"{PREFIX}/intake-links/{link['id']}/revoke", headers=headers)
    assert revoked.status_code == 200, revoked.text

    response = await upload(client, link["token"])

    assert response.status_code in (404, 410), response.text
    assert bucket.uploaded == []


# --- the Pulse that names it ----------------------------------------------------------------------


async def test_the_pulse_binds_the_image_it_names_and_the_archive_keeps_the_three_answers(
    client, db_session, headers, project, bucket
) -> None:
    image_id, submission_id = await a_pulse_with_image(client, db_session, headers)

    row = await db_session.get(ShemaIntakeImage, image_id)
    assert row is not None and row.submission_id == submission_id
    kept = json.loads((await _submission(db_session)).archived_payload)["answers"]
    assert kept["image"] == image_id
    assert kept["imageDescription"] == DESCRIPTION
    assert kept["imageAuthorized"] is True


@pytest.mark.parametrize(
    "image", ["no-such-image", "", 7, True], ids=["unknown", "empty", "int", "bool"]
)
async def test_a_pulse_naming_an_image_that_is_not_its_own_is_refused_whole(
    client, db_session, headers, project, bucket, image
) -> None:
    link = await a_link(client, headers)

    response = await submit(client, link["token"], image=image)

    assert response.status_code == 400, response.text
    assert "image" in response.json()["detail"]
    assert (await db_session.execute(select(ShemaSubmission))).scalars().all() == []


async def test_an_image_uploaded_through_another_link_is_not_this_pulses(
    client, db_session, headers, project, bucket
) -> None:
    """An id guessed or lifted from another team's upload reads as no image at all."""
    await _project(db_session, "kaingang-sul")
    theirs = await a_link(client, headers, "kaingang-sul")
    stored = await upload(client, theirs["token"])
    mine = await a_link(client, headers)

    response = await submit(client, mine["token"], image=stored.json()["id"])

    assert response.status_code == 400, response.text
    assert "no image with this id" in response.json()["detail"]


async def test_an_image_already_bound_to_a_pulse_cannot_be_claimed_again(
    client, db_session, headers, project, bucket
) -> None:
    """Through the same link — another link's claim already reads as *no image*."""
    link = await a_link(client, headers)
    stored = await upload(client, link["token"])
    first = await submit(client, link["token"], image=stored.json()["id"])
    assert first.status_code == 202, first.text

    response = await submit(client, link["token"], period="2026-10", image=stored.json()["id"])

    assert response.status_code == 400, response.text
    assert "already belongs" in response.json()["detail"]


async def test_the_same_pulse_sent_twice_is_still_one_pulse_image_included(
    client, db_session, headers, project, bucket
) -> None:
    """Found by the review bot: a leader's phone that times out and retries the same body must
    get the 202 again, as ``archive_submission`` promises for every replay — not a 400 saying the
    image already belongs to a Pulse, which it does: to this one."""
    link = await a_link(client, headers)
    stored = await upload(client, link["token"])
    body = {"definitionVersion": 1, "answers": answers(image=stored.json()["id"])}
    first = await client.post(f"{PREFIX}/intake/{link['token']}", json=body)
    assert first.status_code == 202, first.text

    again = await client.post(f"{PREFIX}/intake/{link['token']}", json=body)

    assert again.status_code == 202, again.text
    submission = await _submission(db_session)
    image = await db_session.get(ShemaIntakeImage, stored.json()["id"])
    assert image is not None and image.submission_id == submission.id


async def test_a_coordinator_filing_directly_carries_no_image(
    client, db_session, headers, project, bucket
) -> None:
    """There is no upload without a link, so the answer is refused with the reason."""
    response = await client.post(
        SUBMISSIONS,
        json={"projectId": "guarani-mbya", "answers": answers(image="any")},
        headers={**headers, "If-Match": '"1"'},
    )

    assert response.status_code == 400, response.text
    assert "through the team's own link" in response.json()["detail"]


async def test_a_box_answered_with_a_word_is_a_fault(client, db_session, headers, project) -> None:
    link = await a_link(client, headers)

    response = await submit(client, link["token"], imageAuthorized="sim")

    assert response.status_code == 400
    assert "true or false" in response.json()["detail"]


# --- before the import: the image reaches no surface ----------------------------------------------


async def test_before_the_import_the_record_and_the_card_show_no_photo(
    client, db_session, headers, project, bucket
) -> None:
    await a_pulse_with_image(client, db_session, headers)

    record = (await client.get(f"{PROJECTS}/guarani-mbya", headers=headers)).json()
    page = (await client.get(PROJECTS, headers=headers)).json()

    assert record["mediaPhotos"] in (None, [])
    card = next(item for item in page["items"] if item["id"] == "guarani-mbya")
    assert card["hasMedia"] is False
    assert (await db_session.execute(select(ShemaMediaItem))).scalars().all() == []


async def test_the_inbox_shows_the_coordinator_the_three_answers_and_no_key(
    client, db_session, headers, project, bucket
) -> None:
    image_id, submission_id = await a_pulse_with_image(client, db_session, headers)

    detail = (await client.get(f"{SUBMISSIONS}/{submission_id}", headers=headers)).json()

    assert detail["answers"]["image"] == image_id
    assert detail["answers"]["imageDescription"] == DESCRIPTION
    assert detail["answers"]["imageAuthorized"] is True
    assert "shema/media" not in json.dumps(detail) and "signed.example" not in json.dumps(detail)
    assert {f["key"] for f in detail["fields"]} >= set(IMAGE_ANSWERS)
    assert {f["type"] for f in detail["fields"] if f["key"] in IMAGE_ANSWERS} == {
        "image",
        "longText",
        "checkbox",
    }


# --- the import: the record's photo, with the leader's answer as its authorization ----------------


async def test_the_import_mints_the_photo_authorized_as_the_leader_said(
    client, db_session, headers, project, bucket
) -> None:
    image_id, submission_id = await a_pulse_with_image(client, db_session, headers)

    imported = await _import(client, headers, submission_id)
    assert imported.status_code == 200, imported.text

    photo = (await db_session.execute(select(ShemaMediaItem))).scalar_one()
    image = await db_session.get(ShemaIntakeImage, image_id)
    assert image is not None and image.media_item_id == photo.id
    assert photo.storage_key == image.storage_key and photo.caption == DESCRIPTION
    assert photo.kind.value == "photo" and photo.file_name == FILE_NAME
    assert photo.authorization_granted is True
    assert photo.authorized_by == "Kuaray"
    record = (await client.get(f"{PROJECTS}/guarani-mbya", headers=headers)).json()
    [shown] = record["mediaPhotos"]
    assert shown["caption"] == DESCRIPTION and shown["authorization"]["granted"] is True
    page = (await client.get(PROJECTS, headers=headers)).json()
    assert next(c for c in page["items"] if c["id"] == "guarani-mbya")["hasMedia"] is True


@pytest.mark.parametrize("authorized", [False, None], ids=["box-unchecked", "box-absent"])
async def test_without_the_authorization_the_photo_is_undecided_and_leaves_nowhere(
    client, db_session, headers, project, bucket, authorized
) -> None:
    """*Absence of consent is not consent*: an unchecked or missing box is **undecided**, never a
    refusal the server invented — and undecided reaches no output, as on every photo."""
    _image_id, submission_id = await a_pulse_with_image(
        client, db_session, headers, authorized=authorized
    )
    assert (await _import(client, headers, submission_id)).status_code == 200

    photo = (await db_session.execute(select(ShemaMediaItem))).scalar_one()
    assert photo.authorization_granted is None and photo.authorized_by is None
    record = (await client.get(f"{PROJECTS}/guarani-mbya", headers=headers)).json()
    assert record["mediaPhotos"][0]["authorization"] is None
    await _assert_no_output_carries(client, db_session, headers, project, photo, bucket)


async def test_a_second_apply_mints_no_second_photo(
    client, db_session, headers, project, bucket
) -> None:
    _image_id, submission_id = await a_pulse_with_image(client, db_session, headers)
    assert (await _import(client, headers, submission_id)).status_code == 200

    again = await _import(client, headers, submission_id)

    assert again.status_code == 200, again.text
    assert len((await db_session.execute(select(ShemaMediaItem))).scalars().all()) == 1


# --- every output ---------------------------------------------------------------------------------


async def _assert_no_output_carries(client, db_session, headers, project, photo, bucket) -> None:
    """The wall, the Pulse, the export, the signed URL: none of them carries the photo."""
    scope = await region_scope(db_session, await _coordinator_user(db_session), APP_KEY)
    with pytest.raises(Exception, match="not shared"):
        await media_download_url(
            db_session, scope, project.id, photo.id, user=await _coordinator_user(db_session)
        )
    assert bucket.signed == []
    for path, params in ((WALL, {}), (EXPORT, {"format": "json"}), (EXPORT, {"format": "csv"})):
        response = await client.get(path, params=params, headers=headers)
        assert response.status_code == 200, (path, response.text)
        assert photo.storage_key not in response.text and DESCRIPTION not in response.text
        assert "signed.example" not in response.text and FILE_NAME not in response.text


async def _coordinator_user(db_session):
    from app.db.models.auth import User

    return (
        await db_session.execute(select(User).where(User.email == "coordenacao@pulso.test"))
    ).scalar_one()


async def test_an_authorized_photo_reaches_the_coordination_and_only_as_a_signed_link(
    client, db_session, headers, project, bucket
) -> None:
    """The one door the bytes leave by: a 15-minute signed GET, minted per call, behind the
    three gates of ``can_share_media``. The wall, the Pulse and the export still carry nothing of
    it — they are text, and OBT-389 keeps the sent Pulse out of this issue."""
    _image_id, submission_id = await a_pulse_with_image(client, db_session, headers)
    assert (await _import(client, headers, submission_id)).status_code == 200
    photo = (await db_session.execute(select(ShemaMediaItem))).scalar_one()
    me = await _coordinator_user(db_session)
    scope = await region_scope(db_session, me, APP_KEY)

    link = await media_download_url(db_session, scope, project.id, photo.id, user=me)

    assert link.url.startswith("https://signed.example/") and link.expires_in_minutes == 15
    assert bucket.signed == [("shema-private", photo.storage_key)]
    for path, params in ((WALL, {}), (EXPORT, {"format": "json"}), (EXPORT, {"format": "csv"})):
        text = (await client.get(path, params=params, headers=headers)).text
        assert photo.storage_key not in text and "signed.example" not in text
        assert DESCRIPTION not in text


async def test_the_prayer_pulse_carries_no_image_whatever_was_authorized(
    client, db_session, shema_app, headers, project, bucket
) -> None:
    """Out of scope by Daniel's decision (OBT-389): the sent Pulse is text and stays text."""
    _image_id, submission_id = await a_pulse_with_image(client, db_session, headers)
    assert (await _import(client, headers, submission_id)).status_code == 200
    photo = (await db_session.execute(select(ShemaMediaItem))).scalar_one()
    circle = await make_scoped_user(
        db_session,
        shema_app,
        email="circulo@pulso.test",
        role_key="resourceCircle",
        regions=[ShemaRegionKey.SOUTH_AMERICA],
    )

    pulse = await client.get(PULSE, headers=await auth_header(db_session, circle))

    assert pulse.status_code == 200, pulse.text
    assert photo.storage_key not in pulse.text and DESCRIPTION not in pulse.text
    assert FILE_NAME not in pulse.text and "signed.example" not in pulse.text


async def test_on_a_sensitive_project_an_authorized_photo_never_reaches_the_public_audience(
    client, db_session, headers, bucket
) -> None:
    """Question 4, the safe option Daniel chose (8/oct/2026): until OBT-575 exists, the image of a
    sensitive project goes to ``coordenacao`` only — the composed rule ``can_share_media`` already
    had, exercised on a Pulse-born photo."""
    project = await _project(db_session, sensitive=True)
    _image_id, submission_id = await a_pulse_with_image(client, db_session, headers)
    assert (await _import(client, headers, submission_id)).status_code == 200
    photo = (await db_session.execute(select(ShemaMediaItem))).scalar_one()
    me = await _coordinator_user(db_session)
    scope = await region_scope(db_session, me, APP_KEY)

    ours = await media_download_url(db_session, scope, project.id, photo.id, user=me)
    with pytest.raises(Exception, match="not shared"):
        await media_download_url(
            db_session, scope, project.id, photo.id, user=me, audience=ShemaAudience.PUBLICO
        )

    assert ours.url.startswith("https://signed.example/")
    assert bucket.signed == [("shema-private", photo.storage_key)]


# --- the caption is free text, and the ficha reduces it for the reader it reduces the rest for


async def _lab_headers(db_session, shema_app):
    lab = await make_scoped_user(
        db_session,
        shema_app,
        email="obtlab@pulso.test",
        role_key="obtLab",
        regions=[ShemaRegionKey.SOUTH_AMERICA],
    )
    return await auth_header(db_session, lab)


async def test_on_a_sensitive_project_the_caption_reaches_the_coordination_and_not_the_obt_lab(
    client, db_session, shema_app, headers, bucket
) -> None:
    """Found in review: the caption is the leader's sentence about the photo and can name the
    place, as the four fields OBT-556 empties for the ``other`` reader can — and it reached the
    ficha whatever the authorization said, because the authorization gates the bytes. The OBT
    Lab reads the slot with an empty caption, and the decision **without the leader's name**
    (Daniel, 8/oct/2026: ``by`` is ``submittedBy`` on a Pulse-born photo) but with ``granted``
    and the day; the region's coordinator reads every word. A cleared project is the truth for
    both (next test)."""
    project = await _project(db_session, sensitive=True)
    _image_id, submission_id = await a_pulse_with_image(client, db_session, headers)
    assert (await _import(client, headers, submission_id)).status_code == 200

    lab = await client.get(
        f"{PROJECTS}/{project.id}", headers=await _lab_headers(db_session, shema_app)
    )
    ours = await client.get(f"{PROJECTS}/{project.id}", headers=headers)

    assert lab.status_code == 200, lab.text
    assert lab.json()["readAs"] == "other" and lab.json()["locationWithheld"] is True
    assert DESCRIPTION not in lab.text and FILE_NAME not in lab.text
    [reduced] = lab.json()["mediaPhotos"]
    assert reduced["caption"] == ""
    decision = reduced["authorization"]
    assert set(decision) == {"granted", "by", "at"}
    assert decision["granted"] is True and decision["by"] == "" and decision["at"] is not None
    assert "Kuaray" not in lab.text
    assert ours.json()["readAs"] == "coordination"
    [whole] = ours.json()["mediaPhotos"]
    assert whole["caption"] == DESCRIPTION and whole["authorization"]["by"] == "Kuaray"


async def test_on_a_cleared_project_the_obt_lab_reads_the_caption_whole(
    client, db_session, shema_app, headers, project, bucket
) -> None:
    _image_id, submission_id = await a_pulse_with_image(client, db_session, headers)
    assert (await _import(client, headers, submission_id)).status_code == 200

    lab = await client.get(
        f"{PROJECTS}/{project.id}", headers=await _lab_headers(db_session, shema_app)
    )

    assert lab.status_code == 200, lab.text
    assert lab.json()["readAs"] == "other" and lab.json()["locationWithheld"] is False
    [whole] = lab.json()["mediaPhotos"]
    assert whole["caption"] == DESCRIPTION and whole["authorization"]["by"] == "Kuaray"


# --- the withdrawal -------------------------------------------------------------------------------


async def test_withdrawing_refuses_the_photo_and_erases_it_from_the_archived_pulse(
    client, db_session, headers, project, bucket
) -> None:
    """Question 5, as Daniel approved it: the reference, the description and the leader's answer
    leave the archived Pulse — removed, not blanked — and the row says who and when, never what.
    The bytes stay in the bucket behind a decision that now refuses them."""
    image_id, submission_id = await a_pulse_with_image(client, db_session, headers)
    assert (await _import(client, headers, submission_id)).status_code == 200
    photo = (await db_session.execute(select(ShemaMediaItem))).scalar_one()

    response = await client.post(
        f"{PROJECTS}/guarani-mbya/media/{photo.id}/authorization/withdraw", headers=headers
    )

    assert response.status_code == 200, response.text
    assert response.json()["granted"] is False
    await db_session.refresh(photo)
    assert photo.authorization_granted is False and photo.authorized_by
    submission = await _submission(db_session)
    kept = json.loads(submission.archived_payload)["answers"]
    assert not set(kept) & set(IMAGE_ANSWERS)
    assert kept["submittedBy"] == "Kuaray"
    assert submission.image_erased_at is not None
    assert submission.image_erased_by == (await _coordinator_user(db_session)).id
    assert (
        DESCRIPTION not in submission.archived_payload
        and image_id not in submission.archived_payload
    )
    image = await db_session.get(ShemaIntakeImage, image_id)
    assert image is not None and image.storage_key == photo.storage_key
    await _assert_no_output_carries(client, db_session, headers, project, photo, bucket)
    detail = (await client.get(f"{SUBMISSIONS}/{submission_id}", headers=headers)).json()
    assert not set(detail["answers"]) & set(IMAGE_ANSWERS)


async def test_withdrawing_twice_changes_nothing_the_second_time(
    client, db_session, headers, project, bucket
) -> None:
    _image_id, submission_id = await a_pulse_with_image(client, db_session, headers)
    assert (await _import(client, headers, submission_id)).status_code == 200
    photo = (await db_session.execute(select(ShemaMediaItem))).scalar_one()
    path = f"{PROJECTS}/guarani-mbya/media/{photo.id}/authorization/withdraw"
    first = await client.post(path, headers=headers)
    assert first.status_code == 200
    stamped = (await _submission(db_session)).image_erased_at

    await db_session.refresh(photo)
    first_decision = (photo.authorized_by, photo.authorized_at)

    second = await client.post(path, headers=headers)

    assert second.status_code == 200
    await db_session.refresh(photo)
    assert photo.authorization_granted is False
    assert (photo.authorized_by, photo.authorized_at) == first_decision
    assert (await _submission(db_session)).image_erased_at == stamped
    assert (await _submission(db_session)).archived_payload == (
        await _submission(db_session)
    ).archived_payload


@pytest.mark.parametrize("role", ["obtLab", "resourceCircle"])
async def test_only_the_coordination_withdraws(
    client, db_session, shema_app, headers, project, bucket, role
) -> None:
    _image_id, submission_id = await a_pulse_with_image(client, db_session, headers)
    assert (await _import(client, headers, submission_id)).status_code == 200
    photo = (await db_session.execute(select(ShemaMediaItem))).scalar_one()
    other = await make_scoped_user(
        db_session,
        shema_app,
        email=f"{role}@pulso.test",
        role_key=role,
        regions=[ShemaRegionKey.SOUTH_AMERICA],
    )

    response = await client.post(
        f"{PROJECTS}/guarani-mbya/media/{photo.id}/authorization/withdraw",
        headers=await auth_header(db_session, other),
    )

    assert response.status_code == 403, response.text
    await db_session.refresh(photo)
    assert photo.authorization_granted is True


async def test_a_withdrawal_outside_the_scope_is_not_found(
    client, db_session, shema_app, headers, project, bucket
) -> None:
    _image_id, submission_id = await a_pulse_with_image(client, db_session, headers)
    assert (await _import(client, headers, submission_id)).status_code == 200
    photo = (await db_session.execute(select(ShemaMediaItem))).scalar_one()
    elsewhere = await make_scoped_user(
        db_session,
        shema_app,
        email="africa@pulso.test",
        role_key="coordinator",
        regions=[ShemaRegionKey.AFRICA],
    )

    response = await client.post(
        f"{PROJECTS}/guarani-mbya/media/{photo.id}/authorization/withdraw",
        headers=await auth_header(db_session, elsewhere),
    )

    assert response.status_code == 404
    assert DESCRIPTION not in response.text
