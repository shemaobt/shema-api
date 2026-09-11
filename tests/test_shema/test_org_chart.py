"""The chart, the account link, the audit trail, and who may read which of the three.

What is tested is what the issue asked for and what the design forbade, not that SQLAlchemy
stores a string: that twenty-one seats exist without a seeding step, that a change is never
silent, that the account link follows the person and not the slot, that the trail is scoped,
and that the three narrower routes are actually narrower.
"""

from __future__ import annotations

from app.db.models.shema_enums import ShemaRegionKey
from tests.baker import make_user
from tests.test_shema.conftest import (
    REGIONS,
    ROLE_CHANGES,
    auth_header,
    grant,
    make_scoped_user,
)

ASIA_TEAM = f"{REGIONS}/asia/team"


async def _coordinator(db_session, shema_app, *, email: str, regions=None, everywhere=False):
    """A ``coordinator``, optionally reaching every region.

    ``everywhere`` grants ``globalStrategist`` **beside** ``coordinator`` rather than instead
    of it, which is the shape ``docs/shema.md`` §4.2 names as ordinary — an account
    legitimately holds more than one Shemá role, and it is why grants go through
    ``grant_app_role``. A ``coordinator`` with no region row reaches **nothing**, not
    everything: BE-03 read §6.1's *no rows means global* narrowly on purpose, because
    ``access_request`` grants a role and no region, so the loose reading would land every
    approved account globally scoped.
    """
    user = await make_scoped_user(
        db_session, shema_app, email=email, role_key="coordinator", regions=regions
    )
    if everywhere:
        await grant(db_session, user, shema_app, "globalStrategist")
    return user, await auth_header(db_session, user)


# --- the chart ------------------------------------------------------------------------


async def test_the_chart_is_twenty_one_seats_on_an_empty_table(
    db_session, client, shema_app
) -> None:
    """No seeding step stands between a fresh install and a screen that renders.

    FE-44 §5.3 makes twenty-one unassigned roles the honest wave-1 state, *because the
    prototype's names were real people hardcoded in a file*. The grid comes from the two
    vocabularies and the rows are an overlay, so this passes on a database nobody has written
    to — which is the property, not a convenience.
    """
    user = await make_scoped_user(
        db_session, shema_app, email="member@shema.test", role_key="obtLab", regions=[]
    )

    res = await client.get(REGIONS, headers=await auth_header(db_session, user))

    assert res.status_code == 200
    body = res.json()
    assert [row["key"] for row in body] == [key.value for key in ShemaRegionKey]
    assert all(
        row["team"] == {"coordinator": "", "obtLab": "", "resourceCircle": ""} for row in body
    )
    assert body[3]["labelKey"] == "continent_asia"


async def test_every_member_reads_the_chart_whatever_their_role_and_region(
    db_session, client, shema_app
) -> None:
    """The chart's four consumers include the sidebar panel that shows all seven regions.

    Read by ``obtLab`` with an **empty** region scope — an account that reaches no project at
    all — because the rule being pinned is that the org chart is not project data and is not
    narrowed by the project scope.
    """
    user = await make_scoped_user(
        db_session, shema_app, email="narrow@shema.test", role_key="obtLab", regions=[]
    )

    res = await client.get(REGIONS, headers=await auth_header(db_session, user))

    assert res.status_code == 200
    assert len(res.json()) == 7


# --- the write, and its trail ----------------------------------------------------------


async def test_a_save_writes_an_audit_row_for_every_seat_that_moved(
    db_session, client, shema_app
) -> None:
    """``docs/shema.md`` §5.8: a team change is a write with an audit row, not a silent update.

    Two seats filled and one left empty, so the outcome counts are read against three
    different transitions in one save rather than against a single one repeated.
    """
    user, headers = await _coordinator(
        db_session, shema_app, email="asia@shema.test", regions=[ShemaRegionKey.ASIA]
    )

    res = await client.put(
        ASIA_TEAM,
        headers=headers,
        json={"team": {"coordinator": "Ana Lima", "obtLab": "Bruno Sá", "resourceCircle": ""}},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["outcome"] == {"changed": 2, "filled": 2, "cleared": 0}
    assert [(row["role"], row["from"], row["to"]) for row in body["changes"]] == [
        ("coordinator", "", "Ana Lima"),
        ("obtLab", "", "Bruno Sá"),
    ]
    assert body["changes"][0]["changedBy"] == user.display_name
    assert len(body["changes"][0]["changedAt"]) == len("2026-09-11")


async def test_a_save_that_changed_nothing_says_so(db_session, client, shema_app) -> None:
    """FE-44 §9.10's own sentence, and the reason ``SaveOutcome`` exists at all.

    A 204 could not carry this and a screen has no other way to learn it.
    """
    _user, headers = await _coordinator(
        db_session, shema_app, email="quiet@shema.test", regions=[ShemaRegionKey.ASIA]
    )
    payload = {"team": {"coordinator": "Ana Lima", "obtLab": "", "resourceCircle": ""}}
    await client.put(ASIA_TEAM, headers=headers, json=payload)

    res = await client.put(ASIA_TEAM, headers=headers, json=payload)

    assert res.json()["outcome"] == {"changed": 0, "filled": 0, "cleared": 0}
    assert res.json()["changes"] == []


async def test_clearing_a_seat_is_counted_as_cleared_and_keeps_the_departed_name_in_the_trail(
    db_session, client, shema_app
) -> None:
    """The issue's *historical attribution handled deliberately*, in one assertion.

    The person leaves the chart and every consumer that reads it by reference; what survives
    is the record of the act, under the name they held at the time. The trail is not a
    directory — it carries no contact, no account and no country, and it is the only surface
    that shows the name at all.
    """
    _user, headers = await _coordinator(
        db_session, shema_app, email="clear@shema.test", regions=[ShemaRegionKey.ASIA]
    )
    await client.put(
        ASIA_TEAM,
        headers=headers,
        json={"team": {"coordinator": "Ana Lima", "obtLab": "", "resourceCircle": ""}},
    )

    res = await client.put(
        ASIA_TEAM,
        headers=headers,
        json={"team": {"coordinator": "", "obtLab": "", "resourceCircle": ""}},
    )

    assert res.json()["outcome"] == {"changed": 1, "filled": 0, "cleared": 1}

    chart = await client.get(REGIONS, headers=headers)
    asia = next(row for row in chart.json() if row["key"] == "asia")
    assert asia["team"]["coordinator"] == ""

    trail = await client.get(ROLE_CHANGES, headers=headers)
    assert [(row["from"], row["to"]) for row in trail.json()] == [
        ("Ana Lima", ""),
        ("", "Ana Lima"),
    ]
    assert set(trail.json()[0]) == {"regionKey", "role", "from", "to", "changedBy", "changedAt"}


async def test_a_rename_is_changed_but_neither_filled_nor_cleared(
    db_session, client, shema_app
) -> None:
    """The three counts are not the same number wearing three names."""
    _user, headers = await _coordinator(
        db_session, shema_app, email="swap@shema.test", regions=[ShemaRegionKey.ASIA]
    )
    await client.put(
        ASIA_TEAM,
        headers=headers,
        json={"team": {"coordinator": "Ana Lima", "obtLab": "", "resourceCircle": ""}},
    )

    res = await client.put(
        ASIA_TEAM,
        headers=headers,
        json={"team": {"coordinator": "Bruno Sá", "obtLab": "", "resourceCircle": ""}},
    )

    assert res.json()["outcome"] == {"changed": 1, "filled": 0, "cleared": 0}


# --- the account link -------------------------------------------------------------------


async def test_a_seat_points_at_an_account_and_the_name_still_comes_from_the_chart(
    db_session, client, shema_app
) -> None:
    """The DoD's first line for the team half: related to an existing user where one exists.

    The account's own ``display_name`` is deliberately different from the seat's name, so a
    chart that resolved the name through the account would fail here rather than pass by
    coincidence.
    """
    _user, headers = await _coordinator(
        db_session, shema_app, email="link@shema.test", regions=[ShemaRegionKey.ASIA]
    )
    holder = await make_user(db_session, email="ana@shema.test", display_name="Ana R. Lima")

    await client.put(
        ASIA_TEAM,
        headers=headers,
        json={
            "team": {"coordinator": "Ana Lima", "obtLab": "", "resourceCircle": ""},
            "accounts": {"coordinator": holder.id},
        },
    )

    res = await client.get(ASIA_TEAM, headers=headers)

    assert res.json()["team"]["coordinator"] == "Ana Lima"
    assert res.json()["teamAccounts"]["coordinator"] == holder.id


async def test_replacing_the_holder_clears_the_account_the_previous_one_carried(
    db_session, client, shema_app
) -> None:
    """``docs/shema.md`` §5.5's rule for a media authorization, read on a seat.

    An account left pointing at a seat whose holder changed is worse than an empty column:
    it reads as a verified identity and nothing about it looks stale.
    """
    _user, headers = await _coordinator(
        db_session, shema_app, email="follow@shema.test", regions=[ShemaRegionKey.ASIA]
    )
    holder = await make_user(db_session, email="ana2@shema.test")
    await client.put(
        ASIA_TEAM,
        headers=headers,
        json={
            "team": {"coordinator": "Ana Lima", "obtLab": "", "resourceCircle": ""},
            "accounts": {"coordinator": holder.id},
        },
    )

    await client.put(
        ASIA_TEAM,
        headers=headers,
        json={"team": {"coordinator": "Bruno Sá", "obtLab": "", "resourceCircle": ""}},
    )

    res = await client.get(ASIA_TEAM, headers=headers)
    assert res.json()["teamAccounts"]["coordinator"] is None


async def test_naming_the_account_of_the_person_already_there_writes_no_audit_row(
    db_session, client, shema_app
) -> None:
    """``RoleChange`` is a *name* transition, and a row where ``from`` equals ``to`` would say
    *something happened here* to a reader who then cannot find out what."""
    _user, headers = await _coordinator(
        db_session, shema_app, email="correct@shema.test", regions=[ShemaRegionKey.ASIA]
    )
    holder = await make_user(db_session, email="ana3@shema.test")
    await client.put(
        ASIA_TEAM,
        headers=headers,
        json={"team": {"coordinator": "Ana Lima", "obtLab": "", "resourceCircle": ""}},
    )

    res = await client.put(
        ASIA_TEAM,
        headers=headers,
        json={
            "team": {"coordinator": "Ana Lima", "obtLab": "", "resourceCircle": ""},
            "accounts": {"coordinator": holder.id},
        },
    )

    assert res.json()["outcome"]["changed"] == 0
    detail = await client.get(ASIA_TEAM, headers=headers)
    assert detail.json()["teamAccounts"]["coordinator"] == holder.id


async def test_an_unknown_account_is_refused_before_anything_is_written(
    db_session, client, shema_app
) -> None:
    """422 and not a 500 from the database, which is what ``UnknownReferenceError`` is for —
    and the seat is untouched, because the check runs before the first write."""
    _user, headers = await _coordinator(
        db_session, shema_app, email="ghost@shema.test", regions=[ShemaRegionKey.ASIA]
    )

    res = await client.put(
        ASIA_TEAM,
        headers=headers,
        json={
            "team": {"coordinator": "Ana Lima", "obtLab": "", "resourceCircle": ""},
            "accounts": {"coordinator": "no-such-user"},
        },
    )

    assert res.status_code == 422
    chart = await client.get(ASIA_TEAM, headers=headers)
    assert chart.json()["team"]["coordinator"] == ""


# --- who may do what --------------------------------------------------------------------


async def test_a_regional_coordinator_cannot_write_another_region(
    db_session, client, shema_app
) -> None:
    """``docs/shema.md`` §6.2: the scope is applied by the service, never by the router.

    403 rather than 404 here, unlike a project id: the seven region keys are a public
    vocabulary the console already holds, so there is no existence to protect and *not yours*
    is the honest answer. ``_scope.py`` argues at length for the opposite on a project slug,
    and the two answers are different because the two facts are.
    """
    _user, headers = await _coordinator(
        db_session, shema_app, email="africa@shema.test", regions=[ShemaRegionKey.AFRICA]
    )

    res = await client.put(
        ASIA_TEAM,
        headers=headers,
        json={"team": {"coordinator": "Ana Lima", "obtLab": "", "resourceCircle": ""}},
    )

    assert res.status_code == 403
    assert "asia" in res.json()["detail"]


async def test_the_trail_carries_only_the_regions_the_caller_reaches(
    db_session, client, shema_app
) -> None:
    """A regional holder reads their regions' history and not the organisation's."""
    _global_user, global_headers = await _coordinator(
        db_session, shema_app, email="global@shema.test", everywhere=True
    )
    for region in ("asia", "africa"):
        await client.put(
            f"{REGIONS}/{region}/team",
            headers=global_headers,
            json={"team": {"coordinator": f"Lead {region}", "obtLab": "", "resourceCircle": ""}},
        )

    _local, local_headers = await _coordinator(
        db_session, shema_app, email="onlyafrica@shema.test", regions=[ShemaRegionKey.AFRICA]
    )
    res = await client.get(ROLE_CHANGES, headers=local_headers)

    assert [row["regionKey"] for row in res.json()] == ["africa"]
    assert len((await client.get(ROLE_CHANGES, headers=global_headers)).json()) == 2


async def test_a_regional_role_with_no_region_reads_no_trail_at_all(
    db_session, client, shema_app
) -> None:
    """The fail-closed floor, repeated here because this query does not go through
    ``visible_projects`` and so does not inherit it."""
    _global_user, global_headers = await _coordinator(
        db_session, shema_app, email="writer@shema.test", everywhere=True
    )
    await client.put(
        ASIA_TEAM,
        headers=global_headers,
        json={"team": {"coordinator": "Ana Lima", "obtLab": "", "resourceCircle": ""}},
    )

    _unscoped, headers = await _coordinator(
        db_session, shema_app, email="unscoped@shema.test", regions=[]
    )

    assert (await client.get(ROLE_CHANGES, headers=headers)).json() == []


async def test_the_trail_and_the_write_refuse_a_member_who_is_not_a_coordinator(
    db_session, client, shema_app
) -> None:
    """Narrower than authentication, which is the DoD's fourth line.

    A real Shemá member with a real region — the refusal is about the role and nothing else.
    Not an admin account, deliberately: an admin returns early from both platform guards and
    this would pass with the alias deleted.
    """
    user = await make_scoped_user(
        db_session,
        shema_app,
        email="lab@shema.test",
        role_key="obtLab",
        regions=[ShemaRegionKey.ASIA],
    )
    headers = await auth_header(db_session, user)

    assert (await client.get(REGIONS, headers=headers)).status_code == 200
    assert (await client.get(ROLE_CHANGES, headers=headers)).status_code == 403
    assert (await client.get(ASIA_TEAM, headers=headers)).status_code == 403
    refused = await client.put(
        ASIA_TEAM,
        headers=headers,
        json={"team": {"coordinator": "Ana Lima", "obtLab": "", "resourceCircle": ""}},
    )
    assert refused.status_code == 403


async def test_an_account_with_no_shema_grant_reaches_none_of_it(
    db_session, client, shema_app
) -> None:
    """Deny by default, inherited from ``app/api/shema/__init__.py`` rather than declared here."""
    outsider = await make_user(db_session, email="outsider@shema.test")
    headers = await auth_header(db_session, outsider)

    assert (await client.get(REGIONS, headers=headers)).status_code == 403


async def test_the_chart_refuses_a_region_key_that_is_not_one_of_the_seven(
    db_session, client, shema_app
) -> None:
    """The vocabulary is closed and the path type is what closes it."""
    _user, headers = await _coordinator(
        db_session, shema_app, email="bad@shema.test", everywhere=True
    )

    res = await client.get(f"{REGIONS}/atlantis/team", headers=headers)

    assert res.status_code == 422


async def test_a_platform_admin_passes_the_narrow_routes(db_session, client, shema_app) -> None:
    """The installation's standing rule, pinned so the negative tests above cannot drift onto
    it — every one of them uses a non-admin account for exactly this reason."""
    admin = await make_user(db_session, email="chartadmin@shema.test", is_platform_admin=True)
    headers = await auth_header(db_session, admin)

    assert (await client.get(ROLE_CHANGES, headers=headers)).status_code == 200


async def test_an_account_for_a_seat_with_nobody_in_it_is_refused(
    db_session, client, shema_app
) -> None:
    """The reference answers *which account is this person*, and there is no person.

    Stored, it would be a link waiting to attach itself to whoever is typed into the seat
    next — which is the same failure ``holder_user_id`` is cleared on a rename to avoid,
    reached from the empty side.
    """
    _user, headers = await _coordinator(
        db_session, shema_app, email="orphan@shema.test", regions=[ShemaRegionKey.ASIA]
    )
    holder = await make_user(db_session, email="nobody@shema.test")

    res = await client.put(
        ASIA_TEAM,
        headers=headers,
        json={
            "team": {"coordinator": "", "obtLab": "", "resourceCircle": ""},
            "accounts": {"coordinator": holder.id},
        },
    )

    assert res.status_code == 400
    assert "coordinator" in res.json()["detail"]


async def test_saving_three_empty_names_writes_no_rows_at_all(
    db_session, client, shema_app
) -> None:
    """A row is what it means for somebody to hold an office.

    Asked of the table rather than of the chart, because the chart answers twenty-one seats
    either way — which is exactly what would hide three rows that say nothing.
    """
    from sqlalchemy import func, select

    from app.db.models.shema_org_chart import ShemaRegionTeam

    _user, headers = await _coordinator(
        db_session, shema_app, email="empty@shema.test", regions=[ShemaRegionKey.ASIA]
    )

    res = await client.put(
        ASIA_TEAM,
        headers=headers,
        json={"team": {"coordinator": "", "obtLab": "", "resourceCircle": ""}},
    )

    assert res.json()["outcome"] == {"changed": 0, "filled": 0, "cleared": 0}
    rows = await db_session.execute(select(func.count()).select_from(ShemaRegionTeam))
    assert rows.scalar_one() == 0
