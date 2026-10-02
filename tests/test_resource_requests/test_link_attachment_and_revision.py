"""The attachment and the revision by the Admin's link — FE-55 (OBT-542).

BE-26 (OBT-537) closed with the link writing its draft, submitting it and reading its status, and
two doors still user-only: the budget file (item 10 of Part B) and the revision after *revisar*.
Both are the link's now, under the same rules a person's are — the link that started the request
holds the pen, another link does not reach it, and the record names the link as author, never
the Admin who issued it.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.rate_limit import limiter
from app.db.models.resource_request import RRAttachment, RRDecision, RRRequest, RRStage
from app.services.oral_collector import gcs_utils
from tests.test_resource_requests.test_attachments import (
    PDF,
    FakeStore,
    attachment_url,
    put_file,
)
from tests.test_resource_requests.test_link_requests import holder
from tests.test_resource_requests.test_requests import (
    REQUESTS,
    _decide,
    _gestor,
    _to_column,
    as_mesa,
    draft,
)


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture()
def files(monkeypatch) -> FakeStore:
    """The storage seam ``test_attachments.py`` fakes, faked here the same way."""
    fake = FakeStore()
    monkeypatch.setattr(gcs_utils, "upload_gcs_object", fake.upload)
    monkeypatch.setattr(gcs_utils, "generate_signed_download_url", fake.sign)
    return fake


async def started_by(client, headers: dict[str, str]) -> str:
    return (await client.post(REQUESTS, json=draft(), headers=headers)).json()["id"]


# ——— the attachment ——————————————————————————————————————————————————————————————


@pytest.mark.usefixtures("files")
async def test_a_link_attaches_and_replaces_the_file_of_its_own_request(
    db_session, client, rrf_app
) -> None:
    admin, link, headers = await holder(db_session, client)
    own = await started_by(client, headers)

    first = await put_file(client, own, headers, PDF, "application/pdf", filename="a.pdf")
    second = await put_file(client, own, headers, PDF + b"%", "application/pdf", filename="b.pdf")
    read = await client.get(attachment_url(own), headers=headers)

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert read.status_code == 200, read.text
    assert read.json()["filename"] == "b.pdf"
    rows = (
        (await db_session.execute(select(RRAttachment).where(RRAttachment.request_id == own)))
        .scalars()
        .all()
    )
    assert len(rows) == 2
    assert {row.uploaded_by_link_id for row in rows} == {link["id"]}
    assert {row.uploaded_by for row in rows} == {None}, "never the Admin who issued the link"
    assert admin.id not in {row.uploaded_by for row in rows}
    assert second.json()["uploaded_by_link_id"] == link["id"]
    assert second.json()["uploaded_by"] is None


@pytest.mark.usefixtures("files")
async def test_another_link_reaches_neither_the_file_nor_the_upload(
    db_session, client, rrf_app
) -> None:
    _a, _la, owner = await holder(db_session, client, "dona@fora.org")
    _b, _lb, other = await holder(db_session, client, "outra@fora.org")
    own = await started_by(client, owner)
    await put_file(client, own, owner, PDF, "application/pdf")

    upload = await put_file(client, own, other, PDF, "application/pdf")
    read = await client.get(attachment_url(own), headers=other)

    assert upload.status_code == 404, upload.text
    assert read.status_code == 404, read.text


@pytest.mark.usefixtures("files")
async def test_a_submitted_request_takes_no_new_file_from_its_link(
    db_session, client, rrf_app
) -> None:
    _admin, _link, headers = await holder(db_session, client)
    own = await started_by(client, headers)
    await client.post(f"{REQUESTS}/{own}/submit", headers=headers)

    res = await put_file(client, own, headers, PDF, "application/pdf")

    assert res.status_code == 409, res.text


@pytest.mark.usefixtures("files")
async def test_a_person_still_uploads_under_their_own_name(db_session, client, rrf_app) -> None:
    """The pair holds exactly one author: the account's upload keeps ``uploaded_by``."""
    from tests.test_resource_requests.test_requests import as_team, create

    headers = await as_team(db_session, rrf_app)
    own = (await create(client, headers))["id"]

    res = await put_file(client, own, headers, PDF, "application/pdf")

    assert res.status_code == 201, res.text
    assert res.json()["uploaded_by"] is not None
    assert res.json()["uploaded_by_link_id"] is None


# ——— the revision ————————————————————————————————————————————————————————————————


async def test_a_link_reopens_its_request_after_revisar(db_session, client, rrf_app) -> None:
    _admin, link, headers = await holder(db_session, client)
    own = await started_by(client, headers)
    await client.post(f"{REQUESTS}/{own}/submit", headers=headers)
    await _decide(db_session, own, RRDecision.REVISE)

    res = await client.post(f"{REQUESTS}/{own}/revise", headers=headers)

    assert res.status_code == 201, res.text
    assert res.json()["can_edit"] is True
    revision = await db_session.get(RRRequest, res.json()["id"])
    assert revision.request_link_id == link["id"]
    assert revision.started_by_link_id == link["id"]
    assert revision.shema_project_id is None
    edited = await client.patch(f"{REQUESTS}/{revision.id}", json=draft(), headers=headers)
    assert edited.status_code == 200, edited.text


async def test_only_a_revise_decision_reopens_it_for_the_link(db_session, client, rrf_app) -> None:
    _admin, _link, headers = await holder(db_session, client)
    own = await started_by(client, headers)
    await client.post(f"{REQUESTS}/{own}/submit", headers=headers)
    await _decide(db_session, own, RRDecision.CONDITIONAL)

    res = await client.post(f"{REQUESTS}/{own}/revise", headers=headers)

    assert res.status_code == 409, res.text


async def test_the_link_revision_obeys_one_open_per_link(db_session, client, rrf_app) -> None:
    _admin, _link, headers = await holder(db_session, client)
    own = await started_by(client, headers)
    await client.post(f"{REQUESTS}/{own}/submit", headers=headers)
    await _decide(db_session, own, RRDecision.REVISE)
    blocking = (
        await client.post(f"{REQUESTS}/start", json={"request_type": "traducao"}, headers=headers)
    ).json()

    refused = await client.post(f"{REQUESTS}/{own}/revise", headers=headers)
    await client.post(f"{REQUESTS}/{blocking['id']}/cancel", headers=headers)
    opened = await client.post(f"{REQUESTS}/{own}/revise", headers=headers)
    twice = await client.post(f"{REQUESTS}/{own}/revise", headers=headers)

    assert refused.status_code == 409, refused.text
    assert opened.status_code == 201, opened.text
    assert twice.status_code == 409, twice.text


async def test_another_link_does_not_reopen_it(db_session, client, rrf_app) -> None:
    _a, _la, owner = await holder(db_session, client, "dona@fora.org")
    _b, _lb, other = await holder(db_session, client, "outra@fora.org")
    own = await started_by(client, owner)
    await client.post(f"{REQUESTS}/{own}/submit", headers=owner)
    await _decide(db_session, own, RRDecision.REVISE)

    res = await client.post(f"{REQUESTS}/{own}/revise", headers=other)

    assert res.status_code == 404, res.text


async def test_the_board_reopening_a_link_request_leaves_it_the_links(
    db_session, client, rrf_app
) -> None:
    _admin, link, headers = await holder(db_session, client)
    own = await started_by(client, headers)
    await client.post(f"{REQUESTS}/{own}/submit", headers=headers)
    await _decide(db_session, own, RRDecision.REVISE)

    res = await client.post(f"{REQUESTS}/{own}/revise", headers=await as_mesa(db_session, rrf_app))

    assert res.status_code == 201, res.text
    revision = await db_session.get(RRRequest, res.json()["id"])
    assert revision.started_by_link_id == link["id"]
    edited = await client.patch(f"{REQUESTS}/{revision.id}", json=draft(), headers=headers)
    assert edited.status_code == 200, edited.text


async def test_the_board_s_own_path_takes_the_pen_from_the_link(
    db_session, client, rrf_app
) -> None:
    """On the board's *Revisar* path the Gestor writes the change, so the pen leaves the link
    (FE-47, OBT-515, PR #608 review) — after the mesa's *revisar* it stays, as above."""
    _admin, _link, headers = await holder(db_session, client)
    own = await started_by(client, headers)
    await client.post(f"{REQUESTS}/{own}/submit", headers=headers)
    await _decide(db_session, own, RRDecision.APPROVED)
    await _to_column(db_session, own, RRStage.REVISAR)
    gestor_user, gestor = await _gestor(db_session, rrf_app)

    res = await client.post(f"{REQUESTS}/{own}/revise", headers=gestor)

    assert res.status_code == 201, res.text
    revision = await db_session.get(RRRequest, res.json()["id"])
    assert revision.started_by == gestor_user.id
    assert revision.started_by_link_id is None
    edited = await client.patch(f"{REQUESTS}/{revision.id}", json=draft(), headers=headers)
    assert edited.status_code != 200, edited.text
