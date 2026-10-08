"""A withdrawn prayer request leaves the archived Pulses too — OBT-561, narrowed by OBT-576.

Karina, via Daniel, 1/out/2026, on what happens to the Pulso Mensal kept on file when the team
takes back the authorization of a prayer request: *"o pedido é apagado também do Pulso
guardado"*. Every other copy already went with the withdrawal (the wall is derived, the export
log keeps ids); the archive was the one that kept the text as it arrived.

The lines this file holds, one test each:

* withdrawing — the team stating ``coordenacao`` over a request that was in ``rede`` — removes
  the request from every archived Pulse of the project that shared it (answered ``rede``) in
  the same words, and from no other: not from a Pulse that shared an earlier wording (Karina,
  6/out/2026: *"só do Pulso com o texto exatamente igual"*), nor from one that kept its request
  in coordination; and the wall loses it, as before;
* *the same words* is the text as its reader sees it — the ends, the kind of line break and
  the composition of a letter are not compared, and everything else is;
* the removal leaves who and when on the row and never the text;
* after it, no read of a submission — the inbox, the opened Pulse, the export — returns the
  text, and the same file sent again does not bring it back;
* a pending Pulse whose request was removed does not authorize anything when it is applied;
* a new text that replaces the request is not a withdrawal, and erases nothing;
* the health assessment, the other write that carries the request, withdraws the same way.
"""

import pytest
from sqlalchemy import select

from app.db.models.shema_enums import ShemaPrayerVisibility, ShemaRegionKey
from app.db.models.shema_form import ShemaSubmission
from app.services.shema._consent import same_request, withdrawn_request
from app.services.shema._submission_archive import archived_answers
from tests.test_shema.conftest import PREFIX, auth_header, make_scoped_user, make_shema_project

PROJECT_ID = "guarani-mbya"
PROJECTS = f"{PREFIX}/projects"
LINKS = f"{PREFIX}/intake-links"
SUBMISSIONS = f"{PREFIX}/forms/submissions"
EXPORT = f"{PREFIX}/export/projects"
WALL = f"{PREFIX}/prayer/requests"

#: The request the team shared and then took back — a canary no surface may return afterwards.
WITHDRAWN = "PEDIDO-RETIRADO orem pela familia do tradutor"
#: A request a Pulse kept in coordination — never shared, so nothing to take back.
KEPT = "PEDIDO-DA-COORDENACAO orem pela colheita"
#: The words the Pulse arrived with, before the record spelled them otherwise.
EARLIER = "PEDIDO-RETIRADO orem pela familia do tradutr"


@pytest.fixture()
async def coordinator(db_session, shema_app):
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
    """A record whose request is on the wall — the text the team shared, authorized ``rede``.

    The location is what keeps the region: ``save_project`` re-derives it on every write.
    """
    record = await make_shema_project(
        db_session,
        project_id=PROJECT_ID,
        region_key=ShemaRegionKey.SOUTH_AMERICA,
        language_name="Guarani Mbyá",
    )
    record.location = "Brazil"
    record.prayer_requests = WITHDRAWN
    record.prayer_visibility = ShemaPrayerVisibility.REDE
    await db_session.commit()
    return record


async def _pulse(client, headers, **answers) -> tuple[str, dict]:
    """One Pulse through the leader's link; answers the token and the body it sent."""
    link = await client.post(LINKS, json={"projectId": PROJECT_ID}, headers=headers)
    assert link.status_code == 201, link.text
    token = link.json()["token"]
    body = {
        "definitionVersion": link.json()["definitionVersion"],
        "answers": {"submittedBy": "Kuaray", "period": "2026-09", **answers},
    }
    response = await client.post(f"{PREFIX}/intake/{token}", json=body)
    assert response.status_code == 202, response.text
    return token, body


async def _by_request(db_session) -> list[ShemaSubmission]:
    """Every archived Pulse, read again from the database rather than from the identity map."""
    stmt = select(ShemaSubmission).execution_options(populate_existing=True)
    return list((await db_session.execute(stmt)).scalars().all())


async def _withdraw(client, headers, version: int = 1):
    response = await client.patch(
        f"{PROJECTS}/{PROJECT_ID}",
        json={"prayerVisibility": "coordenacao"},
        headers={**headers, "If-Match": f'"{version}"'},
    )
    assert response.status_code == 200, response.text
    return response


async def test_withdrawing_removes_the_request_only_from_the_pulses_with_the_same_text(
    client, db_session, shema_app, headers, coordinator, project
) -> None:
    """Two Pulses shared the request in the words on the record — one of them with a stray space
    and line break at the ends — and both lose it, with the authorization it gave. The Pulse that
    shared an earlier wording keeps it as the record of that version, and the Pulse that kept its
    request in coordination never shared anything; both are left as they arrived."""
    await _pulse(client, headers, prayerRequest=WITHDRAWN, prayerVisibility="rede")
    await _pulse(client, headers, prayerRequest=f"  {WITHDRAWN}\n", prayerVisibility="rede")
    await _pulse(client, headers, prayerRequest=EARLIER, prayerVisibility="rede")
    await _pulse(client, headers, prayerRequest=KEPT, prayerVisibility="coordenacao")

    await _withdraw(client, headers)

    rows = await _by_request(db_session)
    erased = [row for row in rows if row.prayer_request_erased_at is not None]
    kept = {
        archived_answers(row)["prayerRequest"]: row
        for row in rows
        if row.prayer_request_erased_at is None
    }
    assert len(erased) == 2
    for row in erased:
        assert WITHDRAWN not in row.archived_payload
        assert "prayerRequest" not in archived_answers(row)
        assert "prayerVisibility" not in archived_answers(row)
        assert archived_answers(row)["submittedBy"] == "Kuaray"

    assert set(kept) == {EARLIER, KEPT}
    assert archived_answers(kept[EARLIER])["prayerVisibility"] == "rede"
    assert archived_answers(kept[KEPT])["prayerVisibility"] == "coordenacao"
    assert all(row.prayer_request_erased_by is None for row in kept.values())


async def test_the_wall_still_loses_the_request_on_withdrawal(
    client, db_session, shema_app, headers, project
) -> None:
    """Narrowing the archive's erasure narrows nothing on the wall: the request leaves it with
    the withdrawal, although a Pulse with an earlier wording is still on file."""
    await _pulse(client, headers, prayerRequest=EARLIER, prayerVisibility="rede")
    before = await client.get(WALL, headers=headers)
    assert before.status_code == 200, before.text
    assert WITHDRAWN in before.text

    await _withdraw(client, headers)

    after = await client.get(WALL, headers=headers)
    assert after.status_code == 200, after.text
    assert WITHDRAWN not in after.text
    (row,) = await _by_request(db_session)
    assert archived_answers(row)["prayerRequest"] == EARLIER


async def test_the_removal_records_who_and_when_and_never_the_text(
    client, db_session, shema_app, headers, coordinator, project
) -> None:
    """The trace is two columns on the row; a log of what was erased would be the copy the
    erasure removes."""
    await _pulse(client, headers, prayerRequest=WITHDRAWN, prayerVisibility="rede")

    await _withdraw(client, headers)

    (row,) = await _by_request(db_session)
    assert row.prayer_request_erased_by == coordinator.id
    assert row.prayer_request_erased_at is not None
    columns = {column.key: getattr(row, column.key) for column in ShemaSubmission.__table__.c}
    assert not any(WITHDRAWN in str(value) for value in columns.values())


async def test_no_read_of_a_submission_returns_a_withdrawn_request(
    client, db_session, shema_app, headers, project
) -> None:
    """The inbox, the opened Pulse and the export — the three reads the DoD names — after the
    withdrawal, for the coordination that reads everything else in them."""
    await _pulse(client, headers, prayerRequest=WITHDRAWN, prayerVisibility="rede")
    await _withdraw(client, headers)
    (row,) = await _by_request(db_session)

    inbox = await client.get(SUBMISSIONS, headers=headers)
    opened = await client.get(f"{SUBMISSIONS}/{row.id}", headers=headers)
    export = await client.get(EXPORT, params={"format": "json"}, headers=headers)

    for response in (inbox, opened, export):
        assert response.status_code == 200, response.text
        assert WITHDRAWN not in response.text
    assert opened.json()["answers"]["submittedBy"] == "Kuaray"


async def test_the_same_file_sent_again_does_not_bring_the_request_back(
    client, db_session, shema_app, headers, project
) -> None:
    """The hash stays the hash of the bytes as they arrived, so a leader forwarding the same
    Pulse again is still the same submission and still a no-op — not a fresh archive of it."""
    token, body = await _pulse(client, headers, prayerRequest=WITHDRAWN, prayerVisibility="rede")
    await _withdraw(client, headers)

    again = await client.post(f"{PREFIX}/intake/{token}", json=body)

    assert again.status_code == 202, again.text
    rows = await _by_request(db_session)
    assert len(rows) == 1
    assert WITHDRAWN not in rows[0].archived_payload


async def test_a_pending_pulse_whose_request_was_removed_authorizes_nothing_when_applied(
    client, db_session, shema_app, headers, project
) -> None:
    """The Pulse said ``rede`` for the text the team took back. Applied later, it must not put
    that text back on the wall — and it must not empty the record's request either."""
    await _pulse(client, headers, prayerRequest=WITHDRAWN, prayerVisibility="rede")
    await _withdraw(client, headers)
    (row,) = await _by_request(db_session)

    applied = await client.post(
        f"{SUBMISSIONS}/{row.id}/import", headers={**headers, "If-Match": '"2"'}
    )

    assert applied.status_code == 200, applied.text
    await db_session.refresh(project)
    assert project.prayer_visibility is ShemaPrayerVisibility.COORDENACAO
    assert project.prayer_requests == WITHDRAWN


async def test_a_new_request_that_replaces_the_old_one_is_not_a_withdrawal(
    client, db_session, shema_app, headers, project
) -> None:
    """A rewrite clears the authorization for the new text (BE-09) but takes nothing back: the
    Pulse that carried the old one is coordination's record of what the team said."""
    await _pulse(client, headers, prayerRequest=WITHDRAWN, prayerVisibility="rede")

    response = await client.patch(
        f"{PROJECTS}/{PROJECT_ID}",
        json={"prayerRequests": "um pedido novo"},
        headers={**headers, "If-Match": '"1"'},
    )

    assert response.status_code == 200, response.text
    (row,) = await _by_request(db_session)
    assert archived_answers(row)["prayerRequest"] == WITHDRAWN
    assert row.prayer_request_erased_at is None


async def test_restating_rede_takes_nothing_back(
    client, db_session, shema_app, headers, project
) -> None:
    """The positive half of the gate: the console's consent control sends the visibility on
    every save, and ``rede`` over ``rede`` is not a withdrawal."""
    await _pulse(client, headers, prayerRequest=WITHDRAWN, prayerVisibility="rede")

    response = await client.patch(
        f"{PROJECTS}/{PROJECT_ID}",
        json={"prayerVisibility": "rede", "translators": "Equipe A"},
        headers={**headers, "If-Match": '"1"'},
    )

    assert response.status_code == 200, response.text
    (row,) = await _by_request(db_session)
    assert archived_answers(row)["prayerRequest"] == WITHDRAWN


async def test_a_health_reading_that_takes_the_authorization_back_removes_it_too(
    client, db_session, shema_app, headers, project
) -> None:
    """The assessment wizard is the other write that carries the request and its visibility,
    so it withdraws the same way a save does."""
    await _pulse(client, headers, prayerRequest=WITHDRAWN, prayerVisibility="rede")
    mentor = await make_scoped_user(
        db_session,
        shema_app,
        email="mentoria@shema.test",
        role_key="obtLab",
        regions=[ShemaRegionKey.SOUTH_AMERICA],
    )

    response = await client.post(
        f"{PROJECTS}/{PROJECT_ID}/health-assessments",
        json={
            "date": "2026-09-10",
            "assessor": "Marina Alves",
            "emotional": "boa",
            "relational": "boa",
            "spiritual": "boa",
            "physical": "boa",
            "questionSetVersion": 1,
            "prayerRequests": WITHDRAWN,
            "prayerVisibility": "coordenacao",
        },
        headers=await auth_header(db_session, mentor),
    )

    assert response.status_code == 201, response.text
    (row,) = await _by_request(db_session)
    assert WITHDRAWN not in row.archived_payload
    assert row.prayer_request_erased_by == mentor.id


@pytest.mark.parametrize(
    ("sent", "withdraws"),
    [
        ({"prayer_visibility": ShemaPrayerVisibility.COORDENACAO}, True),
        ({"prayer_visibility": None}, True),
        ({"prayer_visibility": ShemaPrayerVisibility.COORDENACAO, "prayer_requests": "novo"}, True),
        ({"prayer_visibility": ShemaPrayerVisibility.REDE}, False),
        ({"prayer_visibility": "rede"}, False),
        ({"prayer_requests": "um pedido novo"}, False),
    ],
)
async def test_only_a_stated_visibility_other_than_rede_withdraws(project, sent, withdraws) -> None:
    """The gate reads the value, not its type: a raw ``"rede"`` is a restatement, and reading it
    as a withdrawal would erase. What a withdrawal names is the text that was on the wall, even
    when a new one arrives with it."""
    assert withdrawn_request(project, sent) == (WITHDRAWN if withdraws else None)


async def test_a_blank_request_withdraws_nothing_to_compare(project) -> None:
    """A request with nothing written in it is still governed by the gate, but no Pulse shared
    a blank, so the withdrawal has no text to erase."""
    project.prayer_requests = "  \n"

    sent = {"prayer_visibility": ShemaPrayerVisibility.COORDENACAO}

    assert withdrawn_request(project, sent) is None


@pytest.mark.parametrize(
    ("archived", "on_record", "same"),
    [
        (f"  {WITHDRAWN}\n\n", WITHDRAWN, True),
        ("orem pela\r\nfamilia", "orem pela\nfamilia", True),
        ("orem pela\rfamilia", "orem pela\nfamilia", True),
        ("orac\u0327a\u0303o pela familia", "ora\u00e7\u00e3o pela familia", True),
        (EARLIER, WITHDRAWN, False),
        ("Orem pela familia", "orem pela familia", False),
        ("orem pela família", "orem pela familia", False),
        ("orem  pela familia", "orem pela familia", False),
        ("orem pela\n\nfamilia", "orem pela\nfamilia", False),
    ],
)
def test_same_request_reads_the_text_as_its_reader_sees_it(archived, on_record, same) -> None:
    """*"Exatamente igual"* (Karina, 6/out/2026) forgives only what the reader cannot see — the
    ends, the kind of line break, a letter composed or decomposed — and counts everything else:
    a letter, a capital, an accent, a doubled space or blank line inside."""
    assert same_request(archived, on_record) is same
