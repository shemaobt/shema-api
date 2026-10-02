"""OBT-560 — a sensitive project's language name is withheld from everybody but coordination.

The residue OBT-552 left: the id stopped naming the place, and the name kept doing it — the
real record in Egypt is *Sa'di of High Egypt*. Karina, via Daniel, 1/out/2026, chose a name
coordination registers for those projects. Ours, not hers: while none is registered, the region
key stands in, which is the convention ``location`` already follows.

The sweep is over the **classes**, not over a list of them: every ``LeavingShape`` that declares
a name field is found by walking the subclasses, so a shape added later is swept the day it is
written. A required field the sweep does not know how to fill fails it loudly, which is the
moment to add one line to ``FILLERS`` and nothing else.
"""

from __future__ import annotations

import importlib
import pkgutil
from datetime import UTC, date, datetime
from typing import Any

import pytest

import app.models
from app.db.models.shema import ShemaProject
from app.db.models.shema_enums import ShemaRegionKey
from app.models.shema_privacy import NAME_FIELDS, LeavingShape, ShemaReader
from app.services.shema._redaction import language_name_for
from app.services.shema._scope import NO_COORDINATION, Readership, RegionScope
from app.services.shema.read_submission import inbox_name

for _module in pkgutil.iter_modules(app.models.__path__):
    if _module.name.startswith("shema"):
        importlib.import_module(f"app.models.{_module.name}")

REAL = "Sa'di of High Egypt"
PUBLIC = "Sa'di"

#: A value for every required field a leaving shape declares, by name.
FILLERS: dict[str, Any] = {
    "id": "p-1",
    "project_id": "p-1",
    "language_code": "",
    "location": "Cairo, Egypt",
    "team": "",
    "created_at": datetime(2026, 10, 2, tzinfo=UTC),
    "kind": "pulso",
    "definition_version": 1,
    "expires_at": date(2026, 10, 30),
    "fields": [],
}


#: The shapes that keep the real name, each with its reason in its own ``_withhold_name``:
#: the intake form is read by the link's holder, who is the project's team.
KEEPS_THE_NAME = frozenset({"IntakeForm"})


def _shapes() -> list[type[LeavingShape]]:
    found: set[type[LeavingShape]] = set()
    pending = list(LeavingShape.__subclasses__())
    while pending:
        shape = pending.pop()
        found.add(shape)
        pending.extend(shape.__subclasses__())
    named = [
        s
        for s in found
        if any(name in s.model_fields for name in NAME_FIELDS) and s.__name__ not in KEEPS_THE_NAME
    ]
    return sorted(named, key=lambda s: s.__name__)


def _source(shape: type[LeavingShape], public: str | None, sensitive: bool) -> dict[str, Any]:
    source: dict[str, Any] = {
        "language_name": REAL,
        "sensitive_country": sensitive,
        "region_key": ShemaRegionKey.AFRICA,
        "public_language_name": public,
    }
    for name, field in shape.model_fields.items():
        if field.is_required() and name not in source:
            assert name in FILLERS, f"{shape.__name__}.{name}: add a filler to FILLERS"
            source[name] = FILLERS[name]
    return source


def _name(payload: LeavingShape) -> str:
    return next(getattr(payload, n) for n in NAME_FIELDS if n in type(payload).model_fields)


def test_the_sweep_finds_the_shapes_the_issue_names() -> None:
    names = {shape.__name__ for shape in _shapes()}
    assert {
        "ShemaProjectCard",
        "ShemaProjectRecord",
        "PrayerRequestEntry",
        "ExportedProject",
        "EtenYearSnapshot",
        "ShemaNeedLine",
    } <= names


def test_the_intake_form_keeps_the_real_name_for_the_team() -> None:
    """The link's holder is the team: two unnamed sensitive projects would otherwise read alike."""
    from app.models.shema_forms import IntakeForm

    form = IntakeForm(
        kind="pulso",
        definition_version=1,
        language_name=REAL,
        expires_at=date(2026, 10, 30),
        fields=[],
    )
    assert form.language_name == REAL and form.language_name_withheld is False


@pytest.mark.parametrize("shape", _shapes(), ids=lambda shape: shape.__name__)
@pytest.mark.parametrize("reader", [ShemaReader.OTHER, ShemaReader.OUTSIDE])
def test_another_reader_reads_the_public_name_and_never_the_real_one(shape, reader) -> None:
    payload = shape.read_by(_source(shape, PUBLIC, sensitive=True), reader)

    assert _name(payload) == PUBLIC
    assert payload.language_name_withheld is True
    assert "Egypt" not in str(payload.model_dump(mode="json", by_alias=True))


@pytest.mark.parametrize("shape", _shapes(), ids=lambda shape: shape.__name__)
def test_with_no_public_name_the_region_stands_in(shape) -> None:
    payload = shape.read_by(_source(shape, None, sensitive=True), ShemaReader.OTHER)

    assert _name(payload) == ShemaRegionKey.AFRICA.value
    assert payload.language_name_withheld is True


@pytest.mark.parametrize("shape", _shapes(), ids=lambda shape: shape.__name__)
def test_coordination_and_an_open_project_keep_the_real_name(shape) -> None:
    coordination = shape.read_by(_source(shape, PUBLIC, sensitive=True), ShemaReader.COORDINATION)
    open_project = shape.read_by(_source(shape, PUBLIC, sensitive=False), ShemaReader.OUTSIDE)

    assert _name(coordination) == REAL and coordination.language_name_withheld is False
    assert _name(open_project) == REAL and open_project.language_name_withheld is False


@pytest.mark.parametrize("shape", _shapes(), ids=lambda shape: shape.__name__)
def test_a_reduced_payload_rebuilt_from_its_dump_keeps_the_public_name(shape) -> None:
    """The seam: a dict round trip carries neither the flag nor the public name, and must not
    reduce a second time a payload the boundary already reduced."""
    reduced = shape.read_by(_source(shape, PUBLIC, sensitive=True), ShemaReader.OTHER)

    rebuilt = shape.model_validate(reduced.model_dump())

    assert _name(rebuilt) == PUBLIC


def _project(public: str | None, sensitive: bool = True) -> ShemaProject:
    return ShemaProject(
        id="p-1",
        language_name=REAL,
        public_language_name=public,
        sensitive_country=sensitive,
        region_key=ShemaRegionKey.AFRICA,
    )


def test_the_paths_that_are_not_shapes_follow_the_same_rule() -> None:
    """The inbox and the notices print the name and nothing else of the project, so they never
    meet the boundary; ``language_name_for`` is the boundary's rule for them."""
    assert language_name_for(_project(PUBLIC), ShemaReader.OTHER) == PUBLIC
    assert language_name_for(_project(None), ShemaReader.OTHER) == ShemaRegionKey.AFRICA.value
    assert language_name_for(_project(None), ShemaReader.OTHER, fallback="") == ""
    assert language_name_for(_project(PUBLIC), ShemaReader.COORDINATION) == REAL
    assert language_name_for(_project(PUBLIC, sensitive=False), ShemaReader.OUTSIDE) == REAL


def test_the_inbox_prints_the_name_its_reader_may_read() -> None:
    """OBT Lab reads the Pulse inbox and is not coordination; a readership is per region."""
    assert inbox_name(_project(PUBLIC), NO_COORDINATION) == PUBLIC
    everywhere = Readership(coordination=RegionScope(global_=True, regions=frozenset()))
    assert inbox_name(_project(PUBLIC), everywhere) == REAL
