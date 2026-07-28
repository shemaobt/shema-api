"""The project audio bucket: which audios a facilitator may list, and how the bytes are reached.

The audios are acousteme-bearing pilot recordings that carry no project of their own
(``oc_acousteme_artifacts`` is standalone by design), so ``sn_audio_refs`` is the only
thing binding one to a project — and therefore the only thing a project gate can stand
on. Bytes are never proxied: the route mints a short-lived signed GET, and the one thing
faked here is Google's signer, so that what we hand it stays assertable.

The invariant these tests exist to hold: **every audio the bucket lists is one the URL
route can serve.** The bytes' only recorded location is a column on the acousteme row,
so an audio with no artifact has no bytes anywhere — listing it would put a bead in the
bucket that 404s the moment the facilitator presses play.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.db.models.oc_acousteme import OC_AcoustemeArtifact
from app.db.models.sound_necklace import SnAudioRef
from app.services.oral_collector import acousteme_service
from tests.baker import make_language, make_project, make_project_user_access, make_user
from tests.test_sound_necklace.conftest import auth_header, grant_role

SN = "/api/sound-necklace"

CODEBOOK = "terena-xlsr53-k100-v1"


async def bind_audio(db_session, project_id: str, audio_id: str, *, consent: bool = False) -> None:
    """Bind an audio to a project — the row that makes the listing project-scoped."""
    db_session.add(SnAudioRef(audio_id=audio_id, project_id=project_id, consent_present=consent))
    await db_session.commit()


async def make_acousteme(
    db_session,
    audio_id: str,
    *,
    codebook_version: str = CODEBOOK,
    status: str = "ready",
    title: str | None = "A História de Rute",
    duration_sec: float | None = 61.5,
    hop_sec: float | None = 0.02,
    audio_bucket: str | None = "terena-pilot",
    audio_object: str | None = "ruth/a-historia-de-rute.mp3",
    created_at: datetime | None = None,
) -> None:
    """An acousteme artifact as the ingestion pipeline writes it.

    ``gcs_bucket`` (where the acousteme *stream* lives) is deliberately NOT the same as
    ``audio_bucket`` (where the *audio* lives), even though the pilot importer happens to
    use one bucket for both. If they matched here, a regression that signed the stream's
    bucket instead of the audio's would sail through every assertion below.
    """
    db_session.add(
        OC_AcoustemeArtifact(
            audio_id=audio_id,
            codebook_version=codebook_version,
            collection="terena-ruth",
            title=title,
            status=status,
            gcs_bucket="acousteme-streams",
            gcs_object=f"acoustemes/{audio_id}/{codebook_version}.json.gz",
            audio_bucket=audio_bucket,
            audio_object=audio_object,
            duration_sec=duration_sec,
            hop_sec=hop_sec,
            created_at=created_at or datetime(2026, 7, 1, tzinfo=UTC),
        )
    )
    await db_session.commit()


@pytest.fixture()
async def facilitator(db_session, sound_necklace_app):
    """A sound-necklace facilitator with access to one project."""
    user = await make_user(db_session, email="facilitator@example.com")
    await grant_role(db_session, sound_necklace_app.id, user.id, "facilitator")
    language = await make_language(db_session, name="Terena", code="ter")
    project = await make_project(db_session, language.id, name="Projeto A")
    await make_project_user_access(db_session, project.id, user.id)
    headers = await auth_header(db_session, user)
    return user, project, headers


@pytest.fixture()
async def other_project(db_session):
    """A project the facilitator cannot reach."""
    language = await make_language(db_session, name="Nheengatu", code="yrl")
    return await make_project(db_session, language.id, name="Projeto B")


@pytest.fixture()
def signer_calls(monkeypatch):
    """Stand in for Google's signer, recording what we asked it to sign."""
    calls: list[dict] = []

    async def _sign(
        bucket_name: str,
        blob_name: str,
        *,
        expiry_minutes: int = 15,
        response_content_type: str | None = None,
    ) -> str:
        calls.append({"bucket": bucket_name, "blob": blob_name, "expiry_minutes": expiry_minutes})
        return f"https://storage.googleapis.com/{bucket_name}/{blob_name}?X-Goog-Signature=deadbeef"

    monkeypatch.setattr(acousteme_service, "generate_signed_download_url", _sign)
    return calls


# ── The invariant: listed means playable ─────────────────────────────────────


async def test_every_audio_the_bucket_lists_can_actually_be_played(
    client, facilitator, db_session, signer_calls
):
    """The facilitator's whole path: read the bucket, pick a story, press play.

    Nothing in the bucket may 404 on click. This walks it end to end across every kind
    of audio the pilot can produce — with a grid, without one, and mid-ingest.
    """
    _user, project, headers = facilitator
    await bind_audio(db_session, project.id, "ruth-com-grade")
    await make_acousteme(db_session, "ruth-com-grade", audio_object="ruth/com-grade.mp3")
    await bind_audio(db_session, project.id, "ruth-sem-grade")
    await make_acousteme(
        db_session, "ruth-sem-grade", hop_sec=None, audio_object="ruth/sem-grade.mp3"
    )
    await bind_audio(db_session, project.id, "ruth-em-ingestao")
    await make_acousteme(
        db_session, "ruth-em-ingestao", status="pending", audio_object="ruth/em-ingestao.mp3"
    )

    listing = await client.get(f"{SN}/projects/{project.id}/audios", headers=headers)
    assert listing.status_code == 200, listing.text
    audios = listing.json()["audios"]
    assert len(audios) == 3

    for audio in audios:
        played = await client.get(f"{SN}/audios/{audio['id']}/url", headers=headers)
        assert played.status_code == 200, f"{audio['id']} listed but will not play: {played.text}"


async def test_an_audio_with_no_acousteme_is_not_in_the_bucket_at_all(
    client, facilitator, db_session, signer_calls
):
    """No artifact means no recorded byte location — anywhere in the system.

    This is not the §6.1 "no grid, use fixed durations" fallback (that one still has an
    audio to play). It is a phantom, and the bucket must not offer it.
    """
    _user, project, headers = facilitator
    await bind_audio(db_session, project.id, "ruth-fantasma")

    listing = await client.get(f"{SN}/projects/{project.id}/audios", headers=headers)

    assert listing.status_code == 200, listing.text
    assert listing.json() == {"audios": []}


async def test_an_audio_whose_source_was_never_recorded_is_not_in_the_bucket(
    client, facilitator, db_session
):
    """READY does not imply servable: store_artifact defaults audio_bucket to None and
    assigns it unconditionally, so a re-ingest that omits it nulls out a live pointer."""
    _user, project, headers = facilitator
    await bind_audio(db_session, project.id, "ruth-sem-fonte")
    await make_acousteme(db_session, "ruth-sem-fonte", audio_bucket=None, audio_object=None)

    listing = await client.get(f"{SN}/projects/{project.id}/audios", headers=headers)

    assert listing.status_code == 200, listing.text
    assert listing.json() == {"audios": []}


# ── The project gate ─────────────────────────────────────────────────────────


async def test_the_listing_carries_only_the_projects_own_audios(
    client, facilitator, other_project, db_session
):
    _user, project, headers = facilitator
    await bind_audio(db_session, project.id, "ruth-a-historia-de-rute")
    await make_acousteme(db_session, "ruth-a-historia-de-rute")
    await bind_audio(db_session, other_project.id, "ruth-o-conto-do-boto")
    await make_acousteme(db_session, "ruth-o-conto-do-boto")

    res = await client.get(f"{SN}/projects/{project.id}/audios", headers=headers)

    assert res.status_code == 200, res.text
    assert [a["id"] for a in res.json()["audios"]] == ["ruth-a-historia-de-rute"]


async def test_the_listing_is_denied_to_someone_outside_the_project(
    client, facilitator, other_project
):
    _user, _project, headers = facilitator

    res = await client.get(f"{SN}/projects/{other_project.id}/audios", headers=headers)

    assert res.status_code == 403


async def test_a_project_with_no_audios_lists_nothing_rather_than_failing(client, facilitator):
    _user, project, headers = facilitator

    res = await client.get(f"{SN}/projects/{project.id}/audios", headers=headers)

    assert res.status_code == 200, res.text
    assert res.json() == {"audios": []}


async def test_the_bucket_is_ordered_the_same_way_every_time(client, facilitator, db_session):
    """The facilitator picks by position as much as by name. A bucket that reshuffles
    between two reads is a bucket they cannot trust."""
    _user, project, headers = facilitator
    for audio_id in ("ruth-zulmira", "ruth-abigail", "ruth-marta"):
        await bind_audio(db_session, project.id, audio_id)
        await make_acousteme(db_session, audio_id, audio_object=f"ruth/{audio_id}.mp3")

    first = await client.get(f"{SN}/projects/{project.id}/audios", headers=headers)
    second = await client.get(f"{SN}/projects/{project.id}/audios", headers=headers)

    assert [a["id"] for a in first.json()["audios"]] == [
        "ruth-abigail",
        "ruth-marta",
        "ruth-zulmira",
    ]
    assert first.json() == second.json()


# ── The acousteme envelope ───────────────────────────────────────────────────


async def test_an_audio_carries_the_envelope_its_granularity_is_derived_from(
    client, facilitator, db_session
):
    """beadSec = granularity_frames[level] x hop_sec — the envelope must carry both."""
    _user, project, headers = facilitator
    await bind_audio(db_session, project.id, "ruth-a-historia-de-rute")
    await make_acousteme(db_session, "ruth-a-historia-de-rute")

    res = await client.get(f"{SN}/projects/{project.id}/audios", headers=headers)

    assert res.status_code == 200, res.text
    (audio,) = res.json()["audios"]
    assert audio["filename"] == "A História de Rute"
    assert audio["duration_sec"] == 61.5
    assert audio["acousteme"] == {
        "codebook_version": CODEBOOK,
        "hop_sec": 0.02,
        "granularity_frames": {"small": 10, "medium": 25, "large": 50},
    }


async def test_an_unservable_acousteme_does_not_become_an_envelope(client, facilitator, db_session):
    """A pending ingest has no stream behind it. Advertising its grid would promise a
    granularity the audio cannot yet deliver — but the audio itself still plays."""
    _user, project, headers = facilitator
    await bind_audio(db_session, project.id, "ruth-em-ingestao")
    await make_acousteme(db_session, "ruth-em-ingestao", status="pending")

    res = await client.get(f"{SN}/projects/{project.id}/audios", headers=headers)

    assert res.status_code == 200, res.text
    (audio,) = res.json()["audios"]
    assert audio["acousteme"] is None


async def test_a_grid_with_no_hop_is_no_grid(client, facilitator, db_session):
    """hop_sec is nullable in the database and not in the DTO. Letting a null through
    would fail response validation and take the whole listing down with it — so the
    audio lists with no envelope, and falls back to fixed durations."""
    _user, project, headers = facilitator
    await bind_audio(db_session, project.id, "ruth-sem-hop")
    await make_acousteme(db_session, "ruth-sem-hop", hop_sec=None)

    res = await client.get(f"{SN}/projects/{project.id}/audios", headers=headers)

    assert res.status_code == 200, res.text
    (audio,) = res.json()["audios"]
    assert audio["acousteme"] is None
    assert audio["duration_sec"] == 61.5


async def test_an_untitled_audio_falls_back_to_its_own_id_for_a_name(
    client, facilitator, db_session
):
    _user, project, headers = facilitator
    await bind_audio(db_session, project.id, "ruth-sem-titulo")
    await make_acousteme(db_session, "ruth-sem-titulo", title=None)

    res = await client.get(f"{SN}/projects/{project.id}/audios", headers=headers)

    assert res.status_code == 200, res.text
    (audio,) = res.json()["audios"]
    assert audio["filename"] == "ruth-sem-titulo"


async def test_a_failed_newer_ingest_does_not_shadow_a_servable_version(
    client, facilitator, db_session
):
    """The newest row is not the answer — the newest SERVABLE one is."""
    _user, project, headers = facilitator
    await bind_audio(db_session, project.id, "ruth-a-historia-de-rute")
    await make_acousteme(
        db_session,
        "ruth-a-historia-de-rute",
        codebook_version="terena-v1",
        status="ready",
        created_at=datetime(2026, 7, 1, tzinfo=UTC),
    )
    await make_acousteme(
        db_session,
        "ruth-a-historia-de-rute",
        codebook_version="terena-v2",
        status="failed",
        created_at=datetime(2026, 7, 10, tzinfo=UTC),
    )

    res = await client.get(f"{SN}/projects/{project.id}/audios", headers=headers)

    assert res.status_code == 200, res.text
    (audio,) = res.json()["audios"]
    assert audio["acousteme"]["codebook_version"] == "terena-v1"


async def test_the_newest_servable_version_wins(client, facilitator, db_session):
    _user, project, headers = facilitator
    await bind_audio(db_session, project.id, "ruth-a-historia-de-rute")
    await make_acousteme(
        db_session,
        "ruth-a-historia-de-rute",
        codebook_version="terena-v1",
        created_at=datetime(2026, 7, 1, tzinfo=UTC),
    )
    await make_acousteme(
        db_session,
        "ruth-a-historia-de-rute",
        codebook_version="terena-v2",
        created_at=datetime(2026, 7, 10, tzinfo=UTC),
    )

    res = await client.get(f"{SN}/projects/{project.id}/audios", headers=headers)

    assert res.status_code == 200, res.text
    (audio,) = res.json()["audios"]
    assert audio["acousteme"]["codebook_version"] == "terena-v2"


async def test_co_ingested_versions_list_and_play_the_same_one(
    client, facilitator, db_session, signer_calls
):
    """``created_at`` is a transaction timestamp, so a batch re-clustering ties. The
    listing and the URL route resolve through different queries, so the tiebreak has to
    live where both read it — otherwise the bucket advertises one codebook's envelope
    while the signer hands over the other codebook's bytes, and unit ids do not survive
    a codebook swap."""
    _user, project, headers = facilitator
    await bind_audio(db_session, project.id, "ruth-a-historia-de-rute")
    ingested_together = datetime(2026, 7, 10, tzinfo=UTC)
    await make_acousteme(
        db_session,
        "ruth-a-historia-de-rute",
        codebook_version="terena-v1",
        audio_object="ruth/v1.mp3",
        created_at=ingested_together,
    )
    await make_acousteme(
        db_session,
        "ruth-a-historia-de-rute",
        codebook_version="terena-v2",
        audio_object="ruth/v2.mp3",
        created_at=ingested_together,
    )

    listing = await client.get(f"{SN}/projects/{project.id}/audios", headers=headers)
    assert listing.status_code == 200, listing.text
    (audio,) = listing.json()["audios"]
    assert audio["acousteme"]["codebook_version"] == "terena-v2"

    url = await client.get(f"{SN}/audios/ruth-a-historia-de-rute/url", headers=headers)
    assert url.status_code == 200, url.text
    assert signer_calls == [
        {"bucket": "terena-pilot", "blob": "ruth/v2.mp3", "expiry_minutes": 15}
    ], "the listing advertised terena-v2 but the signer was pointed at another version"


# ── Collection consent (§12 / O6) ────────────────────────────────────────────


async def test_collection_consent_surfaces_as_recorded(client, facilitator, db_session):
    _user, project, headers = facilitator
    await bind_audio(db_session, project.id, "ruth-com-consentimento", consent=True)
    await make_acousteme(db_session, "ruth-com-consentimento")

    res = await client.get(f"{SN}/projects/{project.id}/audios", headers=headers)

    assert res.status_code == 200, res.text
    (audio,) = res.json()["audios"]
    assert audio["consent_present"] is True


async def test_consent_is_absent_rather_than_assumed_when_it_was_never_recorded(
    client, facilitator, db_session
):
    """Never claim a consent we do not hold."""
    _user, project, headers = facilitator
    await bind_audio(db_session, project.id, "ruth-sem-consentimento")
    await make_acousteme(db_session, "ruth-sem-consentimento")

    res = await client.get(f"{SN}/projects/{project.id}/audios", headers=headers)

    assert res.status_code == 200, res.text
    (audio,) = res.json()["audios"]
    assert audio["consent_present"] is False


# ── Signed GET: the audit point (ENG-266 hooks here) ─────────────────────────


async def test_the_url_is_signed_for_the_audios_own_private_object(
    client, facilitator, db_session, signer_calls
):
    """The TTL is asserted exactly, and on purpose. It is inherited from the Oral
    Collector's constant, which is a coupling we accepted with eyes open: if that module
    ever loosens its expiry, this recording's exposure window widens with it, and this
    assertion is the tripwire that makes it a conversation instead of a silent change."""
    _user, project, headers = facilitator
    await bind_audio(db_session, project.id, "ruth-a-historia-de-rute")
    await make_acousteme(db_session, "ruth-a-historia-de-rute")

    res = await client.get(f"{SN}/audios/ruth-a-historia-de-rute/url", headers=headers)

    assert res.status_code == 200, res.text
    assert signer_calls == [
        {"bucket": "terena-pilot", "blob": "ruth/a-historia-de-rute.mp3", "expiry_minutes": 15}
    ]
    assert res.json()["url"].startswith(
        "https://storage.googleapis.com/terena-pilot/ruth/a-historia-de-rute.mp3"
    )


async def test_the_url_is_denied_for_an_audio_outside_the_callers_projects(
    client, facilitator, other_project, db_session, signer_calls
):
    _user, _project, headers = facilitator
    await bind_audio(db_session, other_project.id, "ruth-alheia")
    await make_acousteme(db_session, "ruth-alheia")

    res = await client.get(f"{SN}/audios/ruth-alheia/url", headers=headers)

    assert res.status_code == 403
    assert signer_calls == [], "a URL was minted before the gate rejected the caller"


async def test_an_audio_no_project_claims_is_not_reachable(
    client, facilitator, db_session, signer_calls
):
    """An acousteme with no sn_audio_refs row belongs to no project, so it has no gate
    to pass — it is unreachable through this API, not world-readable through it."""
    _user, _project, headers = facilitator
    await make_acousteme(db_session, "ruth-orfa")

    res = await client.get(f"{SN}/audios/ruth-orfa/url", headers=headers)

    assert res.status_code == 404
    assert signer_calls == []


async def test_an_unknown_audio_is_a_miss_not_a_crash(client, facilitator, signer_calls):
    _user, _project, headers = facilitator

    res = await client.get(f"{SN}/audios/nao-existe/url", headers=headers)

    assert res.status_code == 404
    assert signer_calls == []


async def test_a_platform_admin_reaches_the_bytes_without_a_project_grant(
    client, db_session, sound_necklace_app, other_project, signer_calls
):
    """The platform-admin bypass is real and it reaches the audit point. Pinning it here
    rather than leaving it implicit: this is a signed URL for a recorded voice in a
    project the caller was never granted."""
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    await grant_role(db_session, sound_necklace_app.id, admin.id, "facilitator")
    headers = await auth_header(db_session, admin)
    await bind_audio(db_session, other_project.id, "ruth-alheia")
    await make_acousteme(db_session, "ruth-alheia")

    res = await client.get(f"{SN}/audios/ruth-alheia/url", headers=headers)

    assert res.status_code == 200, res.text
    assert signer_calls[0]["bucket"] == "terena-pilot"
