"""The record read is FE-44's ``Project``, key for key — checked against the frozen source.

The DoD's first line is *the read returns the full record shaped as FE-44 froze it*, and a
test that restated the seventy-three keys here would be a second copy of the contract going
stale beside the first. So the split is **vendored** from ``src/types/project.ts`` as
``projectContract.json``, carrying the frontend commit it was emitted from — the mechanism
``docs/resource_requests.md`` §9 chose for the same problem, and for its reason: neither CI
job needs the other repository checked out, and a contract change shows up as a reviewable
diff instead of as a silent drift.

``src/types/__tests__/contract.test.ts`` pins the same split on the other side against the
127-record export: **the 55 required fields are exactly the export's keys and the 18 optional
ones are exactly the keys it does not have.** So a field added here without being added there
fails over there, and a key dropped here fails in this file.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.models.shema_record import ShemaProjectRecord

CONTRACT = json.loads((Path(__file__).parent / "projectContract.json").read_text(encoding="utf-8"))

#: The one key the response carries that ``Project`` does not.
#:
#: BE-05 added it to the card with the argument this inherits: the console stops computing
#: FE-44 §7's nine derivations and reads the server's answer, so *is this project stale* has
#: one implementation and the ficha's badge cannot disagree with the list's. It is additive —
#: a client that ignores it sees exactly ``Project``.
ADDED_BY_THE_SERVER = {"derived"}


def _wire_keys() -> set[str]:
    return set(ShemaProjectRecord(id="afrikaans-kaaps").model_dump(by_alias=True))


def test_the_record_carries_every_key_the_contract_freezes() -> None:
    frozen = set(CONTRACT["required"]) | set(CONTRACT["optional"])
    assert frozen - _wire_keys() == set(), "the ficha would render blanks for these"


def test_the_record_carries_nothing_the_contract_does_not() -> None:
    """A 74th key added to a frozen shape is how a contract stops being one."""
    frozen = set(CONTRACT["required"]) | set(CONTRACT["optional"])
    assert _wire_keys() - frozen == ADDED_BY_THE_SERVER


def test_the_split_is_still_fifty_five_and_eighteen() -> None:
    """The vendored copy's own checksum, so a stale emission is visible rather than silent."""
    assert len(CONTRACT["required"]) == 55
    assert len(CONTRACT["optional"]) == 18


def test_three_columns_that_exist_stay_off_the_wire() -> None:
    """``completedDate`` is a column and not a key; ``version`` and the staleness date are ours.

    ``completed_date`` is GATE-01 item 6's schema change, sitting in the table so that a
    stacked wave does not discover it late, and nothing writes it. ``version`` travels as an
    ``ETag`` and ``last_progress_date`` is what ``derived`` was computed from.
    """
    assert {"completedDate", "version", "lastProgressDate"} & _wire_keys() == set()


def test_the_base_is_the_team_under_the_contracts_second_name() -> None:
    """One column, two keys — BE-02 collapsed them and FE-44 §5.1 asks for both on the wire."""
    record = ShemaProjectRecord(id="x", team="YWAM Porto Velho")
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
    record = ShemaProjectRecord(id="x", latitude=-10.5, longitude=-60.25)
    assert record.model_dump(by_alias=True)["coords"] == (-60.25, -10.5)


def test_a_record_nobody_has_assessed_reports_nothing_rather_than_boa() -> None:
    """``""`` is not ``boa`` (FE-44 §7.4): the 127 seed records arrive with every one empty."""
    payload = ShemaProjectRecord(id="x").model_dump(by_alias=True)
    assert payload["healthEmotional"] is None
    assert payload["healthPhysical"] is None
