"""ENG-437 — a device, and the short-lived single-use code it displays at installation.

The boundary under test is the pair of service functions that mint and spend a code.
No HTTP route exists yet; ``POST /facilitator/devices/claim`` is ENG-443.
"""

import logging
from importlib import import_module

import pytest

from app.services.device import (
    InvalidClaimCodeError,
    claim_code,
    claim_device,
    create_device,
    get_device,
    set_device_label,
)
from tests.baker import make_language, make_project

# The package __init__ rebinds this name to the function, so the module has to be reached
# through the import machinery rather than by attribute.
claim_device_module = import_module("app.services.device.claim_device")

CLAIM_LOGGER = "app.services.device.claim_device"

# Glyph pairs that collide when a code is read aloud across a table and typed by the
# person hearing it. Spelled out here rather than imported, so the test asserts the
# property and not the implementation's alphabet.
CONFUSABLE_GLYPHS = set("0O1IlL5S2Z8B")


async def a_project(db, *, name="Test Project"):
    language = await make_language(db, name=f"{name} Language", code=name[:3].lower())
    return await make_project(db, language.id, name=name)


async def refusal_from_claiming(db, *, code_value, project_id):
    """The exception a refused claim raises, so tests can compare refusals as values."""
    try:
        await claim_device(db, code=code_value, project_id=project_id)
    except InvalidClaimCodeError as exc:
        return exc
    raise AssertionError("the claim was expected to fail and did not")


async def three_refusals(db, monkeypatch):
    """One wrong code, one already spent, one expired — in that order."""
    project = await a_project(db)

    wrong = await refusal_from_claiming(db, code_value="AAA-AAAA", project_id=project.id)

    spent_device = await create_device(db)
    await claim_device(db, code=spent_device.claim_code, project_id=project.id)
    spent = await refusal_from_claiming(
        db, code_value=spent_device.claim_code, project_id=project.id
    )

    minted_at = claim_code.utcnow()
    monkeypatch.setattr(claim_code, "utcnow", lambda: minted_at)
    expired_device = await create_device(db)
    monkeypatch.setattr(claim_code, "utcnow", lambda: minted_at + claim_code.CLAIM_CODE_TTL * 2)
    expired = await refusal_from_claiming(
        db, code_value=expired_device.claim_code, project_id=project.id
    )
    monkeypatch.undo()

    return wrong, spent, expired


# Behaviour 1 — a device exists before it belongs to anyone.


async def test_create_device_before_any_claim_gives_a_code_and_no_project(db_session):
    minted = await create_device(db_session)

    assert minted.claim_code
    assert minted.device.project_id is None


async def test_get_device_for_an_unclaimed_device_returns_it_with_no_project(db_session):
    minted = await create_device(db_session)

    found = await get_device(db_session, minted.device.id)

    assert found is not None
    assert found.project_id is None


# Behaviour 2 — a code works once.


async def test_claim_device_with_a_fresh_code_puts_the_device_in_the_project(db_session):
    project = await a_project(db_session)
    minted = await create_device(db_session)

    claimed = await claim_device(db_session, code=minted.claim_code, project_id=project.id)

    assert claimed.project_id == project.id


async def test_claim_device_with_an_already_spent_code_is_refused_and_keeps_the_first_project(
    db_session,
):
    first = await a_project(db_session, name="First")
    second = await a_project(db_session, name="Second")
    minted = await create_device(db_session)
    await claim_device(db_session, code=minted.claim_code, project_id=first.id)

    with pytest.raises(InvalidClaimCodeError):
        await claim_device(db_session, code=minted.claim_code, project_id=second.id)

    still = await get_device(db_session, minted.device.id)
    assert still is not None
    assert still.project_id == first.id


async def test_claim_device_when_the_code_is_spent_between_the_check_and_the_write_is_refused(
    db_session, monkeypatch
):
    """The race the sequential replay test cannot reach.

    Two claims of one code both read the row, both see ``claimed_at`` null, and both go on
    to write. Whoever commits last would take the device, and both callers would be told
    they succeeded.

    The interleaving is forced rather than raced, so the test is deterministic: a
    competing claim is run from inside the last step before the write. A lock would not be
    provable here at all — the suite is SQLite and ``SELECT ... FOR UPDATE`` is a no-op
    there — which is why the write carries its own ``WHERE claimed_at IS NULL`` guard.
    """
    winner = await a_project(db_session, name="Winner")
    loser = await a_project(db_session, name="Loser")
    minted = await create_device(db_session)

    async def claim_it_first(db, project_id):
        monkeypatch.undo()
        await claim_device(db, code=minted.claim_code, project_id=winner.id)
        return True

    monkeypatch.setattr(claim_device_module, "_project_exists", claim_it_first)

    with pytest.raises(InvalidClaimCodeError):
        await claim_device(db_session, code=minted.claim_code, project_id=loser.id)

    settled = await get_device(db_session, minted.device.id)
    assert settled is not None
    assert settled.project_id == winner.id


# Behaviour 3 — a code stops working.


async def test_claim_device_with_a_code_past_its_life_is_refused_and_leaves_it_unclaimed(
    db_session, monkeypatch
):
    project = await a_project(db_session)
    minted_at = claim_code.utcnow()
    monkeypatch.setattr(claim_code, "utcnow", lambda: minted_at)
    minted = await create_device(db_session)

    past_its_life = minted_at + claim_code.CLAIM_CODE_TTL + claim_code.CLAIM_CODE_TTL
    monkeypatch.setattr(claim_code, "utcnow", lambda: past_its_life)

    with pytest.raises(InvalidClaimCodeError):
        await claim_device(db_session, code=minted.claim_code, project_id=project.id)

    unclaimed = await get_device(db_session, minted.device.id)
    assert unclaimed is not None
    assert unclaimed.project_id is None


async def test_claim_device_with_a_code_inside_its_life_puts_the_device_in_the_project(
    db_session, monkeypatch
):
    project = await a_project(db_session)
    minted_at = claim_code.utcnow()
    monkeypatch.setattr(claim_code, "utcnow", lambda: minted_at)
    minted = await create_device(db_session)

    monkeypatch.setattr(claim_code, "utcnow", lambda: minted_at + claim_code.CLAIM_CODE_TTL / 2)

    claimed = await claim_device(db_session, code=minted.claim_code, project_id=project.id)

    assert claimed.project_id == project.id


# Behaviour 4 — the caller cannot tell the failures apart, and the log can.
#
# The security behaviour of the slice. A caller who can tell wrong from spent can
# enumerate live codes; an operator who cannot tell them apart cannot debug a failed
# installation. Both halves are asserted, because a test that only checked "it fails"
# would pass over the enumeration oracle this exists to close.


async def test_claim_device_refusals_are_one_value_to_the_caller(db_session, monkeypatch):
    wrong, spent, expired = await three_refusals(db_session, monkeypatch)

    assert type(wrong) is type(spent) is type(expired)
    assert str(wrong) == str(spent) == str(expired)
    assert wrong.args == spent.args == expired.args


async def test_claim_device_with_an_unknown_project_is_refused_like_an_unknown_code(
    db_session, monkeypatch
):
    wrong, _, _ = await three_refusals(db_session, monkeypatch)
    minted = await create_device(db_session)

    unknown_project = await refusal_from_claiming(
        db_session,
        code_value=minted.claim_code,
        project_id="00000000-0000-0000-0000-000000000000",
    )

    assert type(unknown_project) is type(wrong)
    assert str(unknown_project) == str(wrong)
    assert unknown_project.args == wrong.args


async def test_claim_device_refusals_are_told_apart_in_the_log(db_session, monkeypatch, caplog):
    with caplog.at_level(logging.WARNING, logger=CLAIM_LOGGER):
        await three_refusals(db_session, monkeypatch)

    records = [r for r in caplog.records if r.name == CLAIM_LOGGER]
    assert len(records) == 3

    reasons = [getattr(r, "reason", None) for r in records]
    assert all(reasons), "every rejected claim must log why it was rejected"
    assert len(set(reasons)) == 3, f"the log cannot tell the three apart: {reasons}"


async def test_claim_device_never_writes_the_code_itself_to_the_log(db_session, caplog):
    with caplog.at_level(logging.WARNING, logger=CLAIM_LOGGER):
        minted = await create_device(db_session)
        project = await a_project(db_session)
        await claim_device(db_session, code=minted.claim_code, project_id=project.id)
        await refusal_from_claiming(db_session, code_value=minted.claim_code, project_id=project.id)

    for record in caplog.records:
        assert minted.claim_code not in record.getMessage()
        assert minted.claim_code not in str(getattr(record, "__dict__", {}))


# Behaviour 5 — two unspent codes are never the same.


async def test_create_device_over_many_mints_never_repeats_a_code(db_session):
    codes = [(await create_device(db_session)).claim_code for _ in range(300)]

    assert len(set(codes)) == len(codes)


async def test_create_device_on_a_code_collision_redraws_and_keeps_the_first_device(
    db_session, monkeypatch
):
    project = await a_project(db_session)
    drawn = iter(["KKK-MMMM", "KKK-MMMM", "PPP-QQQQ"])
    monkeypatch.setattr(claim_code, "generate_claim_code", lambda: next(drawn))

    first = await create_device(db_session)
    second = await create_device(db_session)
    monkeypatch.undo()

    assert first.claim_code != second.claim_code
    assert first.device.id != second.device.id

    claimed = await claim_device(db_session, code=first.claim_code, project_id=project.id)
    assert claimed.id == first.device.id


# Behaviour 6 — a code survives being read aloud across a table.


async def test_generate_claim_code_never_contains_a_glyph_that_collides_when_spoken():
    codes = [claim_code.generate_claim_code() for _ in range(500)]

    offenders = {c for c in codes if set(c) & CONFUSABLE_GLYPHS}
    assert not offenders, f"codes carry glyphs that collide when read aloud: {offenders}"


async def test_generate_claim_code_keeps_the_shape_a_facilitator_reads_out():
    for _ in range(50):
        code = claim_code.generate_claim_code()
        head, _, tail = code.partition("-")
        assert len(head) == 3
        assert len(tail) == 4
        assert code == f"{head}-{tail}"


# Behaviour 7 — the who-uses-it label authenticates nothing.


async def test_create_device_without_a_label_leaves_it_null(db_session):
    minted = await create_device(db_session)

    assert minted.device.label is None


async def test_claim_device_treats_a_labelled_and_an_unlabelled_device_identically(db_session):
    labelled_project = await a_project(db_session, name="Labelled")
    bare_project = await a_project(db_session, name="Bare")
    labelled = await create_device(db_session, label="the one by the window")
    bare = await create_device(db_session)

    claimed_labelled = await claim_device(
        db_session, code=labelled.claim_code, project_id=labelled_project.id
    )
    claimed_bare = await claim_device(db_session, code=bare.claim_code, project_id=bare_project.id)

    assert claimed_labelled.project_id == labelled_project.id
    assert claimed_bare.project_id == bare_project.id
    assert claimed_labelled.label == "the one by the window"
    assert claimed_bare.label is None


async def test_set_device_label_after_creation_replaces_the_label(db_session):
    minted = await create_device(db_session)

    await set_device_label(db_session, minted.device.id, "back shelf, cracked case")
    relabelled = await set_device_label(db_session, minted.device.id, "front desk")

    assert relabelled.label == "front desk"


async def test_set_device_label_to_none_clears_it(db_session):
    minted = await create_device(db_session, label="front desk")

    cleared = await set_device_label(db_session, minted.device.id, None)

    assert cleared.label is None
