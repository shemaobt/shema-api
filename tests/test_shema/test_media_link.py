"""OBT-581: a photo's bytes have one door, a signed link minted per call; the record carries the id.

What the console needed and did not have after OBT-578: the photo's ``id`` on the record, to ask
for the bytes and to withdraw the authorization, and a route that answers with the fifteen-minute
link ``media_download_url`` already minted for nobody. Held here, per output: the id reaches every
reader of the record; the link reaches the coordination for an authorized photo and nobody for an
unauthorized one **on the same project**; on a withheld project the OBT Lab (``other``) is refused
the link it would otherwise turn the reduced slot into (Daniel, 8/oct/2026: the image of a
sensitive project is the coordination's until OBT-575); outside the scope the item is not found.

No account here is an installation admin: they pass every guard, and a refusal asserted with one
would pass for the wrong reason. The bucket is a fake that records what it signed — the
``test_privacy.py`` mould.
"""

from __future__ import annotations

import pytest

from app.db.models.shema_enums import ShemaMediaKind, ShemaRegionKey
from app.db.models.shema_media import ShemaMediaItem
from app.services.oral_collector import gcs_utils
from app.services.shema._media_storage import DOWNLOAD_URL_EXPIRY_MINUTES, MEDIA, storage_key
from tests.test_shema.conftest import PREFIX, auth_header, make_scoped_user, make_shema_project

PROJECTS = f"{PREFIX}/projects"
HERE = ShemaRegionKey.SOUTH_AMERICA
CAPTION = "LEGENDA-SIGILOSA a equipe no vale"


class FakeBucket:
    def __init__(self) -> None:
        self.signed: list[tuple[str, str, int]] = []

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
    monkeypatch.setattr(gcs_utils, "generate_signed_download_url", fake.sign)
    return fake


async def _headers(db_session, shema_app, role: str, *, regions=(HERE,)):
    user = await make_scoped_user(
        db_session,
        shema_app,
        email=f"{role.lower()}-{'-'.join(r.value for r in regions)}@link.test",
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


async def _photo(db_session, project, *, granted: bool | None, by: str = "Kuaray"):
    item = ShemaMediaItem(
        project_id=project.id,
        kind=ShemaMediaKind.PHOTO,
        storage_key=storage_key(MEDIA, f"row-{granted}", "a" * 64, ".jpg"),
        file_name="equipe no vale.jpg",
        caption=CAPTION,
        authorization_granted=granted,
        authorized_by=by if granted is not None else None,
    )
    db_session.add(item)
    await db_session.commit()
    return item


def _link(project_id: str, item_id: str) -> str:
    return f"{PROJECTS}/{project_id}/media/{item_id}/link"


# --- the id, for every reader ------------------------------------------------------------------


async def test_the_record_carries_the_photos_id_for_every_reader(
    client, db_session, shema_app
) -> None:
    """The id is what the console hands back to the link and the withdrawal; it names no place
    and no person, so the reader handed the reduction gets it too — beside the emptied caption."""
    project = await _project(db_session, sensitive=True)
    photo = await _photo(db_session, project, granted=True)

    ours = await client.get(
        f"{PROJECTS}/{project.id}", headers=await _headers(db_session, shema_app, "coordinator")
    )
    theirs = await client.get(
        f"{PROJECTS}/{project.id}", headers=await _headers(db_session, shema_app, "obtLab")
    )

    [whole] = ours.json()["mediaPhotos"]
    assert whole["id"] == photo.id and whole["caption"] == CAPTION and whole["image"] is None
    [reduced] = theirs.json()["mediaPhotos"]
    assert theirs.json()["readAs"] == "other"
    assert reduced["id"] == photo.id and reduced["caption"] == ""
    assert "signed.example" not in ours.text and photo.storage_key not in ours.text


async def test_the_id_on_the_record_is_the_one_the_withdrawal_takes(
    client, db_session, shema_app, bucket
) -> None:
    """DoD 1, end to end: read the id off the record, withdraw with it, and the link closes."""
    project = await _project(db_session)
    await _photo(db_session, project, granted=True)
    headers = await _headers(db_session, shema_app, "coordinator")
    [shown] = (await client.get(f"{PROJECTS}/{project.id}", headers=headers)).json()["mediaPhotos"]
    assert (await client.get(_link(project.id, shown["id"]), headers=headers)).status_code == 200

    withdrawn = await client.post(
        f"{PROJECTS}/{project.id}/media/{shown['id']}/authorization/withdraw", headers=headers
    )

    assert withdrawn.status_code == 200, withdrawn.text
    assert withdrawn.json()["granted"] is False
    after = await client.get(_link(project.id, shown["id"]), headers=headers)
    assert after.status_code == 403
    assert len(bucket.signed) == 1


# --- the link, per output ------------------------------------------------------------------------


async def test_only_the_authorized_photo_of_a_project_answers_a_link(
    client, db_session, shema_app, bucket
) -> None:
    """DoD 4: two photos on the same project, one authorized and one nobody decided on — the
    coordination gets a fifteen-minute link for the first and a refusal for the second, and the
    bucket signed exactly one key."""
    project = await _project(db_session)
    authorized = await _photo(db_session, project, granted=True)
    undecided = await _photo(db_session, project, granted=None)
    headers = await _headers(db_session, shema_app, "coordinator")

    yes = await client.get(_link(project.id, authorized.id), headers=headers)
    no = await client.get(_link(project.id, undecided.id), headers=headers)

    assert yes.status_code == 200, yes.text
    assert yes.json() == {
        "url": f"https://signed.example/{authorized.storage_key}?minutes=15",
        "expiresInMinutes": DOWNLOAD_URL_EXPIRY_MINUTES,
    }
    assert yes.headers["cache-control"] == "private, no-store"
    assert no.status_code == 403, no.text
    assert "signed.example" not in no.text and undecided.storage_key not in no.text
    assert bucket.signed == [("shema-private", authorized.storage_key, 15)]


async def test_a_refused_photo_answers_the_same_sentence_as_an_undecided_one(
    client, db_session, shema_app, bucket
) -> None:
    project = await _project(db_session)
    refused = await _photo(db_session, project, granted=False)
    undecided = await _photo(db_session, project, granted=None)
    headers = await _headers(db_session, shema_app, "coordinator")

    first = await client.get(_link(project.id, refused.id), headers=headers)
    second = await client.get(_link(project.id, undecided.id), headers=headers)

    assert first.status_code == second.status_code == 403
    assert first.json()["detail"] == second.json()["detail"]
    assert bucket.signed == []


@pytest.mark.parametrize("role", ["obtLab", "resourceCircle"])
async def test_on_a_withheld_project_nobody_but_the_coordination_gets_a_link(
    client, db_session, shema_app, bucket, role
) -> None:
    """Daniel, 9/oct/2026 (option b): the image of a sensitive project is the coordination's
    **only** until OBT-575 — the OBT Lab, handed the reduction, and the Resource Circle, which
    reads the record's truth (OBT-571) but not these bytes. The photo is authorized; what
    refuses it is who is asking — with the sentence an unauthorized item gets, so the refusal
    says nothing about the project."""
    project = await _project(db_session, sensitive=True)
    photo = await _photo(db_session, project, granted=True)

    theirs = await client.get(
        _link(project.id, photo.id), headers=await _headers(db_session, shema_app, role)
    )
    ours = await client.get(
        _link(project.id, photo.id), headers=await _headers(db_session, shema_app, "coordinator")
    )

    assert theirs.status_code == 403, theirs.text
    assert "signed.example" not in theirs.text
    assert ours.status_code == 200, ours.text
    assert bucket.signed == [("shema-private", photo.storage_key, 15)]


@pytest.mark.parametrize("role", ["obtLab", "resourceCircle"])
async def test_on_a_cleared_project_the_same_readers_get_the_link(
    client, db_session, shema_app, bucket, role
) -> None:
    """Only a withheld project is the coordination's alone: on a cleared one the authorized
    photo reaches whoever reaches the record."""
    project = await _project(db_session)
    photo = await _photo(db_session, project, granted=True)

    res = await client.get(
        _link(project.id, photo.id), headers=await _headers(db_session, shema_app, role)
    )

    assert res.status_code == 200, res.text
    assert res.json()["expiresInMinutes"] == 15


async def test_outside_the_scope_the_item_is_not_found(
    client, db_session, shema_app, bucket
) -> None:
    project = await _project(db_session)
    photo = await _photo(db_session, project, granted=True)

    res = await client.get(
        _link(project.id, photo.id),
        headers=await _headers(
            db_session, shema_app, "coordinator", regions=(ShemaRegionKey.AFRICA,)
        ),
    )

    assert res.status_code == 404, res.text
    assert bucket.signed == []


async def test_an_unknown_item_and_a_photo_with_no_object_are_not_found(
    client, db_session, shema_app, bucket
) -> None:
    project = await _project(db_session)
    headers = await _headers(db_session, shema_app, "coordinator")
    empty = ShemaMediaItem(
        project_id=project.id,
        kind=ShemaMediaKind.PHOTO,
        caption="só legenda",
        authorization_granted=True,
    )
    db_session.add(empty)
    await db_session.commit()

    unknown = await client.get(_link(project.id, "no-such-item"), headers=headers)
    slot = await client.get(_link(project.id, empty.id), headers=headers)

    assert unknown.status_code == slot.status_code == 404
    assert bucket.signed == []
