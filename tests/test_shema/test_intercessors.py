"""The network: consent per context, a contact that does not leave in bulk, and erasure.

Every test here is a rule somebody wrote down about a real person, not a round trip through
SQLAlchemy. The five the file exists for: a contact cannot be stored without a recorded basis;
consenting to be listed is not consenting to be exported; the collection has no contact string
in it; withdrawing the floor consent deletes the person; and the read is narrower than
authentication.
"""

from __future__ import annotations

from sqlalchemy import event

from tests.baker import make_user
from tests.test_shema.conftest import PEOPLE, auth_header, make_intercessor, make_scoped_user


async def _circle(db_session, shema_app, *, email: str = "circle@shema.test"):
    user = await make_scoped_user(
        db_session, shema_app, email=email, role_key="resourceCircle", regions=[]
    )
    return user, await auth_header(db_session, user)


# --- consent, per context ---------------------------------------------------------------


async def test_a_person_cannot_be_stored_without_a_recorded_basis(
    db_session, client, shema_app
) -> None:
    """``docs/shema.md`` §10 item 8's first question, answered by making the alternative
    unrepresentable rather than by a rule a service has to follow."""
    _user, headers = await _circle(db_session, shema_app)

    res = await client.post(
        PEOPLE,
        headers=headers,
        json={"name": "Maria", "country": "BR", "contact": "maria@example.org"},
    )

    assert res.status_code == 422
    assert (await client.get(PEOPLE, headers=headers)).json()["people"] == []


async def test_a_basis_of_whitespace_is_a_bad_payload_and_not_a_server_fault(
    db_session, client, shema_app
) -> None:
    """``min_length`` counts characters and does not strip: ``"   "`` used to pass the
    validator, be stripped by the service and meet the CHECK constraint inside the flush —
    a 500 for the caller's own bad payload. Both places a basis enters are asserted, and each
    refusal is re-read rather than taken on the status code: the directory still withholds the
    person, which is how this file spells *no* ``directory`` *consent stands*. The create
    response would say so whatever the ``PUT`` wrote, so it is not what is asked."""
    _user, headers = await _circle(db_session, shema_app)

    res = await client.post(
        PEOPLE,
        headers=headers,
        json={
            "name": "Maria",
            "country": "BR",
            "contact": "maria@example.org",
            "consentBasis": "   ",
        },
    )
    assert res.status_code == 422
    assert (await client.get(PEOPLE, headers=headers)).json()["people"] == []

    person = await make_intercessor(client, headers)
    res = await client.put(
        f"{PEOPLE}/{person['id']}/consents/directory", headers=headers, json={"basis": " \t "}
    )
    assert res.status_code == 422
    listing = (await client.get(PEOPLE, headers=headers)).json()
    assert listing["people"] == []
    assert listing["withheldCount"] == 1


async def test_the_create_grants_the_floor_consent_and_not_the_other_two(
    db_session, client, shema_app
) -> None:
    """A person is asked three separate questions and answering one is not answering the
    others. A create that quietly granted all three would be the single flag this design
    exists to refuse, wearing three names."""
    _user, headers = await _circle(db_session, shema_app)

    person = await make_intercessor(client, headers)

    assert [row["context"] for row in person["consents"]] == ["network"]
    assert person["consents"][0]["basis"] == "verbal, at the 2026 regional gathering"


async def test_consenting_to_the_directory_is_not_consenting_to_an_export(
    db_session, client, shema_app
) -> None:
    """**The DoD's second line, as the issue's own example.**

    Somebody who agreed to appear in an internal directory has not agreed to appear in a
    report shared with partners, and a store that cannot tell the two apart answers whichever
    question was asked first — with a yes.
    """
    from app.services.shema import leaving_directory

    _user, headers = await _circle(db_session, shema_app)
    person = await make_intercessor(client, headers)

    listed = await client.put(
        f"{PEOPLE}/{person['id']}/consents/directory",
        headers=headers,
        json={"basis": "asked on the call of 3 March, said yes to the internal list"},
    )

    assert listed.status_code == 200
    assert sorted(row["context"] for row in listed.json()["consents"]) == [
        "directory",
        "network",
    ]
    assert (await client.get(PEOPLE, headers=headers)).json()["withheldCount"] == 0
    assert await leaving_directory(db_session) == []


async def test_the_export_gate_is_the_query_and_the_shape_carries_no_contact(
    db_session, client, shema_app
) -> None:
    """What ``_directory.leaving_directory`` hands BE-12 and BE-14 on the day they need it.

    FE-44 §8.4's allowlist carries no personal contact at all, and an allowlist only holds
    while the thing it protects cannot be reached another way — so the leaving shape has no
    field for one.
    """
    from app.services.shema import leaving_directory

    _user, headers = await _circle(db_session, shema_app)
    person = await make_intercessor(client, headers)
    await client.put(
        f"{PEOPLE}/{person['id']}/consents/partner-export",
        headers=headers,
        json={"basis": "signed form on file, 2026-04-02"},
    )

    leaving = await leaving_directory(db_session)

    assert [row.name for row in leaving] == ["Maria Santos"]
    assert leaving[0]._fields == ("name", "country", "country_withheld")


async def test_withdrawing_a_narrow_consent_deletes_the_row_and_keeps_the_person(
    db_session, client, shema_app
) -> None:
    """Somebody who leaves the internal directory is still reachable — which is exactly the
    distinction a single flag cannot express. And the row is **deleted**, not flagged: FE-44
    §8.2's *never flagged and retained*, on a person."""
    _user, headers = await _circle(db_session, shema_app)
    person = await make_intercessor(client, headers)
    await client.put(
        f"{PEOPLE}/{person['id']}/consents/directory",
        headers=headers,
        json={"basis": "said yes on the call"},
    )

    res = await client.delete(f"{PEOPLE}/{person['id']}/consents/directory", headers=headers)

    assert res.status_code == 204
    contact = await client.get(f"{PEOPLE}/{person['id']}/contact", headers=headers)
    assert contact.status_code == 200
    listing = await client.get(PEOPLE, headers=headers)
    assert listing.json()["people"] == []
    assert listing.json()["withheldCount"] == 1


async def test_withdrawing_the_floor_consent_erases_the_person(
    db_session, client, shema_app
) -> None:
    """``network`` is the consent to being held at all, so withdrawing it removes the basis
    the row exists on — and a contact held with no basis is retained personal data."""
    _user, headers = await _circle(db_session, shema_app)
    person = await make_intercessor(client, headers)

    res = await client.delete(f"{PEOPLE}/{person['id']}/consents/network", headers=headers)

    assert res.status_code == 204
    assert res.content == b""
    assert (
        await client.get(f"{PEOPLE}/{person['id']}/contact", headers=headers)
    ).status_code == 404


async def test_withdrawing_from_somebody_who_is_not_there_is_a_404(
    db_session, client, shema_app
) -> None:
    """The subject is read before the delete, so an unknown id is a 404 naming what is
    missing and not a 204 about a row that was never there."""
    _user, headers = await _circle(db_session, shema_app)

    res = await client.delete(f"{PEOPLE}/nobody/consents/directory", headers=headers)

    assert res.status_code == 404


async def test_the_directory_is_read_in_the_same_number_of_statements_whatever_its_size(
    db_session, client, shema_app, test_engine
) -> None:
    """Per-person reads made the directory 2N+2 round trips, on the network screen that is
    the whole consumer of the route. The people come in one ``select`` and the consents in
    one more, so the statement count of the read is the same for one person and for six —
    measured, rather than asserted as a number that the auth chain would make brittle."""
    _user, headers = await _circle(db_session, shema_app)

    async def _listed(index: int) -> None:
        person = await make_intercessor(
            client, headers, name=f"Person {index}", contact=f"person{index}@example.org"
        )
        await client.put(
            f"{PEOPLE}/{person['id']}/consents/directory", headers=headers, json={"basis": "yes"}
        )

    async def _statements_of_a_read() -> int:
        statements: list[str] = []

        def _count(_conn, _cursor, statement, _parameters, _context, _executemany) -> None:
            statements.append(statement)

        event.listen(test_engine.sync_engine, "before_cursor_execute", _count)
        try:
            res = await client.get(PEOPLE, headers=headers)
        finally:
            event.remove(test_engine.sync_engine, "before_cursor_execute", _count)
        assert res.status_code == 200
        return len(statements)

    await _listed(0)
    with_one = await _statements_of_a_read()
    for index in range(1, 6):
        await _listed(index)

    assert len((await client.get(PEOPLE, headers=headers)).json()["people"]) == 6
    assert await _statements_of_a_read() == with_one


# --- the contact --------------------------------------------------------------------------


async def test_the_directory_carries_no_contact_string_anywhere_in_it(
    db_session, client, shema_app
) -> None:
    """**The DoD's last line**, asserted over the serialised body rather than over a field
    list, because the claim is about the response and not about one model's keys."""
    _user, headers = await _circle(db_session, shema_app)
    person = await make_intercessor(client, headers, contact="maria.santos@example.org")
    await client.put(
        f"{PEOPLE}/{person['id']}/consents/directory",
        headers=headers,
        json={"basis": "said yes"},
    )

    res = await client.get(PEOPLE, headers=headers)

    assert "maria.santos@example.org" not in res.text
    entry = res.json()["people"][0]
    assert "contact" not in entry
    assert entry["contactChannel"] == "email"
    assert entry["contactHint"] == "m•••@•••"


async def test_a_phone_hint_keeps_two_digits_and_the_domain_of_an_email_never_survives(
    db_session, client, shema_app
) -> None:
    """A hint separates two people with the same name and identifies nobody outside the list.
    The e-mail domain is often the employer, which is the identifying half."""
    _user, headers = await _circle(db_session, shema_app)
    person = await make_intercessor(client, headers, contact="+55 11 98765-4321")
    await client.put(
        f"{PEOPLE}/{person['id']}/consents/directory", headers=headers, json={"basis": "yes"}
    )

    entry = (await client.get(PEOPLE, headers=headers)).json()["people"][0]

    assert entry["contactChannel"] == "phone"
    assert entry["contactHint"] == "•••21"


async def test_the_real_contact_is_read_one_person_at_a_time(db_session, client, shema_app) -> None:
    """Its own route rather than a flag on the collection: a bulk read and a single read are
    different acts with different risk, and an option makes them look like one act."""
    _user, headers = await _circle(db_session, shema_app)
    person = await make_intercessor(client, headers)

    res = await client.get(f"{PEOPLE}/{person['id']}/contact", headers=headers)

    assert res.status_code == 200
    assert res.json() == {"id": person["id"], "contact": "maria.santos@example.org"}


# --- the record ----------------------------------------------------------------------------


async def test_a_record_with_no_usable_channel_is_refused_naming_the_field(
    db_session, client, shema_app
) -> None:
    """FE-44 §9.6: *the error must say which field is missing, because the screen names it.*"""
    _user, headers = await _circle(db_session, shema_app)

    res = await client.post(
        PEOPLE,
        headers=headers,
        json={
            "name": "Maria",
            "country": "BR",
            "contact": "ask around",
            "consentBasis": "verbal",
        },
    )

    assert res.status_code == 422
    assert any("contact" in str(item["loc"]) for item in res.json()["detail"])


async def test_an_unknown_country_is_refused_and_a_lowercase_one_is_accepted(
    db_session, client, shema_app
) -> None:
    """The code is what stops the network fragmenting into *Brasil* / *Brazil* / *BR*.
    Case is a typo worth accepting; prose is not."""
    _user, headers = await _circle(db_session, shema_app)

    refused = await client.post(
        PEOPLE,
        headers=headers,
        json={
            "name": "Maria",
            "country": "Brasil",
            "contact": "maria@example.org",
            "consentBasis": "verbal",
        },
    )
    assert refused.status_code == 422
    assert any("country" in str(item["loc"]) for item in refused.json()["detail"])

    person = await make_intercessor(client, headers, country="br")
    assert person["country"] == "BR"


async def test_an_edit_leaves_added_at_alone_and_does_not_unflag_by_omission(
    db_session, client, shema_app
) -> None:
    """FE-44 §9.6's *``addedAt`` survives an edit*, and the reason ``exclude_unset`` is not
    ``exclude_none``: a partial edit of a name must not silently unflag somebody."""
    _user, headers = await _circle(db_session, shema_app)
    person = await make_intercessor(client, headers, sensitive=True)

    res = await client.patch(
        f"{PEOPLE}/{person['id']}",
        headers=headers,
        json={"name": "Maria S. Santos"},
    )

    assert res.status_code == 200
    assert res.json()["name"] == "Maria S. Santos"
    assert res.json()["addedAt"] == person["addedAt"]
    assert res.json()["sensitiveCountry"] is True

    refused = await client.patch(
        f"{PEOPLE}/{person['id']}", headers=headers, json={"addedAt": "2020-01-01"}
    )
    assert refused.status_code == 422


async def test_erasing_a_person_takes_their_consents_with_them(
    db_session, client, shema_app
) -> None:
    """No tombstone, no ``removed`` flag, and no consent record outliving its subject.

    Asked of the database rather than of the endpoint, because *absent from storage* is the
    rule and *absent from the list* is what a soft delete also achieves.
    """
    from sqlalchemy import func, select

    from app.db.models.shema_consent import ShemaIntercessorConsent
    from app.db.models.shema_intercessor import ShemaIntercessor

    _user, headers = await _circle(db_session, shema_app)
    person = await make_intercessor(client, headers)

    res = await client.delete(f"{PEOPLE}/{person['id']}", headers=headers)

    assert res.status_code == 204
    people = await db_session.execute(select(func.count()).select_from(ShemaIntercessor))
    consents = await db_session.execute(select(func.count()).select_from(ShemaIntercessorConsent))
    assert people.scalar_one() == 0
    assert consents.scalar_one() == 0


# --- the sensitive country on a person -------------------------------------------------------


async def test_a_flagged_person_keeps_their_country_on_the_read_and_loses_it_on_the_way_out(
    db_session, client, shema_app
) -> None:
    """**The DoD's fifth line**, and it is ``docs/shema.md`` §6.4's split rather than a second
    rule: redact in the payload on every path that leaves, never on the record read.

    The Resource Circle member working the directory is the person who needs the real country;
    hiding it from them is data loss, not privacy. The withheld shape is FE-44 §9.6's own —
    ``country: ""`` with the marker beside it — so the redaction travels in the payload and a
    renderer downstream cannot leak what the payload does not hold.
    """
    from app.services.shema import leaving_directory

    _user, headers = await _circle(db_session, shema_app)
    person = await make_intercessor(client, headers, country="EG", sensitive=True)
    for context in ("directory", "partner-export"):
        await client.put(
            f"{PEOPLE}/{person['id']}/consents/{context}", headers=headers, json={"basis": "yes"}
        )

    listed = (await client.get(PEOPLE, headers=headers)).json()["people"][0]
    assert listed["country"] == "EG"
    assert listed["sensitiveCountry"] is True

    leaving = await leaving_directory(db_session)
    assert leaving[0].country == ""
    assert leaving[0].country_withheld is True


# --- who may reach it ------------------------------------------------------------------------


async def test_every_other_shema_role_is_refused_the_network(db_session, client, shema_app) -> None:
    """**The DoD's fourth line.** The network is the Resource Circle's instrument, and even
    ``globalStrategist`` is refused — a real consequence, and the escape is a second grant
    rather than a second guard. Not an admin account, or it would pass with the alias gone.
    """
    for role in ("coordinator", "obtLab", "globalStrategist"):
        user = await make_scoped_user(
            db_session, shema_app, email=f"{role}@net.test", role_key=role, regions=[]
        )
        res = await client.get(PEOPLE, headers=await auth_header(db_session, user))
        assert res.status_code == 403, role
        assert "resourceCircle" in res.json()["detail"]


async def test_an_account_with_no_shema_grant_reaches_nothing_of_the_network(
    db_session, client, shema_app
) -> None:
    """Deny by default, inherited from the module's router rather than declared per route."""
    outsider = await make_user(db_session, email="outsider@net.test")

    res = await client.get(PEOPLE, headers=await auth_header(db_session, outsider))

    assert res.status_code == 403


async def test_a_null_in_a_partial_edit_is_a_refusal_and_not_a_server_fault(
    db_session, client, shema_app
) -> None:
    """A bad request must not be answered as a server fault.

    ``country``, ``contact`` and ``name`` share their validators between the create and the
    partial edit, and only the edit can carry a ``null``. Without the guard the value reaches
    ``.strip()`` on ``None`` and the caller gets a 500 for a payload the server should have
    refused by naming the field.
    """
    _user, headers = await _circle(db_session, shema_app)
    person = await make_intercessor(client, headers)

    for field in ("name", "country", "contact"):
        res = await client.patch(f"{PEOPLE}/{person['id']}", headers=headers, json={field: None})
        assert res.status_code == 422, field
