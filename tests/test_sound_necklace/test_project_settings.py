"""The project's bead granularity: one decision, one grid.

``beadSec`` defines the bead grid and is mixed into ``manifest_id``, so it is the
coordinate system the pipeline and the training data are built on. Choosing it per
session let two audios of one project land on two incompatible grids. These tests are
written against what makes the setting worth having rather than against its CRUD: that
only a project admin can decide it, that it is decided before anything is cut and cannot
move afterwards, and that the resolved duration the first session lands on is remembered
so a later audio has something to agree with.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.db.models.sound_necklace import SnProjectSettings
from tests.baker import make_project_user_access, make_user
from tests.test_sound_necklace.conftest import auth_header, grant_role, new_session

SN = "/api/sound-necklace"


@pytest.fixture()
async def admin(db_session, sound_necklace_app, project):
    """A project_admin on the shared project — the one who may decide the granularity."""
    user = await make_user(db_session, email="admin@example.com", display_name="Ada")
    await grant_role(db_session, sound_necklace_app.id, user.id, "project_admin")
    await make_project_user_access(db_session, project.id, user.id)
    return user, await auth_header(db_session, user)


async def test_unset_project_reads_as_unset(client, alice, project):
    """A project nobody configured answers with nulls, not 404.

    The setup screen always has something to read: "not decided yet" is a state the SPA
    renders, not an error it has to branch around.
    """
    _user, headers = alice
    res = await client.get(f"{SN}/projects/{project.id}/settings", headers=headers)

    assert res.status_code == 200, res.text
    assert res.json() == {
        "project_id": project.id,
        "granularity_level": None,
        "bead_sec": None,
        "locked": False,
        "updated_at": None,
    }


async def test_admin_sets_the_level_and_everyone_reads_it(client, admin, alice, project):
    _admin, admin_headers = admin
    _alice, alice_headers = alice

    res = await client.put(
        f"{SN}/projects/{project.id}/settings",
        headers=admin_headers,
        json={"granularity_level": "small"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["granularity_level"] == "small"
    assert res.json()["bead_sec"] is None
    assert res.json()["updated_at"] is not None

    read = await client.get(f"{SN}/projects/{project.id}/settings", headers=alice_headers)
    assert read.status_code == 200
    assert read.json()["granularity_level"] == "small"


async def test_confirming_is_what_freezes_it_even_before_anything_is_cut(client, admin, project):
    """The button says "this does not change afterwards"; this is what makes it true.

    The freeze does not wait for a session. A project can be confirmed and frozen having
    cut nothing, which is exactly the state the settings screen produces.
    """
    _admin, headers = admin
    first = await client.put(
        f"{SN}/projects/{project.id}/settings",
        headers=headers,
        json={"granularity_level": "small"},
    )
    assert first.json()["locked"] is True

    res = await client.put(
        f"{SN}/projects/{project.id}/settings",
        headers=headers,
        json={"granularity_level": "large"},
    )

    assert res.status_code == 409, res.text
    assert res.json()["code"] == "PROJECT_GRANULARITY_LOCKED"
    read = await client.get(f"{SN}/projects/{project.id}/settings", headers=headers)
    assert read.json()["granularity_level"] == "small"


async def test_facilitator_may_not_decide_the_granularity(client, alice, project):
    """Reading is everyone's; deciding is the project admin's."""
    _user, headers = alice
    res = await client.put(
        f"{SN}/projects/{project.id}/settings",
        headers=headers,
        json={"granularity_level": "small"},
    )

    assert res.status_code == 403, res.text


async def test_an_outsider_reaches_neither(client, db_session, sound_necklace_app, project):
    """A sound-necklace role is not access to somebody else's project."""
    stranger = await make_user(db_session, email="stranger@example.com")
    await grant_role(db_session, sound_necklace_app.id, stranger.id, "project_admin")
    headers = await auth_header(db_session, stranger)

    read = await client.get(f"{SN}/projects/{project.id}/settings", headers=headers)
    assert read.status_code == 403
    put = await client.put(
        f"{SN}/projects/{project.id}/settings",
        headers=headers,
        json={"granularity_level": "small"},
    )
    assert put.status_code == 403


async def test_unknown_project_is_not_found(client, admin):
    _admin, headers = admin
    res = await client.get(f"{SN}/projects/does-not-exist/settings", headers=headers)
    assert res.status_code in (403, 404), res.text


async def test_an_invented_level_is_refused(client, admin, project):
    _admin, headers = admin
    res = await client.put(
        f"{SN}/projects/{project.id}/settings",
        headers=headers,
        json={"granularity_level": "gigante"},
    )
    assert res.status_code == 422, res.text


async def test_the_first_session_stamps_the_resolved_bead_sec(
    client, db_session, admin, alice, project
):
    """The admin picks a LEVEL; the DURATION comes from the audio's acousteme.

    Nothing can know ``beadSec`` before an audio is cut, so the project's first session is
    what fixes it. From then on it is the value a later audio has to agree with.
    """
    _admin, admin_headers = admin
    _alice, alice_headers = alice
    await client.put(
        f"{SN}/projects/{project.id}/settings",
        headers=admin_headers,
        json={"granularity_level": "medium"},
    )

    await new_session(client, alice_headers, project.id)  # bead_sec 0.5

    res = await client.get(f"{SN}/projects/{project.id}/settings", headers=alice_headers)
    assert res.json()["bead_sec"] == pytest.approx(0.5)
    assert res.json()["locked"] is True


async def test_a_session_on_an_unconfigured_project_stamps_both(client, db_session, alice, project):
    """Sessions predate this table. One created without a settings row makes it.

    Grandfathering is the whole point: the level a session was created with is the
    project's level, and the row it writes is what later audios agree with.
    """
    _alice, headers = alice
    await new_session(client, headers, project.id)

    row = (
        await db_session.execute(
            select(SnProjectSettings).where(SnProjectSettings.project_id == project.id)
        )
    ).scalar_one()
    assert row.granularity_level.value == "medium"
    assert row.bead_sec == pytest.approx(0.5)


async def test_a_grandfathered_project_is_frozen_by_the_session_that_made_its_row(
    client, admin, alice, project
):
    """A project that never saw the settings screen is frozen all the same.

    Its row was written by ``create_session`` at the level that session was cut with, and
    a row IS the lock — so the level cannot be moved out from under audio already cut.
    """
    _admin, admin_headers = admin
    _alice, alice_headers = alice
    await new_session(client, alice_headers, project.id)  # medium

    res = await client.put(
        f"{SN}/projects/{project.id}/settings",
        headers=admin_headers,
        json={"granularity_level": "small"},
    )

    assert res.status_code == 409, res.text
    assert res.json()["code"] == "PROJECT_GRANULARITY_LOCKED"


async def test_re_sending_the_same_level_is_not_a_conflict(client, admin, alice, project):
    """A no-op write is not a change. The settings screen may save what is already there."""
    _admin, admin_headers = admin
    _alice, alice_headers = alice
    await client.put(
        f"{SN}/projects/{project.id}/settings",
        headers=admin_headers,
        json={"granularity_level": "medium"},
    )
    await new_session(client, alice_headers, project.id)

    res = await client.put(
        f"{SN}/projects/{project.id}/settings",
        headers=admin_headers,
        json={"granularity_level": "medium"},
    )

    assert res.status_code == 200, res.text
    assert res.json()["locked"] is True


async def test_the_setting_outlives_the_admin_who_chose_it(client, db_session, admin, project):
    """Deleting the account that decided must not take a project's grid with it."""
    from sqlalchemy import delete

    from app.db.models.auth import User

    admin_user, headers = admin
    await client.put(
        f"{SN}/projects/{project.id}/settings",
        headers=headers,
        json={"granularity_level": "large"},
    )

    await db_session.execute(delete(User).where(User.id == admin_user.id))
    await db_session.commit()

    row = (
        await db_session.execute(
            select(SnProjectSettings).where(SnProjectSettings.project_id == project.id)
        )
    ).scalar_one()
    assert row.granularity_level.value == "large"
    assert row.updated_by is None
