"""**Can I get that out by any path?** — the sensitive-country rule, tested adversarially.

Not *does the endpoint respect the rule*, which is a question an endpoint can answer while
the fact walks out of a badge, a search box, a log line or a file somebody forwards. Every
test here is an attempt to extract ``Egypt`` from a record flagged as sensitive, along a
different path, and the assertion is that the whole response body does not contain it.

**Two records, and both of them matter.** ``arabic-siwa`` is flagged; ``guarani-mbya`` is not.
A suite with only the flagged one passes for a module that withholds everything, which is not
privacy but breakage, so every path is exercised on both.

**The paths that do not exist yet are tested through the shape they will have.** BE-09's
wall, BE-14's export, BE-12's Pulse and BE-15's notification panel are later issues, and the
whole claim of ``docs/shema.md`` §6.4 is that they inherit this rule without their authors
calling anything. So each is written here as the naïve shape its author would write —
declaring the fields the contract names, inheriting the boundary and nothing else — and the
test is that the payload comes out reduced anyway. The day those issues land, these shapes
are what their models are compared against.
"""

from __future__ import annotations

import json

import pytest
from fastapi import APIRouter, FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.shema._deps import Db, Scope
from app.db.models.shema import ShemaProject
from app.db.models.shema_enums import (
    ShemaMaterialKind,
    ShemaMediaKind,
    ShemaPrayerVisibility,
    ShemaRegionKey,
)
from app.db.models.shema_media import ShemaMaterial, ShemaMediaItem
from app.models.shema_privacy import (
    REGION_CENTROIDS,
    UNKNOWN_REGION,
    LeavingShape,
    ShemaAudience,
)
from app.services.oral_collector import gcs_utils
from app.services.shema import (
    DOWNLOAD_URL_EXPIRY_MINUTES,
    GCS_SHEMA_BUCKET,
    can_export_notes,
    can_share_media,
    count_projects_by_region,
    get_project,
    is_authorized,
    is_withheld,
    list_projects,
    log_reference,
    material_download_url,
    media_download_url,
    prayer_visibility,
    reaches_prayer_wall,
    region_scope,
    searchable_text,
    shared_prayer_audio,
    shared_prayer_text,
    storage_key,
    withheld_note,
)
from app.services.shema._media_storage import MATERIALS, MEDIA
from tests.test_shema.conftest import PREFIX, auth_header, make_scoped_user

#: The country the whole file is trying to extract, and the place and the person beside it.
#: All three are the shape of the export's two flagged records (FE-44 §8.1) — a base that
#: names a place, a personal number — so a test that passes here passes against the data the
#: seed actually carries.
#:
#: **They are canaries, and nothing else in the fixtures may contain them.** Most assertions
#: below are ``secret not in <the whole body>`` rather than a field comparison, because a
#: field comparison tests the field somebody remembered and a body search tests the ones they
#: did not. That only works while the cleared record is somewhere else entirely, which is why
#: it is in Brazil and why the two sets of constants do not overlap by a substring.
COUNTRY = "Egypt"
BASE = "YWAM Egypt"
CONTACT = "+20 100 555 0000"
REQUEST_TEXT = "Pray for the team crossing the border this month."

#: The record the rule has nothing to do with. A module that withholds everything is broken,
#: not private, so every path is exercised on this one too.
OPEN_COUNTRY = "Brazil"
OPEN_BASE = "JOCUM Porto Alegre"
OPEN_CONTACT = "+55 51 99999 0000"

NAIVE_PROBE = f"{PREFIX}/_probe/naive"
NAIVE_MODELS_PROBE = f"{PREFIX}/_probe/naive-models"


class NaiveProjectOut(LeavingShape):
    """**The endpoint written by somebody who has never read** ``docs/shema.md``.

    It declares the fields the record has, inherits the base class the module's other
    response models inherit, and applies nothing. That is the whole of the DoD's third line:
    if this shape emits a protected payload, so does every shape written the same way.
    """

    id: str
    language_name: str
    location: str
    location2: str | None
    latitude: float
    longitude: float
    team: str
    team_contact: str
    team_leader_contact: str | None


class NaiveExportRow(LeavingShape):
    """BE-14's file, as FE-44 §8.4's ``ExportedProject`` allowlist names its place columns."""

    id: str
    language_name: str
    location: str
    team: str


class NaivePrayerEntry(LeavingShape):
    """BE-09's wall entry — FE-44 §5.5's ``PrayerRequest``, which keys on ``country``."""

    project_id: str
    country: str
    team: str
    text: str


class NaiveNotification(LeavingShape):
    """BE-15's panel entry — FE-44 §5.8's ``AppNotification``, same two place columns."""

    project_id: str
    country: str
    team: str


class NaiveEtenSnapshot(LeavingShape):
    """BE-11's report line — FE-44 §5.6's ``EtenYearSnapshot``, whose ``country`` is a
    ``LocationDisplay`` on the frontend precisely because it leaves coordination."""

    project_id: str
    country: str
    approved_units: int


class NaivePulseEntry(LeavingShape):
    """BE-12's artifact. GATE-03 owns the format; it does not own this, because a file built
    to be forwarded is where *transformed before serialization, not at render time* is not a
    preference (FE-44 §8.6)."""

    project_id: str
    country: str
    team: str
    text: str


async def _make_project(
    db_session,
    *,
    project_id: str,
    sensitive: bool,
    region: ShemaRegionKey = ShemaRegionKey.AFRICA,
    visibility: ShemaPrayerVisibility | None = None,
) -> ShemaProject:
    """One row with every column this file tries to extract actually filled.

    Written here rather than grown onto ``conftest.make_shema_project``, which fills the three
    columns the scope tests read and says in its own docstring why it fills no more.

    The flagged record and the cleared one are in **different countries**, which is not
    decoration: the assertions search whole response bodies for a canary, and a cleared record
    that happened to sit in the same country would make every one of them pass while the
    string it found belonged to the wrong row.
    """
    withheld = sensitive
    project = ShemaProject(
        id=project_id,
        language_name="Siwi" if withheld else "Mbyá Guaraní",
        bridge_language="Arabic" if withheld else "Portuguese",
        location=COUNTRY if withheld else OPEN_COUNTRY,
        location2="Siwa Oasis" if withheld else "Rio Grande do Sul",
        longitude=25.5 if withheld else -51.2,
        latitude=29.2 if withheld else -30.0,
        sensitive_country=sensitive,
        sensitivity="restricted access country" if sensitive else "",
        team=BASE if withheld else OPEN_BASE,
        team_contact=CONTACT if withheld else OPEN_CONTACT,
        team_leader_contact=CONTACT if withheld else OPEN_CONTACT,
        mentor_contact=CONTACT if withheld else OPEN_CONTACT,
        prayer_requests=REQUEST_TEXT,
        prayer_visibility=visibility,
        prayer_requests_audio="shema/audio/siwa.m4a",
        notes="Internal note nobody outside coordination should read.",
        region_key=region,
    )
    db_session.add(project)
    await db_session.commit()
    return project


@pytest.fixture()
async def flagged(db_session) -> ShemaProject:
    return await _make_project(db_session, project_id="arabic-siwa", sensitive=True)


@pytest.fixture()
async def cleared(db_session) -> ShemaProject:
    return await _make_project(
        db_session,
        project_id="guarani-mbya",
        sensitive=False,
        region=ShemaRegionKey.SOUTH_AMERICA,
    )


@pytest.fixture()
async def naive_client(db_session):
    """An ASGI client carrying two endpoints nobody told about the rule.

    Both are included into ``authenticated``, the router every later sub-router is included
    into, so they reach the application exactly as a real endpoint would. The pair differs
    only in what the handler hands back — an ORM row, or a model it built itself — because
    those are the two shapes a handler can return and FastAPI serialises them by different
    routes (``_prepare_response_content`` dumps the second and validates it again).

    The dependency aliases are imported at module level for the reason
    ``conftest.client`` states: with ``from __future__ import annotations`` FastAPI resolves
    every annotation against this module's globals, and a name bound inside the fixture would
    be read as a query parameter instead of a dependency.
    """
    from app.api.auth import router as auth_router
    from app.api.shema import authenticated
    from app.api.shema import router as module_router
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    probe = APIRouter()

    @probe.get("/_probe/naive", response_model=list[NaiveProjectOut])
    async def _probe_naive(scope: Scope, db: Db) -> list[ShemaProject]:
        return await list_projects(db, scope)

    @probe.get("/_probe/naive-models", response_model=list[NaiveProjectOut])
    async def _probe_naive_models(scope: Scope, db: Db) -> list[NaiveProjectOut]:
        rows = await list_projects(db, scope)
        return [NaiveProjectOut.model_validate(row) for row in rows]

    mark = len(authenticated.routes)
    try:
        authenticated.include_router(probe)
        test_app = FastAPI()
        test_app.include_router(module_router, prefix=PREFIX)
        test_app.include_router(authenticated, prefix=PREFIX)
        test_app.include_router(auth_router, prefix="/api/auth")
        register_exception_handlers(test_app)

        async def _get_db():
            yield db_session

        test_app.dependency_overrides[get_db] = _get_db
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client
    finally:
        del authenticated.routes[mark:]


# --------------------------------------------------------------------------------------
# The boundary itself
# --------------------------------------------------------------------------------------


def test_the_place_is_replaced_by_the_region_and_never_by_an_empty_string(flagged) -> None:
    """FE-44 §8.1 rule 1. An empty string is a payload that cannot say whether the data is
    missing or protected, and a consumer that has to guess guesses wrong in a file."""
    out = NaiveProjectOut.model_validate(flagged).model_dump(by_alias=True)

    assert out["location"] == ShemaRegionKey.AFRICA.value
    assert out["location"] != ""
    assert out["locationWithheld"] is True


def test_the_coordinates_become_the_region_centroid_rather_than_disappearing(flagged) -> None:
    """Reduced precision over omission, because the map must show what the filters return."""
    out = NaiveProjectOut.model_validate(flagged).model_dump()
    longitude, latitude = REGION_CENTROIDS[ShemaRegionKey.AFRICA]

    assert (out["longitude"], out["latitude"]) == (longitude, latitude)
    assert (out["longitude"], out["latitude"]) != (25.5, 29.2)


def test_the_base_that_names_the_place_goes_with_the_place(flagged) -> None:
    """Withholding ``Egypt`` while printing ``YWAM Egypt`` one column over redacts nothing."""
    out = NaiveProjectOut.model_validate(flagged).model_dump()

    assert out["team"] == ""
    assert BASE not in json.dumps(out)


def test_the_personal_contacts_are_gated_the_way_the_location_is(flagged) -> None:
    """FE-44 §8.1 rule 5 — they belong to a person who may be in that country."""
    out = NaiveProjectOut.model_validate(flagged).model_dump()

    assert out["team_contact"] == ""
    assert out["team_leader_contact"] == ""


def test_a_cleared_record_is_not_reduced(cleared) -> None:
    """The other half. A module that withholds everything is broken, not private."""
    out = NaiveProjectOut.model_validate(cleared).model_dump(by_alias=True)

    assert out["location"] == OPEN_COUNTRY
    assert out["team"] == OPEN_BASE
    assert (out["longitude"], out["latitude"]) == (-51.2, -30.0)
    assert out["team_leader_contact"] == OPEN_CONTACT
    assert out["locationWithheld"] is False


def test_a_shape_that_cannot_evaluate_the_rule_withholds() -> None:
    """**Fail closed, and the DoD's fourth line.**

    A payload assembled from a dict, a partial row or a join that did not select the column
    cannot answer the question, and the two ways to be wrong are not symmetric: withholding a
    record that did not need it costs a coordinator one click through to the record, and
    disclosing one that did costs somebody their safety.
    """
    out = NaiveProjectOut.model_validate(
        {
            "id": "arabic-siwa",
            "language_name": "Siwi",
            "location": COUNTRY,
            "location2": "Siwa Oasis",
            "latitude": 29.2,
            "longitude": 25.5,
            "team": BASE,
            "team_contact": CONTACT,
            "team_leader_contact": CONTACT,
        }
    ).model_dump(by_alias=True)

    assert out["locationWithheld"] is True
    assert COUNTRY not in json.dumps(out)
    assert out["location"] == UNKNOWN_REGION.value


def test_the_withholding_is_visible_and_says_nothing_about_what(flagged) -> None:
    """**The DoD's fifth line.** One bit, and the bit carries no second meaning.

    It says a payload was reduced. It does not say the country, the place, the base, the
    coordinates or the free-text reason the export records beside the flag.
    """
    out = NaiveProjectOut.model_validate(flagged).model_dump(by_alias=True)
    body = json.dumps(out)

    assert out["locationWithheld"] is True
    for secret in (COUNTRY, BASE, CONTACT, "Siwa Oasis", "restricted access country"):
        assert secret not in body, f"{secret} survived the boundary"


# --------------------------------------------------------------------------------------
# Every output path, one at a time
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "shape",
    [NaiveExportRow, NaivePrayerEntry, NaiveNotification, NaiveEtenSnapshot, NaivePulseEntry],
    ids=["export", "prayer wall", "notification", "eten report", "pulse"],
)
def test_every_shape_that_leaves_coordination_withholds_the_place(shape, flagged) -> None:
    """**The DoD's second line, for the four paths that do not exist yet.**

    Each of these is the shape FE-44's contract already froze for an issue later in the wave.
    None of them calls anything; each inherits. That is the claim, and this is where it is
    either true or not.
    """
    payload = {
        "project_id": flagged.id,
        "country": flagged.location,
        "team": flagged.team,
        "text": REQUEST_TEXT,
        "approved_units": 12,
        "sensitive_country": flagged.sensitive_country,
        "region_key": flagged.region_key,
        "id": flagged.id,
        "language_name": flagged.language_name,
        "location": flagged.location,
    }
    out = shape.model_validate(payload).model_dump(by_alias=True)
    body = json.dumps(out)

    assert out["locationWithheld"] is True
    assert COUNTRY not in body
    assert BASE not in body


def test_the_search_haystack_of_a_withheld_project_holds_no_place(flagged, cleared) -> None:
    """A search returns no location at all — it returns whether a query matched, which is the
    same fact arriving as a count. Typing a country is the cheapest probe in the module."""
    assert COUNTRY not in searchable_text(flagged)
    assert BASE not in searchable_text(flagged)
    assert "Siwa Oasis" not in searchable_text(flagged)
    assert ShemaRegionKey.AFRICA.value in searchable_text(flagged)

    assert OPEN_COUNTRY in searchable_text(cleared)
    assert OPEN_BASE in searchable_text(cleared)


async def test_an_aggregate_is_keyed_by_region_and_never_by_a_place(
    db_session, shema_app, flagged, cleared
) -> None:
    """A number does not look like data, so a query written for a badge is the one nobody
    scopes. A count keyed by country would answer *there is a project in Egypt* to somebody
    who is not allowed to know it, without ever returning a record."""
    user = await make_scoped_user(
        db_session,
        shema_app,
        email="counter@shema.test",
        role_key="globalStrategist",
    )
    scope = await region_scope(db_session, user, "shema")

    counts = await count_projects_by_region(db_session, scope)

    assert set(counts) <= {region.value for region in ShemaRegionKey}
    assert COUNTRY not in json.dumps(counts)


def test_the_collection_announces_how_many_it_reduced_and_stays_quiet_otherwise(
    flagged, cleared
) -> None:
    """FE-44 §8.1's map overlay and §8.4's file header, as one function.

    *"0 locations withheld"* on a file with no sensitive projects is a sentence about the
    absence of sensitive projects, said on every file, and interesting exactly when it should
    not be said.
    """
    reduced = [NaiveExportRow.model_validate(row) for row in (flagged, cleared)]
    assert withheld_note(reduced) == 1

    assert withheld_note([NaiveExportRow.model_validate(cleared)]) is None
    assert withheld_note([]) is None


def test_a_log_reference_names_the_record_without_naming_the_place(flagged) -> None:
    """**A log is read by more people and kept longer than a response body**, and usually
    lands in a system with different access control. A stack trace with a project's country
    in it has moved the protected fact somewhere nobody is checking who may know it."""
    line = log_reference(flagged)
    rendered = json.dumps(line)

    assert line["shema_project_id"] == flagged.id
    assert line["shema_location_withheld"] is True
    for secret in (COUNTRY, BASE, CONTACT, "Siwa Oasis", "restricted access country"):
        assert secret not in rendered


async def test_a_refusal_carries_no_column_of_the_row_it_refused(
    db_session, shema_app, flagged, caplog
) -> None:
    """The error path. A caller outside the region is refused, the refusal is logged for
    whoever has to investigate, and neither the message nor the line names the place."""
    from app.core.exceptions import NotFoundError

    user = await make_scoped_user(
        db_session,
        shema_app,
        email="outside@shema.test",
        role_key="coordinator",
        regions=[ShemaRegionKey.SOUTH_AMERICA],
    )
    scope = await region_scope(db_session, user, "shema")

    with caplog.at_level("WARNING"), pytest.raises(NotFoundError) as refusal:
        await get_project(db_session, scope, flagged.id, user=user)

    assert COUNTRY not in str(refusal.value)
    assert COUNTRY not in caplog.text
    assert BASE not in caplog.text


# --------------------------------------------------------------------------------------
# The endpoint nobody told
# --------------------------------------------------------------------------------------


async def test_an_endpoint_written_without_knowledge_of_the_rule_still_protects(
    db_session, shema_app, naive_client, flagged, cleared
) -> None:
    """**The DoD's third line, over the wire.**

    The handler calls a service, returns what it answered and applies nothing. The response
    model declares the record's fields and nothing else. Neither mentions the rule, and the
    flagged record still leaves reduced while the cleared one leaves whole — which is the
    difference between a rule that holds and a module that withholds everything.
    """
    user = await make_scoped_user(
        db_session,
        shema_app,
        email="naive@shema.test",
        role_key="globalStrategist",
    )

    res = await naive_client.get(NAIVE_PROBE, headers=await auth_header(db_session, user))

    assert res.status_code == 200
    by_id = {row["id"]: row for row in res.json()}

    # Read per record and not over the whole body: the cleared record is **supposed** to leave
    # whole, and that is the second half of this test. BE-05 (OBT-394) split the assertion for
    # a fixture pair that shared a country, where a scan of ``res.text`` could not tell the
    # leak from the legitimate value; BE-04 then gave the cleared record its own country
    # (``OPEN_COUNTRY``), so the two halves now name different values. Per record either way —
    # the split is what keeps the test honest if the fixtures ever share a country again.
    withheld = json.dumps(by_id[flagged.id], ensure_ascii=False)
    assert COUNTRY not in withheld
    assert BASE not in withheld
    assert CONTACT not in withheld

    assert by_id[flagged.id]["locationWithheld"] is True
    assert by_id[flagged.id]["location"] == ShemaRegionKey.AFRICA.value
    assert by_id[cleared.id]["locationWithheld"] is False
    assert by_id[cleared.id]["location"] == OPEN_COUNTRY
    assert by_id[cleared.id]["team"] == OPEN_BASE


async def test_the_second_serialization_pass_agrees_with_the_first(
    db_session, shema_app, naive_client, flagged, cleared
) -> None:
    """The seam ``app/models/shema_privacy.py``'s docstring names, pinned.

    FastAPI dumps a returned model and validates the dict back into the response model, which
    drops the excluded inputs — so a handler that builds its own models runs the rule against
    a payload that can no longer read the flag. The two probes must answer identically, or a
    cleared record comes back withheld depending on how a handler happened to be written.
    """
    user = await make_scoped_user(
        db_session,
        shema_app,
        email="twice@shema.test",
        role_key="globalStrategist",
    )
    headers = await auth_header(db_session, user)

    from_rows = await naive_client.get(NAIVE_PROBE, headers=headers)
    from_models = await naive_client.get(NAIVE_MODELS_PROBE, headers=headers)

    assert from_rows.json() == from_models.json()

    # Per record, for the reason the test above states.
    by_id = {row["id"]: row for row in from_models.json()}
    assert COUNTRY not in json.dumps(by_id[flagged.id], ensure_ascii=False)
    assert by_id[cleared.id]["location"] == OPEN_COUNTRY


async def test_the_record_read_still_carries_the_truth(db_session, shema_app, flagged) -> None:
    """**The split, from the other side.** Redaction belongs to output paths; an editing
    surface that hides the data from its own author is not privacy, it is data loss — the
    coordinator filling the record is the person who needs the real country."""
    user = await make_scoped_user(
        db_session,
        shema_app,
        email="author@shema.test",
        role_key="coordinator",
        regions=[ShemaRegionKey.AFRICA],
    )
    scope = await region_scope(db_session, user, "shema")

    project = await get_project(db_session, scope, flagged.id, user=user)

    assert project.location == COUNTRY
    assert project.team == BASE
    assert is_withheld(project) is True


async def test_the_collection_read_hands_out_rows_the_boundary_still_has_to_reduce(
    db_session, shema_app, flagged
) -> None:
    """The service layer answers rows, not payloads, and that is the deliberate shape: the
    record read and the collection read start from the same query, and what separates them is
    which shape the answer leaves in. A test that found the rows redacted here would be
    testing that the record read is broken."""
    user = await make_scoped_user(
        db_session,
        shema_app,
        email="lister@shema.test",
        role_key="globalStrategist",
    )
    scope = await region_scope(db_session, user, "shema")

    rows = await list_projects(db_session, scope)

    assert [row.location for row in rows] == [COUNTRY]
    assert NaiveProjectOut.model_validate(rows[0]).location == ShemaRegionKey.AFRICA.value


# --------------------------------------------------------------------------------------
# Consent, and media against an audience
# --------------------------------------------------------------------------------------


def test_absence_of_consent_is_not_consent(flagged) -> None:
    """``prayer_visibility`` is NULL on this row and NULL means ``coordenacao``: nothing has
    to be written for a request to stay private."""
    assert flagged.prayer_visibility is None
    assert prayer_visibility(flagged) == ShemaPrayerVisibility.COORDENACAO
    assert reaches_prayer_wall(flagged) is False
    assert shared_prayer_text(flagged) == ""
    assert shared_prayer_audio(flagged) is None


async def test_a_request_that_consented_travels_text_and_audio_together(db_session) -> None:
    """``coordenacao`` is a destination and not a queue, so the gate is about where the
    request may go and not about whether it was written."""
    project = await _make_project(
        db_session,
        project_id="shared-one",
        sensitive=False,
        visibility=ShemaPrayerVisibility.REDE,
    )

    assert reaches_prayer_wall(project) is True
    assert shared_prayer_text(project) == REQUEST_TEXT
    assert shared_prayer_audio(project) == "shema/audio/siwa.m4a"


async def test_withdrawing_consent_removes_the_request_from_the_next_read(db_session) -> None:
    """*Cleared, not merely hidden.* The wall is derived, so moving a request back to
    ``coordenacao`` removes it from the next query with no cleanup step — the property to
    preserve once BE-09 stores requests server-side, where a filter over a cached list would
    not be compliance."""
    project = await _make_project(
        db_session,
        project_id="withdrawn-one",
        sensitive=False,
        visibility=ShemaPrayerVisibility.REDE,
    )
    assert shared_prayer_text(project) == REQUEST_TEXT

    project.prayer_visibility = ShemaPrayerVisibility.COORDENACAO
    await db_session.commit()

    assert shared_prayer_text(project) == ""
    assert project.prayer_requests == REQUEST_TEXT, (
        "the record keeps it: coordination is a destination, not a wastebasket"
    )


class _Item:
    def __init__(self, granted: bool | None) -> None:
        self.authorization_granted = granted


def test_an_item_nobody_decided_on_behaves_exactly_as_a_refused_one() -> None:
    """The default is *not authorized*, and only an explicit ``True`` counts."""
    assert is_authorized(_Item(None)) is False
    assert is_authorized(_Item(False)) is False
    assert is_authorized(_Item(True)) is True


def test_media_of_a_withheld_project_never_reaches_a_public_audience(flagged, cleared) -> None:
    """The composition, and the half a per-surface implementation gets wrong: the item is
    authorized, and the audience is what refuses it."""
    granted = _Item(True)

    assert can_share_media(flagged, granted, ShemaAudience.COORDENACAO) is True
    assert can_share_media(flagged, granted, ShemaAudience.PUBLICO) is False
    assert can_share_media(cleared, granted, ShemaAudience.PUBLICO) is True
    assert can_share_media(cleared, _Item(None), ShemaAudience.COORDENACAO) is False


def test_notes_never_leave_coordination_whatever_the_record_says() -> None:
    """Notes carry the most sensitive human context in the record, written by somebody who
    was not thinking about a file being forwarded."""
    assert can_export_notes(ShemaAudience.COORDENACAO) is True
    assert can_export_notes(ShemaAudience.PUBLICO) is False


# --------------------------------------------------------------------------------------
# The bytes, which is where a predicate either holds or is decorative
# --------------------------------------------------------------------------------------


class FakeStore:
    """``gcs_utils`` without a bucket, recording what it was asked to sign."""

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
        return f"https://storage.example/signed/{key}?x-goog-expires={expiry_minutes * 60}"


@pytest.fixture()
def storage(monkeypatch) -> FakeStore:
    fake = FakeStore()
    monkeypatch.setattr(gcs_utils, "generate_signed_download_url", fake.sign)
    return fake


async def _make_photo(db_session, project: ShemaProject, *, granted: bool | None) -> ShemaMediaItem:
    item = ShemaMediaItem(
        project_id=project.id,
        kind=ShemaMediaKind.PHOTO,
        storage_key=storage_key(MEDIA, "11111111-2222-3333-4444-555555555555", "a" * 64, ".jpg"),
        file_name="team at the border.jpg",
        authorization_granted=granted,
    )
    db_session.add(item)
    await db_session.commit()
    return item


def test_the_object_key_names_the_row_and_never_the_project_or_the_upload() -> None:
    """A signed URL travels further than the payload it came from, and a Shemá id is
    ``<language>-<place>``. The key is addressed by content, scoped to the row's own uuid,
    and carries a frozen last segment rather than the name somebody uploaded."""
    key = storage_key(MEDIA, "0f7c-uuid", "b" * 64, ".jpg")

    assert key == f"shema/media/0f7c-uuid/{'b' * 64}/photo.jpg"
    assert "arabic-siwa" not in key
    assert storage_key(MATERIALS, "0f7c-uuid", "b" * 64, ".mp3").endswith("/material.mp3")

    with pytest.raises(ValueError, match="unknown media collection"):
        storage_key("photos", "0f7c-uuid", "b" * 64, ".jpg")


async def test_an_authorized_item_is_served_from_the_private_bucket_and_expires(
    db_session, shema_app, storage, cleared
) -> None:
    """The link is minted per call, against the module's own private bucket, and nothing
    stores it — which is what makes the expiry worth anything."""
    user = await make_scoped_user(
        db_session, shema_app, email="media@shema.test", role_key="globalStrategist"
    )
    scope = await region_scope(db_session, user, "shema")
    item = await _make_photo(db_session, cleared, granted=True)

    link = await media_download_url(db_session, scope, cleared.id, item.id, user=user)

    assert storage.signed == [(GCS_SHEMA_BUCKET, item.storage_key, DOWNLOAD_URL_EXPIRY_MINUTES)]
    assert GCS_SHEMA_BUCKET == "shema-private"
    assert link.expires_in_minutes == DOWNLOAD_URL_EXPIRY_MINUTES
    assert link.url.startswith("https://storage.example/signed/")


async def test_media_of_a_withheld_project_is_refused_to_a_public_audience(
    db_session, shema_app, storage, flagged
) -> None:
    """**The predicate applied where it counts.** The item is authorized; the audience is
    what refuses it, and no URL is minted — so there is no address to leak."""
    from app.core.exceptions import AuthorizationError

    user = await make_scoped_user(
        db_session, shema_app, email="publisher@shema.test", role_key="globalStrategist"
    )
    scope = await region_scope(db_session, user, "shema")
    item = await _make_photo(db_session, flagged, granted=True)

    with pytest.raises(AuthorizationError) as refusal:
        await media_download_url(
            db_session, scope, flagged.id, item.id, user=user, audience=ShemaAudience.PUBLICO
        )

    assert storage.signed == []
    assert COUNTRY not in str(refusal.value)

    link = await media_download_url(db_session, scope, flagged.id, item.id, user=user)
    assert link.url  # the same item, to coordination, is served


async def test_the_refusal_reads_the_same_whichever_gate_closed(
    db_session, shema_app, storage, flagged, cleared
) -> None:
    """*Why* is a fact about the project or about a decision somebody made, and that is the
    thing being protected. An undecided item, a refused one and an authorized one on a
    withheld project asked for publicly all answer one sentence."""
    from app.core.exceptions import AuthorizationError

    user = await make_scoped_user(
        db_session, shema_app, email="prober@shema.test", role_key="globalStrategist"
    )
    scope = await region_scope(db_session, user, "shema")
    undecided = await _make_photo(db_session, cleared, granted=None)
    refused = await _make_photo(db_session, cleared, granted=False)
    withheld = await _make_photo(db_session, flagged, granted=True)

    messages = set()
    for project_id, item, audience in (
        (cleared.id, undecided, ShemaAudience.COORDENACAO),
        (cleared.id, refused, ShemaAudience.COORDENACAO),
        (flagged.id, withheld, ShemaAudience.PUBLICO),
    ):
        with pytest.raises(AuthorizationError) as refusal:
            await media_download_url(
                db_session, scope, project_id, item.id, user=user, audience=audience
            )
        messages.add(str(refusal.value))

    assert len(messages) == 1, f"the refusal tells the three cases apart: {messages}"
    assert storage.signed == []


async def test_a_caller_outside_the_region_learns_nothing_about_the_media(
    db_session, shema_app, storage, flagged
) -> None:
    """The scope gate closes first, and it closes as a 404 — so a probe cannot tell an item
    that is not shared from a project that is not theirs, let alone from one that is not
    there."""
    from app.core.exceptions import NotFoundError

    user = await make_scoped_user(
        db_session,
        shema_app,
        email="elsewhere@shema.test",
        role_key="coordinator",
        regions=[ShemaRegionKey.SOUTH_AMERICA],
    )
    scope = await region_scope(db_session, user, "shema")
    item = await _make_photo(db_session, flagged, granted=True)

    with pytest.raises(NotFoundError):
        await media_download_url(db_session, scope, flagged.id, item.id, user=user)

    assert storage.signed == []


async def test_a_video_has_no_object_to_serve(db_session, shema_app, storage, cleared) -> None:
    """``ProjectVideo.url`` is an address on somebody else's service, and a photo slot may
    carry a caption and no image yet. Both are *nothing to serve* rather than a refusal."""
    from app.core.exceptions import NotFoundError

    user = await make_scoped_user(
        db_session, shema_app, email="video@shema.test", role_key="globalStrategist"
    )
    scope = await region_scope(db_session, user, "shema")
    video = ShemaMediaItem(
        project_id=cleared.id,
        kind=ShemaMediaKind.VIDEO,
        url="https://youtu.be/abc123",
        authorization_granted=True,
    )
    db_session.add(video)
    await db_session.commit()

    with pytest.raises(NotFoundError):
        await media_download_url(db_session, scope, cleared.id, video.id, user=user)

    assert storage.signed == []


async def test_a_material_rides_the_same_three_gates_as_a_photo(
    db_session, shema_app, storage, flagged, cleared
) -> None:
    """FE-44 §8.3 is *media and materials*, and two copies of three gates would be two
    chances for the second one to put the audience gate in the wrong place."""
    from app.core.exceptions import AuthorizationError

    user = await make_scoped_user(
        db_session, shema_app, email="materials@shema.test", role_key="globalStrategist"
    )
    scope = await region_scope(db_session, user, "shema")

    def _material(project: ShemaProject) -> ShemaMaterial:
        return ShemaMaterial(
            project_id=project.id,
            kind=ShemaMaterialKind.AUDIO,
            scope="Luke 1-3",
            storage_key=storage_key(MATERIALS, "9999-uuid", "c" * 64, ".mp3"),
            authorization_granted=True,
        )

    open_one, withheld_one = _material(cleared), _material(flagged)
    db_session.add_all([open_one, withheld_one])
    await db_session.commit()

    link = await material_download_url(db_session, scope, cleared.id, open_one.id, user=user)
    assert link.url.startswith("https://storage.example/signed/")
    assert storage.signed[-1][0] == GCS_SHEMA_BUCKET

    with pytest.raises(AuthorizationError) as refusal:
        await material_download_url(
            db_session,
            scope,
            flagged.id,
            withheld_one.id,
            user=user,
            audience=ShemaAudience.PUBLICO,
        )
    assert COUNTRY not in str(refusal.value)
    assert len(storage.signed) == 1
