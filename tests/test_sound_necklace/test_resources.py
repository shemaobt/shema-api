"""Voice answers: the spoken replies of the Mapeamento, kept by their logical path.

Each answer is one WebM/Opus recording, named by the question it answers —
`respostas/level1/<k>.webm`, `respostas/level2/<PT#>/<k>.webm`,
`respostas/level3/<P#>/<k>.webm` (§8.7, O5). The path is a contract, not free-form: the
SPA builds it and the API validates it against a fixed allowlist, so nothing outside
those three shapes — no traversal, no arbitrary key — can name an object.

These recordings are LGPD-sensitive (§12): private bucket only, reached through a
short-TTL signed URL, and this listing/url path is where the audit log will hook (the
same audit point as the artifacts). The bytes are never proxied and, being opaque audio,
never parsed — the API only ever moves them.
"""

from __future__ import annotations

import pytest

from app.services.oral_collector import gcs_utils
from tests.baker import make_language, make_project, make_project_user_access, make_user
from tests.test_sound_necklace.conftest import (
    audio_of,
    auth_header,
    give_project_an_audio,
    grant_role,
)

SN = "/api/sound-necklace"

WEBM = b"\x1a\x45\xdf\xa3 fake webm/opus bytes \x00\x01\x02"
P1 = "respostas/level1/recontar.webm"
P2 = "respostas/level2/PT3/quem.webm"
P3 = "respostas/level3/P12/oque.webm"


@pytest.fixture()
def storage(monkeypatch):
    class FakeStorage:
        def __init__(self) -> None:
            self.objects: dict[str, bytes] = {}
            self.signed: list[dict] = []
            self.deleted: list[str] = []

        async def upload(
            self, bucket: str, key: str, data: bytes, content_type: str, *, content_encoding=None
        ) -> str:
            self.objects[key] = data
            return f"gs://{bucket}/{key}"

        async def sign(
            self, bucket: str, key: str, *, expiry_minutes: int = 15, response_content_type=None
        ) -> str:
            self.signed.append({"bucket": bucket, "key": key, "ttl": expiry_minutes})
            return f"https://storage.googleapis.com/{bucket}/{key}?X-Goog-Signature=beef"

        async def delete(self, bucket: str, key: str) -> None:
            self.deleted.append(key)
            self.objects.pop(key, None)

    fake = FakeStorage()
    monkeypatch.setattr(gcs_utils, "upload_gcs_object", fake.upload)
    monkeypatch.setattr(gcs_utils, "generate_signed_download_url", fake.sign)
    monkeypatch.setattr(gcs_utils, "delete_gcs_object", fake.delete)
    return fake


@pytest.fixture()
async def facilitator(db_session, sound_necklace_app):
    user = await make_user(db_session, email="facilitator@example.com")
    await grant_role(db_session, sound_necklace_app.id, user.id, "facilitator")
    language = await make_language(db_session, name="Terena", code="ter")
    project = await make_project(db_session, language.id, name="Projeto A")
    await give_project_an_audio(db_session, project.id)
    await make_project_user_access(db_session, project.id, user.id)
    headers = await auth_header(db_session, user)
    return user, project, headers


@pytest.fixture()
async def other_project(db_session):
    language = await make_language(db_session, name="Nheengatu", code="yrl")
    other = await make_project(db_session, language.id, name="Projeto B")
    await give_project_an_audio(db_session, other.id)
    return other


async def new_session(client, headers, project_id: str) -> str:
    res = await client.post(
        f"{SN}/sessions",
        headers=headers,
        json={
            "audio_id": audio_of(project_id),
            "project_id": project_id,
            "story_name": "A História de Rute",
            "story_slug": "a-historia-de-rute",
            "granularity_level": "medium",
            "bead_sec": 0.5,
            "manifest_id": "fnv1a32:d31a8419",
            "pipeline_consent": True,
        },
    )
    assert res.status_code == 201, res.text
    return str(res.json()["id"])


async def put_answer(client, headers, session_id: str, path: str, data: bytes = WEBM):
    return await client.put(
        f"{SN}/sessions/{session_id}/resources",
        headers={**headers, "content-type": "audio/webm"},
        params={"path": path},
        content=data,
    )


# ── The path allowlist ───────────────────────────────────────────────────────


@pytest.mark.parametrize("path", [P1, P2, P3])
async def test_the_three_question_shapes_are_accepted(client, facilitator, storage, path):
    _user, project, headers = facilitator
    session_id = await new_session(client, headers, project.id)

    res = await put_answer(client, headers, session_id, path)

    assert res.status_code == 201, res.text
    assert any(key.endswith(path) for key in storage.objects)


@pytest.mark.parametrize(
    "path",
    [
        "respostas/../../etc/passwd",
        "respostas/level1/../../x.webm",
        "/respostas/level1/recontar.webm",
        "respostas/level1/recontar.mp3",
        "respostas/level4/x.webm",
        "respostas/level2/quem.webm",  # missing PT#
        "respostas/level2/P3/quem.webm",  # P# where PT# belongs
        "arbitrary/key.webm",
        "respostas/level1/UPPER.webm",
        # An over-long k would pass an unbounded regex, then blow the VARCHAR(255) on
        # Postgres AFTER the object is already in the private bucket — a 500 and an
        # orphaned recording that SQLite would never surface. The bound makes it a 422.
        "respostas/level1/" + "a" * 300 + ".webm",
        "respostas/level2/PT" + "9" * 300 + "/quem.webm",
    ],
)
async def test_anything_outside_the_allowlist_is_rejected_and_stores_nothing(
    client, facilitator, storage, path
):
    _user, project, headers = facilitator
    session_id = await new_session(client, headers, project.id)

    res = await put_answer(client, headers, session_id, path)

    assert res.status_code == 422, f"{path} was accepted: {res.text}"
    assert storage.objects == {}


# ── The round trip: put → list → url → delete ────────────────────────────────


async def test_an_answer_round_trips_through_the_signed_url(client, facilitator, storage):
    _user, project, headers = facilitator
    session_id = await new_session(client, headers, project.id)
    await put_answer(client, headers, session_id, P1)

    res = await client.get(
        f"{SN}/sessions/{session_id}/resources/url", headers=headers, params={"path": P1}
    )

    assert res.status_code == 200, res.text
    assert res.json()["url"].startswith("https://storage.googleapis.com/sound-necklace-private/")
    (call,) = storage.signed
    assert call["key"].endswith(P1)
    assert call["ttl"] == 15


async def test_the_listing_shows_which_questions_have_an_answer(client, facilitator, storage):
    """The Mapeamento screen needs to know which questions are answered — that is what
    the listing is for, and it is why there is a listing rather than a `has` per path."""
    _user, project, headers = facilitator
    session_id = await new_session(client, headers, project.id)
    await put_answer(client, headers, session_id, P1)
    await put_answer(client, headers, session_id, P3)

    res = await client.get(f"{SN}/sessions/{session_id}/resources", headers=headers)

    assert res.status_code == 200, res.text
    assert sorted(r["path"] for r in res.json()["resources"]) == sorted([P1, P3])


async def test_re_recording_replaces_the_answer_rather_than_adding_one(
    client, facilitator, storage
):
    """O5: one file per question. Re-recording is replace, not append — a single row,
    the new bytes."""
    _user, project, headers = facilitator
    session_id = await new_session(client, headers, project.id)
    await put_answer(client, headers, session_id, P1, b"first take")
    await put_answer(client, headers, session_id, P1, b"second take")

    listing = await client.get(f"{SN}/sessions/{session_id}/resources", headers=headers)

    assert [r["path"] for r in listing.json()["resources"]] == [P1]
    key = next(k for k in storage.objects if k.endswith(P1))
    assert storage.objects[key] == b"second take"


async def test_a_deleted_answer_is_gone_from_the_listing_and_from_storage(
    client, facilitator, storage
):
    _user, project, headers = facilitator
    session_id = await new_session(client, headers, project.id)
    await put_answer(client, headers, session_id, P1)

    res = await client.request(
        "DELETE", f"{SN}/sessions/{session_id}/resources", headers=headers, params={"path": P1}
    )

    assert res.status_code == 204, res.text
    assert storage.deleted and storage.deleted[0].endswith(P1)
    listing = await client.get(f"{SN}/sessions/{session_id}/resources", headers=headers)
    assert listing.json()["resources"] == []


# ── Size cap ─────────────────────────────────────────────────────────────────


async def test_an_oversize_answer_is_rejected_and_nothing_is_stored(client, facilitator, storage):
    """A voice answer is a short spoken reply. The cap is a guard against a client bug or
    a wrong file, and it is enforced before a byte reaches storage."""
    _user, project, headers = facilitator
    session_id = await new_session(client, headers, project.id)

    res = await put_answer(client, headers, session_id, P1, b"x" * (10 * 1024 * 1024 + 1))

    assert res.status_code == 413, res.text
    assert res.json()["code"], res.text
    assert storage.objects == {}


async def test_an_empty_answer_is_rejected_and_nothing_is_stored(client, facilitator, storage):
    """An empty body is a client bug, not a recording — storing it would mark the question
    answered with nothing to play back."""
    _user, project, headers = facilitator
    session_id = await new_session(client, headers, project.id)

    res = await put_answer(client, headers, session_id, P1, b"")

    assert res.status_code == 400, res.text
    assert storage.objects == {}
    listing = await client.get(f"{SN}/sessions/{session_id}/resources", headers=headers)
    assert listing.json()["resources"] == []


# ── Delete is idempotent ─────────────────────────────────────────────────────


async def test_deleting_an_answer_that_was_never_recorded_is_a_no_op(client, facilitator, storage):
    """The caller's goal — no answer at this path — is already met, so deleting one that
    never existed succeeds rather than 404ing."""
    _user, project, headers = facilitator
    session_id = await new_session(client, headers, project.id)

    res = await client.request(
        "DELETE", f"{SN}/sessions/{session_id}/resources", headers=headers, params={"path": P1}
    )

    assert res.status_code == 204, res.text
    assert storage.deleted == []


# ── The gate ─────────────────────────────────────────────────────────────────


async def test_writing_into_another_projects_session_is_denied(
    client, facilitator, other_project, db_session, sound_necklace_app, storage
):
    _user, _project, headers = facilitator
    outsider = await make_user(db_session, email="outsider@example.com")
    await grant_role(db_session, sound_necklace_app.id, outsider.id, "facilitator")
    await make_project_user_access(db_session, other_project.id, outsider.id)
    theirs = await new_session(client, await auth_header(db_session, outsider), other_project.id)

    res = await put_answer(client, headers, theirs, P1)

    assert res.status_code == 403
    assert storage.objects == {}


async def test_reading_another_projects_answer_url_is_denied(
    client, facilitator, other_project, db_session, sound_necklace_app, storage
):
    _user, _project, headers = facilitator
    outsider = await make_user(db_session, email="outsider@example.com")
    await grant_role(db_session, sound_necklace_app.id, outsider.id, "facilitator")
    await make_project_user_access(db_session, other_project.id, outsider.id)
    their_headers = await auth_header(db_session, outsider)
    theirs = await new_session(client, their_headers, other_project.id)
    await put_answer(client, their_headers, theirs, P1)

    res = await client.get(
        f"{SN}/sessions/{theirs}/resources/url", headers=headers, params={"path": P1}
    )

    assert res.status_code == 403
    assert storage.signed == []


async def test_an_answer_never_recorded_is_a_miss(client, facilitator, storage):
    _user, project, headers = facilitator
    session_id = await new_session(client, headers, project.id)

    res = await client.get(
        f"{SN}/sessions/{session_id}/resources/url", headers=headers, params={"path": P1}
    )

    assert res.status_code == 404
    assert storage.signed == []


async def test_listing_another_projects_answers_is_denied(
    client, facilitator, other_project, db_session, sound_necklace_app, storage
):
    """Which questions a session has answered is itself scoped — a non-member cannot
    read another project's answer inventory."""
    _user, _project, headers = facilitator
    outsider = await make_user(db_session, email="outsider@example.com")
    await grant_role(db_session, sound_necklace_app.id, outsider.id, "facilitator")
    await make_project_user_access(db_session, other_project.id, outsider.id)
    theirs = await new_session(client, await auth_header(db_session, outsider), other_project.id)

    res = await client.get(f"{SN}/sessions/{theirs}/resources", headers=headers)

    assert res.status_code == 403
