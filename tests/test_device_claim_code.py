"""ENG-437 — a device, and the short-lived single-use code it displays at installation.

The boundary under test is the pair of service functions that mint and spend a code.
No HTTP route exists yet; ``POST /facilitator/devices/claim`` is ENG-443.
"""

import logging

import pytest

from app.core.exceptions import InvalidClaimCodeError
from app.services.device import (
    claim_code,
    claim_device,
    create_device,
    get_device,
    set_device_label,
)
from tests.baker import make_language, make_project

CLAIM_LOGGER = "app.services.device.claim_device"

# Glyph pairs that collide when a code is read aloud across a table and typed by the
# person hearing it. Spelled out here rather than imported, so the test asserts the
# property and not the implementation's alphabet.
CONFUSABLE_GLYPHS = set("0O1IlL5S2Z8B")


async def a_project(db, *, name="Test Project"):
    language = await make_language(db, name=f"{name} Language", code=name[:3].lower())
    return await make_project(db, language.id, name=name)


class TestBehaviour1DeviceExistsBeforeItBelongsToAnyone:
    async def test_a_new_device_has_a_code_and_no_project(self, db_session):
        minted = await create_device(db_session)

        assert minted.claim_code
        assert minted.device.project_id is None

    async def test_a_device_with_no_project_is_readable(self, db_session):
        minted = await create_device(db_session)

        found = await get_device(db_session, minted.device.id)

        assert found is not None
        assert found.project_id is None


class TestBehaviour2ACodeWorksOnce:
    async def test_claiming_puts_the_device_in_the_project(self, db_session):
        project = await a_project(db_session)
        minted = await create_device(db_session)

        claimed = await claim_device(db_session, code=minted.claim_code, project_id=project.id)

        assert claimed.project_id == project.id

    async def test_the_same_code_cannot_be_spent_twice(self, db_session):
        first = await a_project(db_session, name="First")
        second = await a_project(db_session, name="Second")
        minted = await create_device(db_session)
        await claim_device(db_session, code=minted.claim_code, project_id=first.id)

        with pytest.raises(InvalidClaimCodeError):
            await claim_device(db_session, code=minted.claim_code, project_id=second.id)

        still = await get_device(db_session, minted.device.id)
        assert still is not None
        assert still.project_id == first.id


class TestBehaviour3ACodeStopsWorking:
    async def test_a_code_past_its_life_does_not_claim(self, db_session, monkeypatch):
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

    async def test_a_code_inside_its_life_still_claims(self, db_session, monkeypatch):
        project = await a_project(db_session)
        minted_at = claim_code.utcnow()
        monkeypatch.setattr(claim_code, "utcnow", lambda: minted_at)
        minted = await create_device(db_session)

        monkeypatch.setattr(claim_code, "utcnow", lambda: minted_at + claim_code.CLAIM_CODE_TTL / 2)

        claimed = await claim_device(db_session, code=minted.claim_code, project_id=project.id)
        assert claimed.project_id == project.id


class TestBehaviour4TheCallerCannotTellTheFailuresApart:
    """The security behaviour of the slice.

    Wrong, spent and expired must be one answer to whoever is asking, and three answers
    in the log. A caller who can tell them apart can enumerate live codes; an operator
    who cannot tell them apart cannot debug a failed installation.
    """

    async def _three_failures(self, db_session, monkeypatch):
        project = await a_project(db_session)

        wrong = await self._capture(db_session, code_value="AAA-AAAA", project_id=project.id)

        spent_device = await create_device(db_session)
        await claim_device(db_session, code=spent_device.claim_code, project_id=project.id)
        spent = await self._capture(
            db_session, code_value=spent_device.claim_code, project_id=project.id
        )

        minted_at = claim_code.utcnow()
        monkeypatch.setattr(claim_code, "utcnow", lambda: minted_at)
        expired_device = await create_device(db_session)
        monkeypatch.setattr(claim_code, "utcnow", lambda: minted_at + claim_code.CLAIM_CODE_TTL * 2)
        expired = await self._capture(
            db_session, code_value=expired_device.claim_code, project_id=project.id
        )
        monkeypatch.undo()

        return wrong, spent, expired

    async def _capture(self, db_session, *, code_value, project_id):
        try:
            await claim_device(db_session, code=code_value, project_id=project_id)
        except InvalidClaimCodeError as exc:
            return exc
        raise AssertionError("the claim was expected to fail and did not")

    async def test_the_three_failures_are_the_same_value_to_the_caller(
        self, db_session, monkeypatch
    ):
        wrong, spent, expired = await self._three_failures(db_session, monkeypatch)

        assert type(wrong) is type(spent) is type(expired)
        assert str(wrong) == str(spent) == str(expired)
        assert wrong.args == spent.args == expired.args

    async def test_an_unknown_project_fails_the_same_way(self, db_session, monkeypatch):
        wrong, _, _ = await self._three_failures(db_session, monkeypatch)
        minted = await create_device(db_session)

        unknown_project = await self._capture(
            db_session,
            code_value=minted.claim_code,
            project_id="00000000-0000-0000-0000-000000000000",
        )

        assert type(unknown_project) is type(wrong)
        assert str(unknown_project) == str(wrong)
        assert unknown_project.args == wrong.args

    async def test_the_log_tells_the_three_apart(self, db_session, monkeypatch, caplog):
        with caplog.at_level(logging.WARNING, logger=CLAIM_LOGGER):
            await self._three_failures(db_session, monkeypatch)

        records = [r for r in caplog.records if r.name == CLAIM_LOGGER]
        assert len(records) == 3

        reasons = [getattr(r, "reason", None) for r in records]
        assert all(reasons), "every rejected claim must log why it was rejected"
        assert len(set(reasons)) == 3, f"the log cannot tell the three apart: {reasons}"

    async def test_the_log_does_not_carry_the_code_itself(self, db_session, monkeypatch, caplog):
        with caplog.at_level(logging.WARNING, logger=CLAIM_LOGGER):
            minted = await create_device(db_session)
            project = await a_project(db_session)
            await claim_device(db_session, code=minted.claim_code, project_id=project.id)
            await self._capture(db_session, code_value=minted.claim_code, project_id=project.id)

        for record in caplog.records:
            assert minted.claim_code not in record.getMessage()
            assert minted.claim_code not in str(getattr(record, "__dict__", {}))


class TestBehaviour5TwoUnspentCodesAreNeverTheSame:
    async def test_many_mints_do_not_collide(self, db_session):
        codes = [(await create_device(db_session)).claim_code for _ in range(300)]

        assert len(set(codes)) == len(codes)

    async def test_a_collision_does_not_overwrite_the_first_device(self, db_session, monkeypatch):
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


class TestBehaviour6ACodeSurvivesBeingReadAloud:
    async def test_no_code_contains_a_glyph_that_collides_when_spoken(self, db_session):
        codes = [claim_code.generate_claim_code() for _ in range(500)]

        offenders = {c for c in codes if set(c) & CONFUSABLE_GLYPHS}
        assert not offenders, f"codes carry glyphs that collide when read aloud: {offenders}"

    async def test_a_code_keeps_the_shape_a_facilitator_reads_out(self, db_session):
        for _ in range(50):
            code = claim_code.generate_claim_code()
            head, _, tail = code.partition("-")
            assert len(head) == 3
            assert len(tail) == 4
            assert code == f"{head}-{tail}"


class TestBehaviour7TheLabelAuthenticatesNothing:
    async def test_a_device_can_be_created_without_a_label(self, db_session):
        minted = await create_device(db_session)

        assert minted.device.label is None

    async def test_a_labelled_and_an_unlabelled_device_claim_identically(self, db_session):
        labelled_project = await a_project(db_session, name="Labelled")
        bare_project = await a_project(db_session, name="Bare")
        labelled = await create_device(db_session, label="the one by the window")
        bare = await create_device(db_session)

        claimed_labelled = await claim_device(
            db_session, code=labelled.claim_code, project_id=labelled_project.id
        )
        claimed_bare = await claim_device(
            db_session, code=bare.claim_code, project_id=bare_project.id
        )

        assert claimed_labelled.project_id == labelled_project.id
        assert claimed_bare.project_id == bare_project.id
        assert claimed_labelled.label == "the one by the window"
        assert claimed_bare.label is None

    async def test_the_label_is_editable_after_the_fact(self, db_session):
        minted = await create_device(db_session)

        await set_device_label(db_session, minted.device.id, "back shelf, cracked case")
        relabelled = await set_device_label(db_session, minted.device.id, "front desk")

        assert relabelled.label == "front desk"

    async def test_the_label_can_be_cleared(self, db_session):
        minted = await create_device(db_session, label="front desk")

        cleared = await set_device_label(db_session, minted.device.id, None)

        assert cleared.label is None
