"""``directory`` for somebody already in the network, found by their contact — OBT-681.

The DoD's first line: *whoever adds people to the network records the* ``directory`` *consent of
somebody already registered, with the day and a record of who did it*. A person who withheld it is
on no screen, so the console never holds their id; the coordination types the contact they were
asked through. Every test is one of the rules that makes that safe: a contact is the same contact
in any case or punctuation and never a guess; only a member of the network is found; a contact two
members share lists neither; somebody already listed is answered and not restamped; and a miss
names nobody and logs who asked.

Who may do it is ``network_routes`` in ``conftest.py``: the route is one of the network's writes,
so the Resource Circle's and the OBT Lab's refusals are asserted there, never with an admin.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from sqlalchemy import select

from app.db.models.shema_change_log import ShemaChangeLog
from app.db.models.shema_consent import ShemaIntercessorConsent
from app.db.models.shema_enums import ShemaRegionKey
from app.db.models.shema_intercessor import ShemaIntercessor
from app.services.shema._directory import NOBODY_AT_CONTACT
from app.utils.shema_contacts import contact_key
from app.utils.stored_time import as_utc
from tests.test_shema.conftest import (
    PEOPLE,
    PREFIX,
    as_role,
    auth_header,
    make_intercessor,
    make_scoped_user,
)

BY_CONTACT = f"{PEOPLE}/consents/directory"
AUDIT = f"{PREFIX}/audit"
BASIS = "said yes on WhatsApp, 30 October"


def _today() -> str:
    return datetime.now(UTC).date().isoformat()


async def _listing(client, headers) -> dict:
    return (await client.get(PEOPLE, headers=headers)).json()


async def _consent_marks(db_session, person_id: str) -> list[ShemaChangeLog]:
    stmt = select(ShemaChangeLog).where(
        ShemaChangeLog.subject_id == person_id, ShemaChangeLog.action == "consent-recorded"
    )
    rows = await db_session.execute(stmt.execution_options(populate_existing=True))
    return list(rows.scalars())


async def test_the_coordination_lists_a_withheld_member_found_by_their_contact(
    db_session, client, shema_app
) -> None:
    """The person withheld ``directory`` at the create and consents later: typed in another case,
    their e-mail finds them, and they are listed with the basis the coordinator gave."""
    _user, headers = await as_role(db_session, shema_app, "coordinator")
    person = await make_intercessor(client, headers, contact="Maria.Santos@Example.org")
    assert (await _listing(client, headers))["withheldCount"] == 1

    res = await client.post(
        BY_CONTACT, headers=headers, json={"contact": "maria.santos@example.org", "basis": BASIS}
    )

    assert res.status_code == 201, res.text
    assert res.json()["id"] == person["id"]
    consents = {row["context"]: row for row in res.json()["consents"]}
    assert sorted(consents) == ["directory", "network"]
    assert consents["directory"]["basis"] == BASIS
    listing = await _listing(client, headers)
    assert [entry["id"] for entry in listing["people"]] == [person["id"]]
    assert listing["withheldCount"] == 0


async def test_the_directory_consent_is_recorded_with_its_day_and_its_author(
    db_session, client, shema_app
) -> None:
    """**The DoD's "com a data e o registro de quem o fez"**, as the create records it: the row
    carries the account and the day, the change log the act signed by that account, and the
    coordination's audit feed reads it."""
    coordinator = await make_scoped_user(
        db_session,
        shema_app,
        email="carla@coord.test",
        role_key="coordinator",
        regions=[ShemaRegionKey.AFRICA],
    )
    coordinator.display_name = "Carla Coordenadora"
    await db_session.commit()
    headers = await auth_header(db_session, coordinator)
    person = await make_intercessor(client, headers)

    res = await client.post(
        BY_CONTACT, headers=headers, json={"contact": "maria.santos@example.org", "basis": BASIS}
    )
    assert res.status_code == 201, res.text

    row = (
        await db_session.execute(
            select(ShemaIntercessorConsent)
            .where(
                ShemaIntercessorConsent.intercessor_id == person["id"],
                ShemaIntercessorConsent.context == "directory",
            )
            .execution_options(populate_existing=True)
        )
    ).scalar_one()
    assert row.recorded_by == coordinator.id
    assert as_utc(row.recorded_at).date().isoformat() == _today()
    [mark] = await _consent_marks(db_session, person["id"])
    assert (mark.actor_id, json.loads(mark.field_keys or "[]")) == (coordinator.id, ["directory"])
    feed = (await client.get(AUDIT, headers=headers)).json()
    [entry] = [
        e for e in feed if e["subjectId"] == person["id"] and e["action"] == "consent-recorded"
    ]
    assert entry["changedBy"] == "Carla Coordenadora"
    assert entry["changedAt"].startswith(_today())


async def test_a_phone_is_the_same_phone_when_its_digits_are(db_session, client, shema_app) -> None:
    """Punctuation and the no-break space a pasted WhatsApp number carries do not matter; a missing
    country code does, because guessing one is how the wrong person gets listed."""
    _user, headers = await as_role(db_session, shema_app, "coordinator")
    pasted = await make_intercessor(
        client, headers, name="Ana Colada", contact="+55 (11)\N{NO-BREAK SPACE}98765-4321"
    )
    local = await make_intercessor(client, headers, name="Bia Local", contact="+55 21 91234-5678")

    found = await client.post(
        BY_CONTACT, headers=headers, json={"contact": "5511987654321", "basis": BASIS}
    )
    guessed = await client.post(
        BY_CONTACT, headers=headers, json={"contact": "21 91234-5678", "basis": BASIS}
    )

    assert (found.status_code, found.json()["id"]) == (201, pasted["id"])
    assert guessed.status_code == 404
    listing = await _listing(client, headers)
    assert [entry["id"] for entry in listing["people"]] == [pasted["id"]]
    assert local["id"] not in guessed.text
    assert listing["withheldCount"] == 1


async def test_someone_already_listed_is_answered_and_not_restamped(
    db_session, client, shema_app
) -> None:
    """Asked twice is answered — a retry, or a coordinator who did not see the row — and the
    basis and day the person gave stay the evidence: nothing is written, not even a mark."""
    _user, headers = await as_role(db_session, shema_app, "coordinator")
    person = await make_intercessor(client, headers, listed=True)
    before = (await _listing(client, headers))["people"][0]["consents"]
    marks = len(await _consent_marks(db_session, person["id"]))

    res = await client.post(
        BY_CONTACT, headers=headers, json={"contact": "maria.santos@example.org", "basis": BASIS}
    )

    assert res.status_code == 200, res.text
    assert res.json()["consents"] == before
    assert {c["context"]: c["basis"] for c in before}["directory"] == "yes"
    assert len(await _consent_marks(db_session, person["id"])) == marks


async def test_a_contact_no_member_has_lists_nobody(db_session, client, shema_app) -> None:
    """An unknown contact and a row imported with no consent at all get the same sentence. The
    second matters: the list shows any ``directory`` row, so a lookup that ignored the floor would
    put on a screen somebody who never agreed even to be reached."""
    _user, headers = await as_role(db_session, shema_app, "coordinator")
    member = await make_intercessor(client, headers)
    imported = ShemaIntercessor(name="Cid Importado", country="BR", contact="cid@example.org")
    db_session.add(imported)
    await db_session.commit()

    unknown = await client.post(
        BY_CONTACT, headers=headers, json={"contact": "ninguem@example.org", "basis": BASIS}
    )
    floorless = await client.post(
        BY_CONTACT, headers=headers, json={"contact": "cid@example.org", "basis": BASIS}
    )

    assert (unknown.status_code, floorless.status_code) == (404, 404)
    assert unknown.json()["detail"] == floorless.json()["detail"] == NOBODY_AT_CONTACT
    consents = await db_session.execute(
        select(ShemaIntercessorConsent).where(ShemaIntercessorConsent.intercessor_id == imported.id)
    )
    assert consents.scalars().all() == []
    listing = await _listing(client, headers)
    assert (listing["people"], listing["withheldCount"]) == ([], 1)
    assert await _consent_marks(db_session, imported.id) == []
    assert await _consent_marks(db_session, member["id"]) == []


async def test_two_members_at_one_contact_are_listed_by_neither(
    db_session, client, shema_app
) -> None:
    """A family's shared phone is ordinary in the field. The consent is one person's and the
    contact cannot say whose, so nobody is listed and the refusal names neither."""
    _user, headers = await as_role(db_session, shema_app, "coordinator")
    await make_intercessor(client, headers, name="Rute Família", contact="+55 11 90000-1234")
    await make_intercessor(client, headers, name="Noemi Família", contact="+55 11 90000-1234")

    res = await client.post(
        BY_CONTACT, headers=headers, json={"contact": "+5511900001234", "basis": BASIS}
    )

    assert res.status_code == 409
    assert "Família" not in res.text
    listing = await _listing(client, headers)
    assert (listing["people"], listing["withheldCount"]) == ([], 2)


async def test_a_miss_names_nobody_and_logs_who_asked(
    db_session, client, shema_app, caplog
) -> None:
    """A hit is a signed write; a miss leaves a line with the account that asked, so asking
    whether a contact is held is never silent — and neither the line nor the answer carries the
    contact or anybody's name."""
    user, headers = await as_role(db_session, shema_app, "coordinator")
    await make_intercessor(client, headers, name="Canário Oculto", contact="canario@example.org")
    caplog.set_level(logging.INFO, logger="app.services.shema.admit_to_directory")

    res = await client.post(
        BY_CONTACT, headers=headers, json={"contact": "canario@exemplo.org", "basis": BASIS}
    )

    assert res.status_code == 404
    assert "canario" not in res.text and "Canário" not in res.text
    [line] = [r for r in caplog.records if r.name == "app.services.shema.admit_to_directory"]
    assert line.shema_user_id == user.id
    assert "canario" not in line.getMessage() and "canario" not in str(vars(line))


async def test_a_blank_basis_or_an_unreachable_contact_is_a_bad_payload(
    db_session, client, shema_app
) -> None:
    """Refused by naming the field, before anybody is looked for — a blank basis would otherwise
    meet the CHECK inside the flush and come back as a 500."""
    _user, headers = await as_role(db_session, shema_app, "coordinator")
    await make_intercessor(client, headers)

    for body in (
        {"contact": "maria.santos@example.org", "basis": " \t "},
        {"contact": "ask at the church", "basis": BASIS},
        {"contact": "maria.santos@example.org", "basis": BASIS, "name": "Maria"},
        {"contact": "maria.santos@example.org"},
    ):
        res = await client.post(BY_CONTACT, headers=headers, json=body)
        assert res.status_code == 422, body

    listing = await _listing(client, headers)
    assert (listing["people"], listing["withheldCount"]) == ([], 1)


async def test_the_admin_role_lists_a_withheld_member_too(db_session, client, shema_app) -> None:
    """The create's guard is coordination and the Admin of OBT-522 — a granted role, not the
    installation's platform admin, who passes every guard and would prove nothing."""
    _user, headers = await as_role(db_session, shema_app, "admin")
    person = await make_intercessor(client, headers)

    res = await client.post(
        BY_CONTACT, headers=headers, json={"contact": "maria.santos@example.org", "basis": BASIS}
    )

    assert (res.status_code, res.json()["id"]) == (201, person["id"])


def test_two_spellings_of_one_contact_share_a_key() -> None:
    """The rule the lookup is, without a database: an e-mail in any case, a phone by its digits,
    and nothing for a string nobody is reached at."""
    assert contact_key(" Maria.Santos@Example.ORG ") == "maria.santos@example.org"
    assert contact_key("+55 (11) 98765-4321") == contact_key("5511987654321") == "5511987654321"
    assert contact_key("11 98765-4321") != contact_key("+55 11 98765-4321")
    assert contact_key("ask at the church") is None
