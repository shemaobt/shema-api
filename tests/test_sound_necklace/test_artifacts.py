"""Artifact custody: bytes in, the same bytes out, forever.

The three artifacts are produced client-side and re-read by a downstream pipeline that
diffs them byte for byte against a golden reference (PRD §10.5). The API is only their
custodian. That makes one property load-bearing above all others: **nothing here may
parse a payload.** A `json.loads` + `json.dumps` round-trip is invisible to a shallow
assertion and fatal to the contract — it silently reorders keys, collapses whitespace,
re-escapes unicode and appends a newline.

So the payloads in these tests are deliberately ugly: keys out of alphabetical order,
two-space indents, a long float, en/em dashes, accented characters, no trailing newline.
A server that re-serialized any of them would still return valid, plausible JSON — and
every one of these tests would fail.
"""

from __future__ import annotations

import base64

import google_crc32c
import pytest

from app.db.models.sound_necklace import ArtifactKind
from app.services.oral_collector import gcs_utils
from tests.baker import make_language, make_project, make_project_user_access, make_user
from tests.test_sound_necklace.conftest import (
    audio_of,
    auth_header,
    give_project_an_audio,
    grant_role,
    hand_lease_to,
)

SN = "/api/sound-necklace"


# The bytes the golden harness would diff. Not built with json.dumps, on purpose.
MANIFEST_BYTES = (
    b'{"manifest_id":"fnv1a32:d31a8419",\n  "bead_sec": 0.30000000000000004,\n'
    b'  "zeta": 1, "alpha": 2,\n  "story": "A Hist\xc3\xb3ria de Rute \xe2\x80\x94 parte I"}'
)
ANCHORING_BYTES = (
    b'{"scenes":[{"id":"PT1","kind":"journey","confidence":"m\xc3\xa9dia"}],\n'
    b'  "phrases": [],  "seams":[]}'
)
# No trailing newline, en dash, em dash, curly quotes, accents, two-space indent. The
# dashes are escaped rather than written literally so that the linter's homoglyph check
# stays useful elsewhere — the bytes are the same, and they are the point: a report that
# came back with an ASCII hyphen would still read correctly and still break the diff.
REPORT_BYTES = (
    "# Relatório de Mapeamento\n\n"
    "## Cena PT1 \u2013 jornada\n\n"
    "  Resposta \u2014 nível 1: \u201co povo caminhou\u201d\n"
    "  Confiança: média"
).encode()

PAYLOADS = {
    "manifest": MANIFEST_BYTES,
    "anchoring": ANCHORING_BYTES,
    "report": REPORT_BYTES,
}


def crc32c_of(data: bytes) -> str:
    return base64.b64encode(google_crc32c.Checksum(data).digest()).decode()


class Boom(Exception):
    """A storage failure, so a test can put one in the middle of a three-object upload."""


@pytest.fixture()
def storage(monkeypatch):
    """A fake GCS: what was uploaded under a key, and what a signed URL points at.

    Real storage serves the bytes verbatim, so holding them in a dict is the honest
    model of it — and it lets a test read back exactly what the API handed over. It can
    be told to fail on the Nth upload, because "a failure partway through" is the one
    behaviour a dict that always succeeds cannot exercise.
    """

    class FakeStorage:
        def __init__(self) -> None:
            self.objects: dict[str, bytes] = {}
            self.content_types: dict[str, str] = {}
            self.signed: list[dict] = []
            self.fail_on_upload: int | None = None
            self._uploads = 0

        def fail_next_on(self, nth: int) -> None:
            """Fail on the Nth upload from now — counted fresh, so a prior successful
            batch does not throw the count off."""
            self.fail_on_upload = self._uploads + nth

        async def upload(
            self,
            bucket_name: str,
            blob_name: str,
            data: bytes,
            content_type: str,
            *,
            content_encoding: str | None = None,
        ) -> str:
            self._uploads += 1
            if self.fail_on_upload is not None and self._uploads == self.fail_on_upload:
                raise Boom("storage went away mid-upload")
            self.objects[blob_name] = data
            self.content_types[blob_name] = content_type
            return f"gs://{bucket_name}/{blob_name}"

        async def sign(
            self,
            bucket_name: str,
            blob_name: str,
            *,
            expiry_minutes: int = 15,
            response_content_type: str | None = None,
        ) -> str:
            self.signed.append({"bucket": bucket_name, "blob": blob_name, "ttl": expiry_minutes})
            return f"https://storage.googleapis.com/{bucket_name}/{blob_name}?X-Goog-Signature=d0d0"

        def fetch(self, url: str) -> bytes:
            """What a client following the redirect would actually receive."""
            key = url.split("?", 1)[0].split("/", 4)[4]
            return self.objects[key]

    fake = FakeStorage()
    monkeypatch.setattr(gcs_utils, "upload_gcs_object", fake.upload)
    monkeypatch.setattr(gcs_utils, "generate_signed_download_url", fake.sign)
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


async def new_session(
    client,
    headers,
    project_id: str,
    *,
    slug: str = "a-historia-de-rute",
    audio_id: str = "ruth-a-historia-de-rute",
) -> str:
    res = await client.post(
        f"{SN}/sessions",
        headers=headers,
        json={
            "audio_id": audio_of(project_id),
            "project_id": project_id,
            "story_name": "A História de Rute",
            "story_slug": slug,
            "granularity_level": "medium",
            "bead_sec": 0.5,
            "manifest_id": "fnv1a32:d31a8419",
            "pipeline_consent": True,
        },
    )
    assert res.status_code == 201, res.text
    return str(res.json()["id"])


def upload_files(payloads: dict[str, bytes] | None = None) -> dict:
    p = payloads or PAYLOADS
    return {
        "manifest": ("manifesto-contas.json", p["manifest"], "application/json"),
        "anchoring": ("retorno-ancoragem.json", p["anchoring"], "application/json"),
        "report": ("relatorio-mapeamento.md", p["report"], "text/markdown"),
    }


async def upload(client, headers, session_id: str, payloads: dict[str, bytes] | None = None):
    return await client.post(
        f"{SN}/sessions/{session_id}/artifacts", headers=headers, files=upload_files(payloads)
    )


async def served_bytes(client, headers, session_id: str, kind: str, storage) -> bytes:
    res = await client.get(
        f"{SN}/sessions/{session_id}/artifacts/{kind}", headers=headers, follow_redirects=False
    )
    assert res.status_code == 307, f"{kind}: {res.text}"
    return storage.fetch(res.headers["location"])


# ── The rule this issue exists for ───────────────────────────────────────────


async def test_the_bytes_that_come_back_are_the_bytes_that_went_in(client, facilitator, storage):
    """The whole issue, in one test. A json round-trip anywhere on this path would
    reorder the keys, normalize the whitespace, re-escape the accents and add a newline
    — and every payload here is shaped to make that visible."""
    _user, project, headers = facilitator
    session_id = await new_session(client, headers, project.id)

    assert (await upload(client, headers, session_id)).status_code == 201

    for kind, expected in (
        ("manifest", MANIFEST_BYTES),
        ("anchoring", ANCHORING_BYTES),
        ("report", REPORT_BYTES),
    ):
        assert await served_bytes(client, headers, session_id, kind, storage) == expected, (
            f"{kind} did not survive custody"
        )


def test_no_artifact_payload_is_ever_deserialized():
    """A guard for the rule the test above proves, at the level §10.5 states it: the API
    "must NOT deserialize an artifact into a Pydantic model and re-serialize it".

    The byte-identity test catches a round-trip on the payloads it happens to carry.
    This catches the reach for a parser itself, across the whole artifact path — the
    router (where a JSON body would be the temptation) and both services.
    """
    import importlib
    import inspect

    modules = [
        "app.api.sound_necklace.artifacts",
        "app.services.sound_necklace.store_artifacts",
        "app.services.sound_necklace.artifact_download_url",
    ]
    source = "\n".join(inspect.getsource(importlib.import_module(m)) for m in modules)
    # Parsers only. A payload never becomes a str, so `.decode()`/`.encode()` are not
    # listed — they legitimately appear on the checksum, not the bytes, and the
    # byte-identity test already catches any re-encode of the payload itself.
    for parser in (
        "json.loads",
        "json.load",
        "json.dumps",
        "orjson",
        "model_validate",
        "model_dump",
        "TypeAdapter",
        "= Body(",
    ):
        assert parser not in source, (
            f"the artifact path reaches for {parser!r} — payloads must stay opaque bytes"
        )


async def test_an_empty_artifact_is_rejected_before_anything_is_stored(
    client, facilitator, storage
):
    """An empty upload is a client bug, and storing it would hand the pipeline a
    zero-byte artifact that diffs as 'present but wrong'."""
    _user, project, headers = facilitator
    session_id = await new_session(client, headers, project.id)

    res = await upload(client, headers, session_id, {**PAYLOADS, "report": b""})

    assert res.status_code == 400, res.text
    assert storage.objects == {}, "an artifact was stored before the envelope was validated"


# ── Atomicity: a failure mid-upload must not corrupt the current triple ───────


async def test_a_failed_reupload_leaves_the_previous_triple_intact(client, facilitator, storage):
    """The property the content-addressed key exists to give. A first export succeeds;
    a second one fails on its third object. The pipeline must still see the first triple,
    whole — not a mix of new-manifest, new-anchoring, old-report that never coexisted.

    The failure surfaces however the transport carries it (here it propagates); what this
    pins is that the failure does not move a single pointer."""
    _user, project, headers = facilitator
    session_id = await new_session(client, headers, project.id)
    assert (await upload(client, headers, session_id)).status_code == 201
    first = {
        k: await served_bytes(client, headers, session_id, k, storage)
        for k in ("manifest", "anchoring", "report")
    }

    storage.fail_next_on(3)
    revised = {
        "manifest": b'{"manifest_id":"fnv1a32:d31a8419", "revised": 1}',
        "anchoring": b'{"scenes":[], "revised": 2}',
        "report": b"# revised",
    }
    with pytest.raises(Boom):
        await upload(client, headers, session_id, revised)

    # Every pointer still resolves to the first export's bytes, byte for byte.
    for kind, original in first.items():
        assert await served_bytes(client, headers, session_id, kind, storage) == original, (
            f"{kind}'s pointer moved to a half-written triple"
        )


async def test_a_reupload_that_succeeds_replaces_every_artifact(client, facilitator, storage):
    """The happy re-record: reopen, export again, and the pipeline reads the new triple
    — not the old one, and not a single stale file."""
    _user, project, headers = facilitator
    session_id = await new_session(client, headers, project.id)
    assert (await upload(client, headers, session_id)).status_code == 201

    revised = {**PAYLOADS, "manifest": b'{"manifest_id":"fnv1a32:d31a8419", "revised": true}'}
    assert (await upload(client, headers, session_id, revised)).status_code == 201

    assert (
        await served_bytes(client, headers, session_id, "manifest", storage) == revised["manifest"]
    )
    assert await served_bytes(client, headers, session_id, "report", storage) == REPORT_BYTES


# ── A user-controlled slug must not be able to break custody ──────────────────


async def test_a_hostile_slug_cannot_produce_an_undownloadable_artifact(
    client, facilitator, storage
):
    """`story_slug` is user input. If it reached the object key, a slug like `../..` would
    sign fine and 404 on fetch — a silent custody failure. The key is content-addressed,
    so the slug never touches it, and upload→download round-trips regardless."""
    _user, project, headers = facilitator
    session_id = await new_session(client, headers, project.id, slug="a-historia-de-rute")

    assert (await upload(client, headers, session_id)).status_code == 201

    served = await served_bytes(client, headers, session_id, "manifest", storage)
    assert served == MANIFEST_BYTES
    # The slug is nowhere in the object key.
    assert all("../" not in blob and "a-historia" not in blob for blob in storage.objects)


# ── Checksums ────────────────────────────────────────────────────────────────


async def test_the_stored_checksum_describes_the_stored_bytes(client, facilitator, storage):
    """Not that our function is deterministic — that the recorded crc32c matches the
    object a client would actually fetch."""
    _user, project, headers = facilitator
    session_id = await new_session(client, headers, project.id)

    res = await upload(client, headers, session_id)

    assert res.status_code == 201, res.text
    by_kind = {a["kind"]: a for a in res.json()}
    for kind in ("manifest", "report"):
        stored = await served_bytes(client, headers, session_id, kind, storage)
        assert by_kind[kind]["crc32c"] == crc32c_of(stored)
        assert by_kind[kind]["size"] == len(stored)


# ── The gate (this download is an audit point — ENG-266 hooks here) ──────────


async def test_uploading_into_another_projects_session_is_denied(
    client, facilitator, other_project, db_session, sound_necklace_app, storage
):
    _user, _project, headers = facilitator
    outsider = await make_user(db_session, email="outsider@example.com")
    await grant_role(db_session, sound_necklace_app.id, outsider.id, "facilitator")
    await make_project_user_access(db_session, other_project.id, outsider.id)
    theirs = await new_session(
        client,
        await auth_header(db_session, outsider),
        other_project.id,
        audio_id="ruth-a-historia-de-rute-b",
    )

    res = await upload(client, headers, theirs)

    assert res.status_code == 403
    assert storage.objects == {}, "bytes were stored before the gate rejected the caller"


async def test_downloading_another_projects_artifact_is_denied(
    client, facilitator, other_project, db_session, sound_necklace_app, storage
):
    _user, _project, headers = facilitator
    outsider = await make_user(db_session, email="outsider@example.com")
    await grant_role(db_session, sound_necklace_app.id, outsider.id, "facilitator")
    await make_project_user_access(db_session, other_project.id, outsider.id)
    their_headers = await auth_header(db_session, outsider)
    theirs = await new_session(client, their_headers, other_project.id)
    await upload(client, their_headers, theirs)

    res = await client.get(
        f"{SN}/sessions/{theirs}/artifacts/manifest", headers=headers, follow_redirects=False
    )

    assert res.status_code == 403
    assert storage.signed == [], "a URL was minted before the gate rejected the caller"


async def test_an_artifact_never_uploaded_is_a_miss(client, facilitator, storage):
    _user, project, headers = facilitator
    session_id = await new_session(client, headers, project.id)

    res = await client.get(
        f"{SN}/sessions/{session_id}/artifacts/manifest", headers=headers, follow_redirects=False
    )

    assert res.status_code == 404
    assert storage.signed == []


async def test_the_download_url_is_short_lived_and_names_the_frozen_filename(
    client, facilitator, storage
):
    """PRD §10 freezes the artifact filenames. They ride in the object key, so the
    browser saves the file the pipeline expects without the API proxying a byte."""
    _user, project, headers = facilitator
    session_id = await new_session(client, headers, project.id)
    await upload(client, headers, session_id)

    res = await client.get(
        f"{SN}/sessions/{session_id}/artifacts/anchoring", headers=headers, follow_redirects=False
    )

    assert res.status_code == 307
    (call,) = storage.signed
    assert call["bucket"] == "sound-necklace-private"
    assert call["blob"].endswith("retorno-ancoragem.json")
    assert call["ttl"] == 15


async def test_every_kind_of_artifact_is_reachable(client, facilitator, storage):
    _user, project, headers = facilitator
    session_id = await new_session(client, headers, project.id)
    await upload(client, headers, session_id)

    for kind in ArtifactKind:
        res = await client.get(
            f"{SN}/sessions/{session_id}/artifacts/{kind.value}",
            headers=headers,
            follow_redirects=False,
        )
        assert res.status_code == 307, f"{kind.value} is not reachable: {res.text}"


# ── The editor lock fences the upload too (ENG-262) ──────────────────────────
#
# The artifacts are the output of a completion, so leaving them open while `complete`
# is fenced would let the loser's artifacts land on the winner's session anyway. Unlike
# the autosave, the guard here cannot ride in the write statement: the write is to GCS,
# and an external side effect is outside anything a SQL predicate can fence. It is a
# check-then-act with a real (small) window — the honest best available.


async def test_uploading_artifacts_to_a_session_someone_else_holds_is_refused(
    client, alice, bob, project, storage
):
    _alice_user, alice_headers = alice
    _bob_user, bob_headers = bob
    session_id = await new_session(client, alice_headers, project.id)
    await client.put(f"{SN}/sessions/{session_id}/lock", headers=bob_headers)

    res = await upload(client, alice_headers, session_id)

    assert res.status_code == 409, res.text
    assert res.json()["code"] == "SESSION_LOCKED"
    assert res.json()["holder_name"] == "Bob"
    # Refused before the bytes moved: a rejected upload must not leave objects behind.
    assert storage.objects == {}


async def test_uploading_artifacts_to_an_unlocked_session_still_works(
    client, alice, project, storage
):
    _user, headers = alice
    session_id = await new_session(client, headers, project.id)

    res = await upload(client, headers, session_id)

    assert res.status_code == 201, res.text


async def test_the_holder_can_upload_artifacts(client, alice, project, storage):
    _user, headers = alice
    session_id = await new_session(client, headers, project.id)
    await client.put(f"{SN}/sessions/{session_id}/lock", headers=headers)

    res = await upload(client, headers, session_id)

    assert res.status_code == 201, res.text


async def test_a_takeover_during_the_upload_stops_the_pointers_from_landing(
    client, db_session, alice, bob, project, storage, monkeypatch
):
    """The preflight check goes stale while the bytes are in flight.

    Three uploads are three network round trips, and a lease can lapse and be taken
    across them — after which the old caller would still publish its pointers onto the
    session the new holder is now editing. The objects it already sent are orphans
    nothing references, which is what content-addressed keys are for; the pointers are
    what must not move.
    """
    _alice_user, alice_headers = alice
    bob_user, bob_headers = bob
    session_id = await new_session(client, alice_headers, project.id)

    sent = storage.upload

    async def bob_takes_it_over_mid_flight(*args, **kwargs):
        await hand_lease_to(db_session, session_id, bob_user.id)
        return await sent(*args, **kwargs)

    monkeypatch.setattr(gcs_utils, "upload_gcs_object", bob_takes_it_over_mid_flight)

    res = await upload(client, alice_headers, session_id)

    assert res.status_code == 409, res.text
    assert res.json()["code"] == "SESSION_LOCKED"
    manifest = await client.get(
        f"{SN}/sessions/{session_id}/artifacts/manifest",
        headers=bob_headers,
        follow_redirects=False,
    )
    assert manifest.status_code == 404, "the refused caller's pointers landed anyway"
