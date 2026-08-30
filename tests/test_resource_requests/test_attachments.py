"""The budget attachment: private bucket, signed URL, ten types proven by signature.

The fixtures at the top build *real* minimal files — a ZIP that is an OOXML or ODF
container, an OLE2 stream with the marker at byte 512, UTF-8 text — because the whole
point of BE-14's validation is that the bytes are read, not the filename. A test that
faked the sniffing would be testing the mock.

Storage is faked at the ``gcs_utils`` seam the services call through, the same seam
``test_sound_necklace/test_artifacts.py`` fakes: what the fake records is which bucket
and key every byte landed under, which is what the private-bucket assertions read.
"""

from __future__ import annotations

import hashlib
import io
import zipfile

import pytest
from sqlalchemy import select

from app.db.models.resource_request import RRAttachment
from app.services.oral_collector import gcs_utils
from app.services.resource_request._attachment_rules import MAX_ATTACHMENT_BYTES
from app.services.resource_request._attachment_storage import GCS_RR_BUCKET
from app.utils import resource_request_vocabularies as v
from tests.baker import make_user
from tests.test_resource_requests.conftest import auth_header, grant
from tests.test_resource_requests.test_requests import as_mesa, as_team, create

REQUESTS = "/api/resource-requests/requests"


def attachment_url(request_id: str) -> str:
    return f"{REQUESTS}/{request_id}/attachment"


# ——— ten minimal real files ——————————————————————————————————————————————————————


def zip_with(entries: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def odf_file(mime: str) -> bytes:
    return zip_with({"mimetype": mime.encode(), "content.xml": b"<office:document/>"})


def ooxml_file(marker: str) -> bytes:
    content_types = (
        f'<?xml version="1.0"?><Types><Override ContentType='
        f'"application/vnd.openxmlformats-officedocument.{marker}.main+xml"/></Types>'
    ).encode("ascii")
    return zip_with({"[Content_Types].xml": content_types, "_rels/.rels": b"<Relationships/>"})


def ole2_file(marker_at_512: bytes) -> bytes:
    """The OLE2 magic, zero-padding, and the stream marker the 512th byte carries."""
    header = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
    return header + b"\x00" * (512 - len(header)) + marker_at_512 + b"\x00" * 16


PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"
RTF = b"{\\rtf1\\ansi Orcamento}"
CSV = b"categoria,valor\npapel,12.50\n"
CSV_CP1252 = "categoria,orçamento\npapel,12.50\n".encode("cp1252")
TXT = "orçamento em texto simples\n".encode()
XLSX = ooxml_file("spreadsheetml")
DOCX = ooxml_file("wordprocessingml")
ODS = odf_file("application/vnd.oasis.opendocument.spreadsheet")
ODT = odf_file("application/vnd.oasis.opendocument.text")
XLS = ole2_file(b"\x09\x08\x10\x00\x00\x06\x05\x00")
DOC = ole2_file(b"\xec\xa5\xc1\x00")

THE_TEN: dict[str, bytes] = {
    "application/pdf": PDF,
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": XLSX,
    "application/vnd.ms-excel": XLS,
    "application/vnd.oasis.opendocument.spreadsheet": ODS,
    "text/csv": CSV,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": DOCX,
    "application/msword": DOC,
    "application/vnd.oasis.opendocument.text": ODT,
    "application/rtf": RTF,
    "text/plain": TXT,
}


# ——— the storage fake ————————————————————————————————————————————————————————————


class FakeStore:
    """Records every object and every signature request; deletes nothing, has no delete."""

    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], tuple[bytes, str]] = {}
        self.signed: list[tuple[str, str, int]] = []

    async def upload(
        self, bucket: str, key: str, data: bytes, content_type: str, **_: object
    ) -> str:
        self.objects[(bucket, key)] = (data, content_type)
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
        return f"https://storage.example/signed/{key}?x-goog-expires={expiry_minutes * 60}"


@pytest.fixture()
def storage(monkeypatch) -> FakeStore:
    fake = FakeStore()
    monkeypatch.setattr(gcs_utils, "upload_gcs_object", fake.upload)
    monkeypatch.setattr(gcs_utils, "generate_signed_download_url", fake.sign)
    return fake


async def put_file(
    client, request_id: str, headers: dict[str, str], data: bytes, content_type: str, **params
):
    return await client.put(
        attachment_url(request_id),
        content=data,
        headers={**headers, "Content-Type": content_type},
        params=params,
    )


# ——— the private bucket and the content-addressed key ————————————————————————————


async def test_upload_lands_in_the_private_bucket_under_a_content_addressed_key(
    db_session, client, rrf_app, storage
) -> None:
    """The bytes go to the dedicated private bucket, keyed by their own sha256 — and the
    answer is a receipt, not a URL: no public link exists on any path here."""
    headers = await as_team(db_session, rrf_app)
    created = await create(client, headers)

    res = await put_file(client, created["id"], headers, PDF, "application/pdf", filename="a.pdf")
    assert res.status_code == 201, res.text
    body = res.json()

    sha256 = hashlib.sha256(PDF).hexdigest()
    assert body["sha256"] == sha256
    assert body["size_bytes"] == len(PDF)
    assert body["filename"] == "a.pdf"
    assert "storage.googleapis.com" not in res.text
    assert "url" not in body

    ((bucket, key),) = storage.objects
    assert bucket == GCS_RR_BUCKET
    assert created["id"] in key
    assert sha256 in key
    assert key.endswith("orcamento.pdf")
    assert storage.objects[(bucket, key)] == (PDF, "application/pdf")


@pytest.mark.parametrize(("content_type", "data"), THE_TEN.items(), ids=list(THE_TEN))
async def test_each_of_the_ten_types_is_accepted(
    db_session, client, rrf_app, storage, content_type: str, data: bytes
) -> None:
    headers = await as_team(db_session, rrf_app)
    created = await create(client, headers)

    res = await put_file(client, created["id"], headers, data, content_type)
    assert res.status_code == 201, res.text
    assert res.json()["content_type"] == content_type


# ——— refusal: type and signature must both hold ——————————————————————————————————


async def test_a_type_outside_the_ten_is_refused(db_session, client, rrf_app, storage) -> None:
    headers = await as_team(db_session, rrf_app)
    created = await create(client, headers)

    res = await put_file(client, created["id"], headers, b"\x89PNG\r\n", "image/png")
    assert res.status_code == 400
    assert storage.objects == {}


async def test_a_declared_type_the_bytes_contradict_is_refused(
    db_session, client, rrf_app, storage
) -> None:
    """Renaming decides nothing: the declared type is checked against the signature, and
    a ZIP wearing ``application/pdf`` is refused before a byte reaches storage."""
    headers = await as_team(db_session, rrf_app)
    created = await create(client, headers)

    res = await put_file(
        client, created["id"], headers, XLSX, "application/pdf", filename="orcamento.pdf"
    )
    assert res.status_code == 400
    assert storage.objects == {}


@pytest.mark.parametrize(
    ("declared", "data"),
    [
        ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", DOCX),
        ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", XLSX),
        ("application/vnd.oasis.opendocument.spreadsheet", ODT),
        ("application/vnd.oasis.opendocument.text", ODS),
    ],
    ids=["docx-as-xlsx", "xlsx-as-docx", "odt-as-ods", "ods-as-odt"],
)
async def test_zip_containers_are_told_apart_from_the_inside(
    db_session, client, rrf_app, storage, declared: str, data: bytes
) -> None:
    """All four share the outer ``PK\\x03\\x04``; what refuses the swap is the archive's
    own statement — ODF's ``mimetype`` member, OOXML's ``[Content_Types].xml``."""
    headers = await as_team(db_session, rrf_app)
    created = await create(client, headers)

    res = await put_file(client, created["id"], headers, data, declared)
    assert res.status_code == 400
    assert storage.objects == {}


@pytest.mark.parametrize(
    ("declared", "data"),
    [
        ("text/plain", b"texto\x00binario"),
        ("text/csv", b"a,b\n\x81\x8d nem utf-8 nem cp1252"),
    ],
    ids=["control-byte", "undecodable"],
)
async def test_the_two_signatureless_types_are_proven_as_text(
    db_session, client, rrf_app, storage, declared: str, data: bytes
) -> None:
    """.csv and .txt have no magic number; the proof is text with no control bytes
    outside tab, CR and LF, decodable as UTF-8 or cp1252 — a binary renamed to .txt fails
    exactly that. ``\\x81`` and ``\\x8d`` are undefined in both codecs, which is what keeps
    the decode arm reachable after the cp1252 fallback."""
    headers = await as_team(db_session, rrf_app)
    created = await create(client, headers)

    res = await put_file(client, created["id"], headers, data, declared)
    assert res.status_code == 400
    assert storage.objects == {}


async def test_a_cp1252_spreadsheet_export_is_accepted(
    db_session, client, rrf_app, storage
) -> None:
    """Excel on a pt-BR Windows writes .csv as cp1252, and a header cell reading
    ``orçamento`` is one byte away from failing a strict UTF-8 decode — a 400 on one of
    the formats the client named as *planilha*. The control-byte proof is untouched."""
    headers = await as_team(db_session, rrf_app)
    created = await create(client, headers)

    res = await put_file(client, created["id"], headers, CSV_CP1252, "text/csv")
    assert res.status_code == 201, res.text
    assert storage.objects[next(iter(storage.objects))][0] == CSV_CP1252


# ——— the 10 MB ceiling, refused before storage is touched ————————————————————————


async def test_over_the_ceiling_answers_413_and_storage_is_never_touched(
    db_session, client, rrf_app, storage
) -> None:
    headers = await as_team(db_session, rrf_app)
    created = await create(client, headers)

    res = await put_file(
        client, created["id"], headers, b"x" * (MAX_ATTACHMENT_BYTES + 1), "application/pdf"
    )
    assert res.status_code == 413
    assert storage.objects == {}


async def test_a_chunked_body_with_no_content_length_is_still_capped(
    db_session, client, rrf_app, storage
) -> None:
    """A sender that omits Content-Length does not skip the ceiling: the counted read
    refuses the stream the moment it passes the limit."""
    headers = await as_team(db_session, rrf_app)
    created = await create(client, headers)

    async def oversized():
        for _ in range(11):
            yield b"x" * (1024 * 1024)

    res = await client.put(
        attachment_url(created["id"]),
        content=oversized(),
        headers={**headers, "Content-Type": "application/pdf"},
    )
    assert res.status_code == 413
    assert storage.objects == {}


# ——— one file per request, replaceable, history kept —————————————————————————————


async def test_replacement_supersedes_the_previous_row_and_deletes_nothing(
    db_session, client, rrf_app, storage
) -> None:
    """The second upload becomes the current file; the first survives as a superseded
    row still naming its object — history, never DELETE."""
    headers = await as_team(db_session, rrf_app)
    created = await create(client, headers)

    first = await put_file(client, created["id"], headers, PDF, "application/pdf")
    second = await put_file(client, created["id"], headers, CSV, "text/csv")
    assert first.status_code == 201 and second.status_code == 201

    read = await client.get(attachment_url(created["id"]), headers=headers)
    assert read.status_code == 200
    assert read.json()["id"] == second.json()["id"]
    assert read.json()["content_type"] == "text/csv"

    rows = (
        (
            await db_session.execute(
                select(RRAttachment).where(RRAttachment.request_id == created["id"])
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 2
    by_id = {row.id: row for row in rows}
    assert by_id[first.json()["id"]].superseded_at is not None
    assert by_id[second.json()["id"]].superseded_at is None
    assert len(storage.objects) == 2


# ——— the signed download, scoped like the request ————————————————————————————————


async def test_download_is_a_short_lived_signed_url_from_the_private_bucket(
    db_session, client, rrf_app, storage
) -> None:
    headers = await as_team(db_session, rrf_app)
    created = await create(client, headers)
    await put_file(client, created["id"], headers, PDF, "application/pdf")

    res = await client.get(attachment_url(created["id"]), headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()

    ((bucket, key, expiry),) = storage.signed
    assert bucket == GCS_RR_BUCKET
    assert key in body["download_url"]
    assert body["download_url"].startswith("https://storage.example/signed/")
    assert body["expires_in_minutes"] == expiry == 15
    assert "storage.googleapis.com" not in res.text


async def test_the_attachment_is_scoped_exactly_like_its_request(
    db_session, client, rrf_app, storage
) -> None:
    """Another team answers 404 on both verbs — not 403, for ``get_request``'s reason —
    while the mesa, which reaches every request, reaches the file too."""
    author = await as_team(db_session, rrf_app)
    created = await create(client, author)
    await put_file(client, created["id"], author, PDF, "application/pdf")

    stranger = await make_user(db_session, email="outra@rr.test")
    await grant(db_session, stranger, rrf_app, "equipe")
    other_team = await auth_header(db_session, stranger)

    assert (await client.get(attachment_url(created["id"]), headers=other_team)).status_code == 404
    replaced = await put_file(client, created["id"], other_team, CSV, "text/csv")
    assert replaced.status_code == 404

    mesa = await as_mesa(db_session, rrf_app)
    assert (await client.get(attachment_url(created["id"]), headers=mesa)).status_code == 200


async def test_a_request_with_no_attachment_answers_404(
    db_session, client, rrf_app, storage
) -> None:
    headers = await as_team(db_session, rrf_app)
    created = await create(client, headers)

    res = await client.get(attachment_url(created["id"]), headers=headers)
    assert res.status_code == 404


async def test_a_submitted_request_refuses_a_new_file(db_session, client, rrf_app, storage) -> None:
    """The same 409 an edit gets: the mesa evaluates a frozen snapshot, and the file may
    not move under it either — the way back in is a revision."""
    headers = await as_team(db_session, rrf_app)
    created = await create(client, headers)
    submitted = await client.post(f"{REQUESTS}/{created['id']}/submit", headers=headers)
    assert submitted.status_code == 200, submitted.text

    res = await put_file(client, created["id"], headers, PDF, "application/pdf")
    assert res.status_code == 409


# ——— the note beside the file ————————————————————————————————————————————————————


def test_attachment_note_survives_among_the_45_text_keys() -> None:
    """The file is additive to the note, never a replacement: ``attachment_note`` stays
    one of the contract's 45 keys — a team that cannot upload still says what it sent —
    and the 45 do not move."""
    assert "attachment_note" in v.TEXT_FIELD_KEYS
    assert len(v.TEXT_FIELD_KEYS) == 45
