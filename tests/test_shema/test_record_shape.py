"""The record read is FE-44's ``Project``, key for key — checked against the frozen source.

The DoD's first line is *the read returns the full record shaped as FE-44 froze it*, and a
test that restated the seventy-six keys here would be a second copy of the contract going
stale beside the first. So the split is **vendored** from ``src/types/project.ts`` as
``projectContract.json``, carrying the frontend commit it was emitted from — the mechanism
``docs/resource_requests.md`` §9 chose for the same problem, and for its reason: neither CI
job needs the other repository checked out, and a contract change shows up as a reviewable
diff instead of as a silent drift.

``src/types/__tests__/contract.test.ts`` pins the same split on the other side against the
127-record export: **the 55 required fields are exactly the export's keys and the 21 optional
ones are exactly the keys it does not have.** So a field added here without being added there
fails over there, and a key dropped here fails in this file.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from app.models.shema_record import ShemaProjectRecord

CONTRACT = json.loads((Path(__file__).parent / "projectContract.json").read_text(encoding="utf-8"))

#: The keys the response carries that ``Project`` does not — additive, so a client that ignores
#: them sees exactly ``Project``.
#:
#: ``locationWithheld`` is OBT-528's: the record became a leaving shape built for its reader, and
#: every leaving shape carries the marker. It was one of three until the contract caught up:
#: ``derived`` (BE-05's, the nine derivations the console stopped computing) entered ``Project``
#: with OBT-407 and ``readAs`` (OBT-528's *truth or region*) with FE-48, OBT-532 — both are the
#: contract's own keys in the emission vendored since OBT-413.
ADDED_BY_THE_SERVER = {"locationWithheld"}


def _wire_keys() -> set[str]:
    return set(ShemaProjectRecord(id="afrikaans-kaaps").model_dump(by_alias=True))


def test_the_record_carries_every_key_the_contract_freezes() -> None:
    frozen = set(CONTRACT["required"]) | set(CONTRACT["optional"])
    assert frozen - _wire_keys() == set(), "the ficha would render blanks for these"


def test_the_record_carries_nothing_the_contract_does_not() -> None:
    """A key the contract does not have, added to a frozen shape, is how it stops being one."""
    frozen = set(CONTRACT["required"]) | set(CONTRACT["optional"])
    assert _wire_keys() - frozen == ADDED_BY_THE_SERVER


def test_the_split_is_fifty_five_and_twenty_one() -> None:
    """The vendored copy's own checksum, so a stale emission is visible rather than silent."""
    assert len(CONTRACT["required"]) == 55
    assert len(CONTRACT["optional"]) == 21


def test_two_columns_that_exist_stay_off_the_wire() -> None:
    """``version`` and the staleness date are ours, and neither is a key of ``Project``.

    ``version`` travels as an ``ETag`` and ``last_progress_date`` is what ``derived`` was
    computed from. ``completedDate`` was the third until OBT-413: the console's ``Project``
    gained it (FE-50), and ``test_the_completion_day_travels_as_a_day_or_null`` holds it now.
    """
    assert {"version", "lastProgressDate"} & _wire_keys() == set()


@pytest.mark.parametrize(
    ("stamped", "wire"), [(date(2026, 3, 31), "2026-03-31"), (None, None)], ids=["day", "null"]
)
def test_the_completion_day_travels_as_a_day_or_null(
    stamped: date | None, wire: str | None
) -> None:
    """``completed_date`` is what ``save_project`` stamped on the move into ``concluido``
    (BE-11), served as the ``YYYY-MM-DD`` FE-50's annual report reads, and ``null`` — never
    ``""`` and never absent — for a project with no stamp, so *not finished* and *finished
    before the stamp existed* read the same undated way on both sides.
    """
    payload = ShemaProjectRecord(id="x", completed_date=stamped).model_dump(
        by_alias=True, mode="json"
    )
    assert payload["completedDate"] == wire


def test_the_base_is_the_team_under_the_contracts_second_name() -> None:
    """One column, two keys — BE-02 collapsed them and FE-44 §5.1 asks for both on the wire.

    The record says it is not sensitive: since OBT-528 one that cannot say fails closed, as every
    leaving shape does, and its base would read ``""`` (``test_reader.py`` pins that half).
    """
    record = ShemaProjectRecord(id="x", team="YWAM Porto Velho", sensitive_country=False)
    payload = record.model_dump(by_alias=True)
    assert payload["team"] == payload["ywamBase"] == "YWAM Porto Velho"


def test_the_three_org_chart_names_are_empty_and_cannot_be_anything_else() -> None:
    """``src/fixtures/__tests__/fixtures.test.ts`` asserts they stay empty; there is no column.

    They are emitted rather than dropped because they are **required** keys of the interface
    FE-44 §9.3 has ``POST`` take whole — a response missing them is a response the client
    cannot send back.
    """
    payload = ShemaProjectRecord(id="x", team="YWAM Recife").model_dump(by_alias=True)
    assert payload["regionalCoordinator"] == ""
    assert payload["obtLabPerson"] == ""
    assert payload["resourceCirclePerson"] == ""


def test_coordinates_are_longitude_first_and_survive_the_response_model() -> None:
    """``[0, 0]`` is *no coordinate* and that is a fact about the pair, so the pair travels."""
    record = ShemaProjectRecord(id="x", latitude=-10.5, longitude=-60.25, sensitive_country=False)
    assert record.model_dump(by_alias=True)["coords"] == (-60.25, -10.5)


def test_a_record_nobody_has_assessed_reports_nothing_rather_than_boa() -> None:
    """``""`` is not ``boa`` (FE-44 §7.4): the 127 seed records arrive with every one empty."""
    payload = ShemaProjectRecord(id="x").model_dump(by_alias=True)
    assert payload["healthEmotional"] is None
    assert payload["healthPhysical"] is None
