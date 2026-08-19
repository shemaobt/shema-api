"""ENG-443 — POST /facilitator/devices/claim, at the boundary the Desk actually meets.

Two behaviours here pull in opposite directions on purpose, and both are load-bearing.

ENG-437 made wrong, spent and expired indistinguishable, because its caller was anyone at
all. This route's caller is an authenticated facilitator standing in a room with the team
watching, and the three refusals ask for three different actions — retype, go find the
device, make the tablet show a new code. So the three become distinguishable (Behaviour 4).

What does **not** become distinguishable is the team check. Claiming into a project the
caller does not facilitate answers byte for byte like an unknown code, or a facilitator
could map the whole installation by trying (Behaviour 5).
"""

import logging
from importlib import import_module

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.device import claim_code, claim_device_as_facilitator, create_device
from tests.baker import make_language, make_project, make_project_user_access, make_user

CLAIM_URL = "/api/facilitator/devices/claim"
DEVICE_SELF_URL = "/api/devices/me"
DEVICE_CREDENTIAL_HEADER = "X-Device-Credential"

# The package __init__ rebinds this name to the function, so the module itself has to
# be reached through the import machinery.
facilitator_claim = import_module("app.services.device.claim_device_as_facilitator")


@pytest.fixture()
async def client(db_session: AsyncSession):
    """Both routers this slice adds, running the real auth chain."""
    from fastapi import FastAPI

    from app.api.devices import devices_router
    from app.api.facilitator.devices import facilitator_devices_router
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    test_app = FastAPI()
    test_app.include_router(facilitator_devices_router, prefix="/api/facilitator/devices")
    test_app.include_router(devices_router, prefix="/api/devices")
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def auth_header(db: AsyncSession, user) -> dict[str, str]:
    from app.services.auth.issue_tokens import issue_tokens

    access, _refresh = await issue_tokens(db, user)
    return {"Authorization": f"Bearer {access}"}


async def a_facilitator(db: AsyncSession, *, email="facilitator@example.com"):
    """A user with access to one project. Returns (user, project, auth headers)."""
    user = await make_user(db, email=email)
    language = await make_language(db, name=f"Lang {email}", code=email[:3])
    project = await make_project(db, language.id, name=f"Team {email}")
    await make_project_user_access(db, project.id, user.id)
    return user, project, await auth_header(db, user)


async def claim(client, headers, *, code, project_id, label=None):
    body = {"code": code, "project_id": project_id}
    if label is not None:
        body["label"] = label
    return await client.post(CLAIM_URL, json=body, headers=headers)


# Behaviour 1 — a valid claim binds the device and answers once.


async def test_claim_with_a_live_code_binds_the_device_and_returns_a_credential(client, db_session):
    _user, project, headers = await a_facilitator(db_session)
    minted = await create_device(db_session)

    response = await claim(
        client, headers, code=minted.claim_code, project_id=project.id, label="back shelf"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["credential"]
    assert body["project_id"] == project.id
    assert body["label"] == "back shelf"


async def test_claim_stores_the_who_uses_it_label_verbatim(client, db_session):
    _user, project, headers = await a_facilitator(db_session)
    minted = await create_device(db_session)
    written_by_a_human = "  Ana's tablet (cracked screen) — 2nd row  "

    response = await claim(
        client, headers, code=minted.claim_code, project_id=project.id, label=written_by_a_human
    )

    assert response.status_code == 200
    assert response.json()["label"] == written_by_a_human


async def test_claim_without_a_label_succeeds_and_leaves_it_null(client, db_session):
    _user, project, headers = await a_facilitator(db_session)
    minted = await create_device(db_session)

    response = await claim(client, headers, code=minted.claim_code, project_id=project.id)

    assert response.status_code == 200
    assert response.json()["label"] is None


# Behaviour 2 — the credential is answered exactly once and never again.


async def test_the_device_read_path_never_answers_with_the_credential(client, db_session):
    _user, project, headers = await a_facilitator(db_session)
    minted = await create_device(db_session)
    credential = (
        await claim(client, headers, code=minted.claim_code, project_id=project.id)
    ).json()["credential"]

    seen_again = await client.get(DEVICE_SELF_URL, headers={DEVICE_CREDENTIAL_HEADER: credential})

    assert seen_again.status_code == 200
    assert credential not in seen_again.text


# Behaviour 3 — the credential is never stored in plaintext and never logged.


async def test_the_credential_is_never_written_to_the_devices_table_in_plaintext(
    client, db_session
):
    _user, project, headers = await a_facilitator(db_session)
    minted = await create_device(db_session)

    credential = (
        await claim(client, headers, code=minted.claim_code, project_id=project.id)
    ).json()["credential"]

    stored = (await db_session.execute(text("SELECT * FROM devices"))).all()
    assert credential not in str(stored)


async def test_the_credential_is_never_written_to_the_log(client, db_session, caplog):
    _user, project, headers = await a_facilitator(db_session)
    minted = await create_device(db_session)

    with caplog.at_level(logging.DEBUG):
        credential = (
            await claim(client, headers, code=minted.claim_code, project_id=project.id)
        ).json()["credential"]

    for record in caplog.records:
        assert credential not in record.getMessage()
        assert credential not in str(record.__dict__)


# Behaviour 4 — the three code refusals are told apart.
#
# The reversal of ENG-437, and only inside this route. Asserted on the body's machine
# readable code, not on the status: the issue is explicit that a shared HTTP status is
# not enough for the Desk to choose what to tell the facilitator.


async def test_an_unknown_code_and_a_spent_code_and_an_expired_code_give_three_reasons(
    client, db_session, monkeypatch
):
    _user, project, headers = await a_facilitator(db_session)

    unknown = await claim(client, headers, code="AAA-AAAA", project_id=project.id)

    spent_device = await create_device(db_session)
    await claim(client, headers, code=spent_device.claim_code, project_id=project.id)
    spent = await claim(client, headers, code=spent_device.claim_code, project_id=project.id)

    minted_at = claim_code.utcnow()
    monkeypatch.setattr(claim_code, "utcnow", lambda: minted_at)
    expired_device = await create_device(db_session)
    monkeypatch.setattr(claim_code, "utcnow", lambda: minted_at + claim_code.CLAIM_CODE_TTL * 2)
    expired = await claim(client, headers, code=expired_device.claim_code, project_id=project.id)
    monkeypatch.undo()

    reasons = [unknown.json()["code"], spent.json()["code"], expired.json()["code"]]
    assert len(set(reasons)) == 3, f"the Desk cannot tell the three apart: {reasons}"
    assert all(r for r in reasons)


# Behaviour 5 — the team check does not enumerate.
#
# The one place indistinguishability survives. Asserted as equality of two whole
# responses, because a test that only checked "both failed" would pass straight over the
# leak it exists to close.


async def test_claiming_into_a_team_the_caller_does_not_facilitate_answers_like_an_unknown_code(
    client, db_session
):
    _user, own_project, headers = await a_facilitator(db_session)
    _stranger, someone_elses_project, _their_headers = await a_facilitator(
        db_session, email="stranger@example.com"
    )
    minted = await create_device(db_session)

    # The two must fail for genuinely different reasons and still answer identically: a
    # live code aimed at a team that is not the caller's, against a code that does not
    # exist aimed at the team that is. Pointing both at the stranger's project would
    # compare two team-check refusals with each other and prove nothing.
    not_yours = await claim(
        client, headers, code=minted.claim_code, project_id=someone_elses_project.id
    )
    unknown_code = await claim(client, headers, code="AAA-AAAA", project_id=own_project.id)

    assert not_yours.status_code == unknown_code.status_code
    assert not_yours.json() == unknown_code.json()
    assert not_yours.content == unknown_code.content


async def test_claiming_into_a_project_that_does_not_exist_answers_like_an_unknown_code(
    client, db_session
):
    _user, project, headers = await a_facilitator(db_session)
    minted = await create_device(db_session)

    absent = await claim(
        client,
        headers,
        code=minted.claim_code,
        project_id="00000000-0000-0000-0000-000000000000",
    )
    unknown_code = await claim(client, headers, code="AAA-AAAA", project_id=project.id)

    assert absent.status_code == unknown_code.status_code
    assert absent.content == unknown_code.content


async def test_a_refused_team_check_does_not_spend_the_code(client, db_session):
    _user, own_project, headers = await a_facilitator(db_session)
    _stranger, someone_elses_project, _h = await a_facilitator(db_session, email="s@example.com")
    minted = await create_device(db_session)

    await claim(client, headers, code=minted.claim_code, project_id=someone_elses_project.id)
    afterwards = await claim(client, headers, code=minted.claim_code, project_id=own_project.id)

    assert afterwards.status_code == 200


# Behaviour 6 — an unauthenticated caller gets nothing.


async def test_an_unauthenticated_claim_is_refused_without_any_reason(client, db_session):
    _user, project, _headers = await a_facilitator(db_session)
    minted = await create_device(db_session)

    response = await client.post(
        CLAIM_URL, json={"code": minted.claim_code, "project_id": project.id}
    )

    assert response.status_code == 401
    assert "CLAIM_CODE" not in response.text


async def test_an_unauthenticated_claim_does_not_spend_the_code(client, db_session):
    _user, project, headers = await a_facilitator(db_session)
    minted = await create_device(db_session)

    await client.post(CLAIM_URL, json={"code": minted.claim_code, "project_id": project.id})
    afterwards = await claim(client, headers, code=minted.claim_code, project_id=project.id)

    assert afterwards.status_code == 200


# Behaviour 7 — the device learns its team without anyone touching it.


async def test_a_device_can_read_its_own_team_after_the_claim(client, db_session):
    _user, project, headers = await a_facilitator(db_session)
    minted = await create_device(db_session)

    credential = (
        await claim(client, headers, code=minted.claim_code, project_id=project.id)
    ).json()["credential"]
    seen = await client.get(DEVICE_SELF_URL, headers={DEVICE_CREDENTIAL_HEADER: credential})

    assert seen.status_code == 200
    assert seen.json()["project_id"] == project.id


async def test_a_device_that_was_never_claimed_cannot_read_anything(client, db_session):
    await create_device(db_session)

    seen = await client.get(DEVICE_SELF_URL, headers={DEVICE_CREDENTIAL_HEADER: "a" * 64})

    assert seen.status_code == 401


async def test_the_device_read_path_refuses_a_request_with_no_credential(client, db_session):
    # A claimed device has to exist for this to mean anything: the failure being guarded
    # against is a missing credential falling through to whichever device is at hand.
    _user, project, headers = await a_facilitator(db_session)
    minted = await create_device(db_session)
    await claim(client, headers, code=minted.claim_code, project_id=project.id)

    seen = await client.get(DEVICE_SELF_URL)

    assert seen.status_code == 401
    assert project.id not in seen.text


# Behaviour 8 — replay after success.


async def test_replaying_a_spent_code_is_refused_as_already_used_and_does_not_move_the_device(
    client, db_session
):
    _user, first_project, headers = await a_facilitator(db_session)
    _second_user, second_project, second_headers = await a_facilitator(
        db_session, email="second@example.com"
    )
    minted = await create_device(db_session)

    first = await claim(client, headers, code=minted.claim_code, project_id=first_project.id)
    credential = first.json()["credential"]

    replay = await claim(
        client, second_headers, code=minted.claim_code, project_id=second_project.id
    )

    assert replay.status_code != 200
    assert replay.json()["code"] != ""
    still = await client.get(DEVICE_SELF_URL, headers={DEVICE_CREDENTIAL_HEADER: credential})
    assert still.json()["project_id"] == first_project.id


# Spending the code and paying for it are one transaction.


async def test_a_failure_after_the_code_is_spent_leaves_the_device_claimable(
    db_session, monkeypatch
):
    """The device must not be stranded by a transient failure half way through.

    Spending the code and issuing the credential are two writes. If the first commits and
    the second does not, the row is left with ``claimed_at`` set and no credential — and
    from there it can never recover on its own. Claiming it again is refused as already
    used, and nothing else issues a credential, so the tablet is permanently unusable
    because a hash write failed once.

    This is asserted below the HTTP boundary because there is no way to fail half way
    through from outside it. The rollback stands in for what a real request does: get_db
    yields the session inside ``async with``, so a request that raises closes the session
    and discards whatever was not committed.
    """
    user, project, _headers = await a_facilitator(db_session)
    minted = await create_device(db_session)

    def _the_credential_write_fails() -> str:
        raise RuntimeError("minting the credential failed")

    monkeypatch.setattr(
        facilitator_claim, "generate_device_credential", _the_credential_write_fails
    )

    with pytest.raises(RuntimeError):
        await claim_device_as_facilitator(
            db_session, user=user, code=minted.claim_code, project_id=project.id
        )

    monkeypatch.undo()
    await db_session.rollback()
    # A new request loads its own objects; the rollback expired these ones.
    await db_session.refresh(user)
    await db_session.refresh(project)

    recovered = await claim_device_as_facilitator(
        db_session, user=user, code=minted.claim_code, project_id=project.id
    )

    assert recovered.device.project_id == project.id
    assert recovered.credential
