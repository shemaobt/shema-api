"""The leader link — the weakest credential in the system, held to its five words.

*Project-scoped, expiring, revocable, rate-limited and write-mostly.* Every test here is one
of those five, and the fourth line of the DoD gets the longest one, because it is the only one
phrased as a claim about what **cannot** happen:

    A test confirms a leader link cannot read project data beyond the minimum the form needs.

An allowlist of response keys is a test of what somebody remembered to write down.
:func:`test_the_intake_form_carries_nothing_of_the_project_but_its_language` is the other kind:
it fills **every column of the project** with a value unique to that column, asks for the form,
and fails if any of them appears anywhere in the answer. A column added by a later issue is
covered by it the day it is added, without anybody extending a list.

Run over the wire rather than against the services, because three of the five — the rate limit,
the absence of a guard and the 202 — are properties of the route and a service-level test would
pass with the router wired wrongly.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from typing import ClassVar

import pytest
import sqlalchemy as sa
from sqlalchemy import select

from app.api.shema.forms import INTAKE_LINK_RATE_LIMIT, INTAKE_READ_RATE_LIMIT
from app.db.models.shema import ShemaProject
from app.db.models.shema_enums import ShemaRegionKey
from app.db.models.shema_form import ShemaIntakeLink
from app.services.auth.hash_refresh_token import hash_refresh_token
from app.services.shema._intake_tokens import MAX_LINK_DAYS
from tests.test_shema.conftest import PREFIX, auth_header, make_scoped_user, make_shema_project

LINKS = f"{PREFIX}/intake-links"

#: The keys ``GET /api/shema/intake/{token}`` may answer with, and no others.
#:
#: ``locationWithheld`` is here because the shape inherits ``LeavingShape`` and that is
#: deliberate (``app/models/shema_forms.py``): the form declares no place field, so the bit is
#: a constant that says nothing — and the boundary is already underneath the shape for the day
#: somebody adds one.
FORM_KEYS = {"kind", "definitionVersion", "languageName", "expiresAt", "fields", "locationWithheld"}


@pytest.fixture()
async def coordinator(db_session, shema_app):
    """A regional coordinator scoped to South America — **not** a platform admin.

    ``require_role`` returns early on ``is_platform_admin``, so the refusal tests below would
    pass with the guard deleted if this account were one.
    """
    return await make_scoped_user(
        db_session,
        shema_app,
        email="coordenacao@shema.test",
        role_key="coordinator",
        regions=[ShemaRegionKey.SOUTH_AMERICA],
    )


@pytest.fixture()
async def headers(db_session, coordinator):
    return await auth_header(db_session, coordinator)


@pytest.fixture()
async def project(db_session):
    """One record in South America, **with a location that derives to that region**.

    The location is not decoration and leaving it empty is the trap this comment exists for.
    ``save_project`` re-derives ``region_key`` from ``location`` on every write (BE-06), so a
    fixture that sets the region directly and leaves the location blank has a record that
    silently moves to ``other`` the first time anything writes it — and the coordinator who
    could reach it a moment ago gets a 404 on the second call. A real record has both.
    """
    record = await make_shema_project(
        db_session,
        project_id="guarani-mbya",
        region_key=ShemaRegionKey.SOUTH_AMERICA,
        language_name="Guarani Mbyá",
    )
    record.location = "Brazil"
    await db_session.commit()
    return record


async def mint(client, headers, project_id: str = "guarani-mbya", **body):
    return await client.post(LINKS, json={"projectId": project_id, **body}, headers=headers)


# --- project-scoped -------------------------------------------------------------------


async def test_a_minted_link_names_one_project_and_carries_its_token_once(
    client, db_session, shema_app, headers, project
) -> None:
    """The creation response is the only place the raw token ever appears."""
    response = await mint(client, headers)

    assert response.status_code == 201
    body = response.json()
    assert body["projectId"] == "guarani-mbya"
    assert body["status"] == "pending"
    assert body["definitionVersion"] == 1
    assert body["token"]
    assert body["url"].endswith(f"/intake/{body['token']}")


async def test_the_raw_token_is_never_stored(
    client, db_session, shema_app, headers, project
) -> None:
    """Every token in this repository is kept as a hash, and this one has the strongest case:
    its holder has no account, so a database dump is the only place it could be read from."""
    token = (await mint(client, headers)).json()["token"]

    link = (await db_session.execute(select(ShemaIntakeLink))).scalar_one()
    assert link.token_hash == hash_refresh_token(token)
    assert token not in link.token_hash


async def test_a_link_cannot_be_minted_for_a_project_outside_the_scope(
    client, db_session, shema_app, headers
) -> None:
    """Refused the way everything out of scope in this module is: indistinguishably from
    absent, because a 403 on a direct id **is** the existence-without-detail answer."""
    await make_shema_project(db_session, project_id="wolof-dakar", region_key=ShemaRegionKey.AFRICA)

    assert (await mint(client, headers, project_id="wolof-dakar")).status_code == 404


async def test_a_link_with_no_project_is_refused_by_the_shape(
    client, db_session, shema_app, headers, project
) -> None:
    """FE-44 §9.9 writes ``{projectId?, expiresAt}`` and this module requires it: *project-
    scoped* is the first word of the line this credential is judged by, and a link with no
    project is a link to all of them."""
    assert (await client.post(LINKS, json={}, headers=headers)).status_code == 422


async def test_a_member_who_is_not_a_coordinator_may_not_mint_one(
    client, db_session, shema_app, project
) -> None:
    """A real Shemá member with a different role. Issuing a bearer credential to somebody with
    no account is the coordinator's act — ``PULSE_LOOP``'s own three steps are theirs."""
    mentor = await make_scoped_user(
        db_session,
        shema_app,
        email="mentor@shema.test",
        role_key="obtLab",
        regions=[ShemaRegionKey.SOUTH_AMERICA],
    )
    response = await mint(client, await auth_header(db_session, mentor))

    assert response.status_code == 403
    assert "coordinator" in response.json()["detail"]


# --- expiring -------------------------------------------------------------------------


async def test_a_link_expires_by_default_rather_than_never(
    client, db_session, shema_app, headers, project
) -> None:
    """A coordinator on a phone should not have to compute a date for the link to be safe."""
    expires = date.fromisoformat((await mint(client, headers)).json()["expiresAt"])

    assert expires > date.today()
    assert (expires - date.today()).days <= MAX_LINK_DAYS


async def test_a_link_may_not_be_minted_past_the_ceiling(
    client, db_session, shema_app, headers, project
) -> None:
    """*Expiring* is a property of the credential, not of the coordinator's intention: a link
    that can be minted for a year is a link that will be."""
    far = date.today() + timedelta(days=MAX_LINK_DAYS + 1)
    response = await mint(client, headers, expiresAt=far.isoformat())

    assert response.status_code == 400
    assert "may not live that long" in response.json()["detail"]


async def test_a_link_may_not_be_minted_already_dead(
    client, db_session, shema_app, headers, project
) -> None:
    """Minting a dead link silently is the kind of success discovered by a leader in a village."""
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    assert (await mint(client, headers, expiresAt=yesterday)).status_code == 400


async def test_an_expired_link_serves_nothing(
    client, db_session, shema_app, headers, project
) -> None:
    token = (await mint(client, headers)).json()["token"]
    link = (await db_session.execute(select(ShemaIntakeLink))).scalar_one()
    link.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    await db_session.commit()

    response = await client.get(f"{PREFIX}/intake/{token}")

    assert response.status_code == 404
    assert "expired" in response.json()["detail"]


# --- revocable ------------------------------------------------------------------------


async def test_a_revoked_link_serves_nothing_even_while_its_clock_still_runs(
    client, db_session, shema_app, headers, project
) -> None:
    """Revocation is checked ahead of the expiry: *the door a person walked through must not
    later present itself as merely expired*."""
    created = (await mint(client, headers)).json()
    assert (await client.get(f"{PREFIX}/intake/{created['token']}")).status_code == 200

    revoked = await client.post(f"{LINKS}/{created['id']}/revoke", headers=headers)
    assert revoked.status_code == 200
    assert revoked.json()["status"] == "revoked"

    response = await client.get(f"{PREFIX}/intake/{created['token']}")
    assert response.status_code == 404
    assert "revoked" in response.json()["detail"]


async def test_revoking_twice_is_not_an_error(
    client, db_session, shema_app, headers, project
) -> None:
    """A coordinator who taps revoke on a bad connection and taps it again is asking for one
    thing, and the answer both times is the link, revoked."""
    link_id = (await mint(client, headers)).json()["id"]

    first = await client.post(f"{LINKS}/{link_id}/revoke", headers=headers)
    second = await client.post(f"{LINKS}/{link_id}/revoke", headers=headers)

    assert second.status_code == 200
    assert second.json()["revokedAt"] == first.json()["revokedAt"]


async def test_a_link_on_another_region_cannot_be_revoked(
    client, db_session, shema_app, headers, project
) -> None:
    """Revocation is a write and is scoped like one."""
    await make_shema_project(db_session, project_id="wolof-dakar", region_key=ShemaRegionKey.AFRICA)
    # Minted by the coordinator of the other region: ``globalStrategist`` does not hold the
    # role that mints, so an account with only that key could not have issued this link.
    africa = await make_scoped_user(
        db_session,
        shema_app,
        email="africa@shema.test",
        role_key="coordinator",
        regions=[ShemaRegionKey.AFRICA],
    )
    elsewhere = await mint(client, await auth_header(db_session, africa), project_id="wolof-dakar")

    response = await client.post(f"{LINKS}/{elsewhere.json()['id']}/revoke", headers=headers)
    assert response.status_code == 404


async def test_the_listing_shows_the_links_and_never_their_tokens(
    client, db_session, shema_app, headers, project
) -> None:
    """A listing that handed the token back would make *revoked* a word rather than a fact:
    the credential would still be readable by everybody who can read the list."""
    token = (await mint(client, headers)).json()["token"]

    response = await client.get(LINKS, headers=headers)

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert "token" not in response.json()[0]
    assert token not in response.text


async def test_an_unknown_token_is_refused(client, db_session, shema_app) -> None:
    assert (await client.get(f"{PREFIX}/intake/not-a-token-this-server-issued")).status_code == 404


# --- write-mostly: the DoD's fourth line ----------------------------------------------


#: Columns the sweep below leaves alone, and why each one is not a hole in it.
#:
#: ``id`` and ``language_name`` are the two the form is allowed to know about — the language
#: because a leader holding two links has to tell them apart, and the id because it is derived
#: from the language and would flag the same string twice. ``version`` is the record's
#: concurrency counter and names nothing about where a project is.
_NOT_PLANTED = frozenset({"id", "language_name", "version"})


def _sentinel_values(project: ShemaProject) -> dict[str, object]:
    """Fill every column of the project with a value unique to that column.

    Read off the mapper rather than typed out, so **a column a later issue adds is covered the
    day it is added** — which is the difference between a test of this rule and a test of the
    columns somebody remembered when they wrote it.

    Only the types that can carry a value traceable back to their own column are planted.
    ``Enum`` is skipped although it *is* a ``String`` subclass: its vocabulary is closed, the
    module turns ``create_constraint`` back on (``docs/shema.md`` §7.3), and a made-up member
    would be refused by the database before the test could ask its question. A foreign key is
    skipped for the same reason and not a weaker one — the suite runs with
    ``PRAGMA foreign_keys=ON``, so an invented reference is refused at the commit. A boolean
    and a date are skipped because neither has a value that could be traced back to one
    column.

    **The coordinates are planted**, and they are the sharpest case in the list: a leaked
    latitude is a leaked location that no redaction of a text field would have caught. They get
    whole numbers so the float round-trips to a string the search can match exactly.
    """
    planted: dict[str, object] = {}
    for index, column in enumerate(sa.inspect(ShemaProject).columns):
        if column.key in _NOT_PLANTED or isinstance(column.type, sa.Enum):
            continue
        if column.foreign_keys:
            continue
        text = f"LEAK-{column.key.upper().replace('_', '-')}"
        if isinstance(column.type, sa.String | sa.Text):
            setattr(project, column.key, text)
            planted[column.key] = text
        elif isinstance(column.type, sa.JSON):
            setattr(project, column.key, [text])
            planted[column.key] = text
        elif isinstance(column.type, sa.Float):
            value = float(1000 + index)
            setattr(project, column.key, value)
            planted[column.key] = str(value)
        elif isinstance(column.type, sa.Integer) and not isinstance(column.type, sa.Boolean):
            value = 900000 + index
            setattr(project, column.key, value)
            planted[column.key] = str(value)
    return planted


async def test_the_intake_form_carries_nothing_of_the_project_but_its_language(
    client, db_session, shema_app, headers, project
) -> None:
    """**The DoD's fourth line.** Not an allowlist of keys — a search of the whole payload.

    Every readable column of the record is planted with a value that names it, the link is
    opened, and the answer must contain none of them. The location, the country, the base, the
    three contacts, the prayer text, the notes, the status comments, the progress tables: a
    forwarded WhatsApp message reaches whoever it reaches, and the answer to *what does it
    disclose* has to be **nothing**, checked rather than reviewed.
    """
    planted = _sentinel_values(project)
    await db_session.commit()
    assert len(planted) > 30, "the sweep planted almost nothing and would pass on an empty row"
    token = (await mint(client, headers)).json()["token"]

    response = await client.get(f"{PREFIX}/intake/{token}")

    assert response.status_code == 200
    leaked = sorted(column for column, value in planted.items() if str(value) in response.text)
    assert leaked == [], f"the intake form disclosed project columns: {leaked}"


async def test_the_intake_form_answers_exactly_the_minimum_that_makes_it_answerable(
    client, db_session, shema_app, headers, project
) -> None:
    """The other half of the same claim, keyed rather than searched.

    The language name **is** there and is the one thing of the project that is: a leader
    holding links for two projects has to be able to tell which form they are filling.
    """
    token = (await mint(client, headers)).json()["token"]

    body = (await client.get(f"{PREFIX}/intake/{token}")).json()

    assert set(body) == FORM_KEYS
    assert body["languageName"] == "Guarani Mbyá"
    assert body["kind"] == "pulso"
    assert {field["key"] for field in body["fields"]} >= {"submittedBy", "period"}


async def test_the_form_does_not_publish_which_column_an_answer_lands_in(
    client, db_session, shema_app, headers, project
) -> None:
    """``column`` is in the stored spec and is dropped on the way out. *Where a prayer request
    is kept* is a description of the record's shape that the form does not need to be
    answerable, and it is handed to an anonymous caller for free if nobody drops it."""
    token = (await mint(client, headers)).json()["token"]

    body = (await client.get(f"{PREFIX}/intake/{token}")).json()

    for field in body["fields"]:
        assert "column" not in field
    assert "prayer_requests" not in body["fields"][0].get("labelKey", "")


async def test_the_intake_routes_need_no_authorization_header(
    client, db_session, shema_app, headers, project
) -> None:
    """The premise of this whole file, asserted so it cannot become true by accident later.

    ``tests/test_shema/test_access.py`` names the path in ``UNAUTHENTICATED_PATHS``; this is
    the other side of that line — the route really does answer with no bearer token, which is
    the one thing the audit cannot check by reading a dependency tree.
    """
    token = (await mint(client, headers)).json()["token"]

    assert (await client.get(f"{PREFIX}/intake/{token}")).status_code == 200
    submission = await client.post(
        f"{PREFIX}/intake/{token}",
        json={"definitionVersion": 1, "answers": {"submittedBy": "Kuaray", "period": "2026-09"}},
    )
    assert submission.status_code == 202
    assert submission.content == b""


# --- rate-limited ---------------------------------------------------------------------


async def test_the_intake_read_is_rate_limited(
    client, db_session, shema_app, headers, project
) -> None:
    """It is unauthenticated by design and is therefore the endpoint that will be found."""
    token = (await mint(client, headers)).json()["token"]
    allowed = int(INTAKE_LINK_RATE_LIMIT.split("/")[0])

    statuses = [
        (await client.get(f"{PREFIX}/intake/{token}")).status_code for _ in range(allowed + 1)
    ]

    assert statuses[:allowed] == [200] * allowed
    assert statuses[-1] == 429


async def test_the_limit_is_per_link_and_not_only_per_address(
    client, db_session, shema_app, headers, project
) -> None:
    """**Why there are two keys and not one.** A link forwarded to a hundred phones is one
    token, and a limit keyed only on the caller's address never notices it; a limit keyed only
    on the token never notices somebody walking the keyspace. This proves the half a per-address
    limit cannot buy: the two links share an address and do not share a budget.
    """
    first = (await mint(client, headers)).json()["token"]
    second = (await mint(client, headers)).json()["token"]
    per_link = int(INTAKE_LINK_RATE_LIMIT.split("/")[0])
    per_address = int(INTAKE_READ_RATE_LIMIT.split("/")[0])
    assert per_link < per_address, "the per-link bucket has to bite first for this to be a test"

    for _ in range(per_link):
        await client.get(f"{PREFIX}/intake/{first}")

    assert (await client.get(f"{PREFIX}/intake/{first}")).status_code == 429
    assert (await client.get(f"{PREFIX}/intake/{second}")).status_code == 200


async def test_the_rate_limit_bucket_is_the_hash_and_not_the_token(
    client, db_session, shema_app, headers, project
) -> None:
    """A limiter's store is a place a credential should not be readable from — the same reason
    ``bearer_token_key`` in ``app/core/rate_limit.py`` hashes what it buckets on."""
    from app.api.shema.forms import intake_token_key

    class _Request:
        path_params: ClassVar[dict[str, str]] = {"token": "a-raw-token"}

    key = intake_token_key(_Request())

    assert key == hash_refresh_token("a-raw-token")
    assert "a-raw-token" not in key


# --- what the link may write ----------------------------------------------------------


async def test_a_submission_through_the_link_does_not_move_the_record(
    client, db_session, shema_app, headers, project
) -> None:
    """**202 means accepted, not applied.** ``save_project`` takes an actor the audit trail can
    name and a version somebody read, and a link has neither — so the answer lands in the inbox
    and a coordinator applies it. The weakest credential in the system does not move the numbers
    the ETEN year-end report is reconstructed from on its own."""
    token = (await mint(client, headers)).json()["token"]
    before = project.version

    response = await client.post(
        f"{PREFIX}/intake/{token}",
        json={
            "definitionVersion": 1,
            "answers": {
                "submittedBy": "Kuaray",
                "period": "2026-09",
                "bookProgress": [
                    {
                        "id": "mrk",
                        "name": "Marcos",
                        "chapters": 16,
                        "translated": 9,
                        "communityChecked": 0,
                        "mentorApproved": 0,
                    }
                ],
            },
        },
    )

    assert response.status_code == 202
    await db_session.refresh(project)
    assert project.version == before
    assert project.translated_units == 0


async def test_the_first_answer_stamps_the_link_and_a_second_one_does_not_move_it(
    client, db_session, shema_app, headers, project
) -> None:
    """``used_at`` records the **first** answer rather than spending the link.

    The Pulse is monthly and the leader is the person who is offline; a link that had to be
    re-minted and re-sent through WhatsApp before every cycle would be replaced by a coordinator
    typing the answers in themselves. What bounds the abuse is the expiry, the revocation and
    the rate limit — three things that hold whether or not anybody remembers to re-send.
    """
    token = (await mint(client, headers)).json()["token"]
    answer = {"definitionVersion": 1, "answers": {"submittedBy": "Kuaray", "period": "2026-09"}}

    await client.post(f"{PREFIX}/intake/{token}", json=answer)
    link = (await db_session.execute(select(ShemaIntakeLink))).scalar_one()
    await db_session.refresh(link)
    first_use = link.used_at
    assert first_use is not None

    later = {**answer, "answers": {**answer["answers"], "period": "2026-10"}}
    assert (await client.post(f"{PREFIX}/intake/{token}", json=later)).status_code == 202

    await db_session.refresh(link)
    assert link.used_at == first_use


async def test_a_revoked_link_cannot_submit_either(
    client, db_session, shema_app, headers, project
) -> None:
    """The guard is one function, so the write inherits every check the read does."""
    created = (await mint(client, headers)).json()
    await client.post(f"{LINKS}/{created['id']}/revoke", headers=headers)

    response = await client.post(
        f"{PREFIX}/intake/{created['token']}",
        json={"definitionVersion": 1, "answers": {"submittedBy": "Kuaray", "period": "2026-09"}},
    )

    assert response.status_code == 404


async def test_a_submission_too_large_to_be_a_form_is_refused(
    client, db_session, shema_app, headers, project
) -> None:
    """A ceiling on an unauthenticated write: generous against what a team leader types on a
    phone, small against what a script would send."""
    token = (await mint(client, headers)).json()["token"]

    response = await client.post(
        f"{PREFIX}/intake/{token}",
        json={
            "definitionVersion": 1,
            "answers": {"submittedBy": "Kuaray", "period": "2026-09", "voice": "x" * 500_000},
        },
    )

    assert response.status_code == 400
    assert "Nothing was kept" in json.dumps(response.json())
