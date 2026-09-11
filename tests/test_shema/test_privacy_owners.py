"""**The three nets that make the privacy rules rules rather than intentions.**

A rule applied per endpoint is a rule the next endpoint forgets. ``docs/shema.md`` §6.4 asks
for the same mechanism ``_scope.py`` uses for the module's only ``select(ShemaProject)``, and
FE-44's frontend already has its own version of it: a scan that fails the build when a file
that is not the named owner reads a guarded column. This file is that scan, plus the two
checks the scan alone cannot make.

The three nets, and what each one catches that the others do not:

1. **The owner globs.** No file in ``app/services/shema/`` or ``app/api/shema/`` but the
   named owner may read a guarded column. This is what stops a future service reaching past
   the boundary — a ``group_by(ShemaProject.location)`` for a badge, a search that filters on
   the country, a notification body that reads the prayer text straight off the row.
2. **The route audit.** Every route under ``/api/shema`` whose response model can name a
   place must inherit :class:`~app.models.shema_privacy.LeavingShape`. This is what makes an
   endpoint written by somebody who has never read ``docs/shema.md`` either protected or red,
   and never quietly open.
3. **The vocabulary check.** Every field the boundary promises to replace has a replacement,
   so the two lists cannot drift into a field that is declared guarded and is emitted whole.

**Why AST and not a substring search.** The precedent in this directory
(``test_the_app_key_is_named_once_in_the_module``) greps for a quoted literal, which works
for a literal. A column name is a word that appears in prose, and this repository's files are
mostly prose: a substring search over these docstrings would fail on every file that explains
the rule, so the check would be deleted within a week. Attribute access is what a leak
actually looks like, and ``ast`` sees exactly that.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from fastapi.routing import APIRoute
from pydantic import BaseModel

from app.db.models.shema_enums import ShemaRegionKey
from app.main import create_app
from app.models.shema_privacy import (
    CONTACT_FIELDS,
    PLACE_FIELDS,
    WITHHELD_FIELDS,
    LeavingShape,
    withheld_value,
)
from tests.test_shema.conftest import PREFIX

REPO_ROOT = Path(__file__).resolve().parents[2]

#: The two packages the globs read. ``app/models/`` is deliberately not among them: the
#: request shapes there carry the guarded names because they are what a client *writes*, and
#: the record's own editing surface is the one place FE-44 §8.1 rule 5 keeps the truth.
GUARDED_PACKAGES = (REPO_ROOT / "app" / "services" / "shema", REPO_ROOT / "app" / "api" / "shema")

#: What the sensitive-country rule guards. ``sensitivity`` is in the list beside the flag
#: because it is the export's free text about *why* a place is sensitive, which is a worse
#: thing to emit than the country; BE-02 kept it as provenance and nothing reads it for a
#: safety decision.
#:
#: ``team`` is deliberately **not** here, and the omission is the honest half of this list.
#: It is the base name, it is withheld inside every leaving shape, and it is also one of the
#: four fields required to save — so every write path legitimately reads it, and a glob that
#: refused them would be a glob somebody switches off. The boundary is what guards it.
REDACTION_COLUMNS = frozenset(
    {"location", "location2", "latitude", "longitude", "sensitive_country", "sensitivity"}
    | set(CONTACT_FIELDS)
)

#: The three columns whose only reader is the consent gate, in the spelling BE-02 wrote them
#: in so this test and that table cannot drift.
CONSENT_COLUMNS = frozenset({"prayer_requests", "prayer_visibility", "prayer_requests_audio"})

#: The per-item sharing decision and its evidence.
MEDIA_COLUMNS = frozenset({"authorization_granted", "authorized_by", "authorized_at"})

#: Which file owns which set, and the allowlist beside it — **one entry each today**.
#:
#: A later issue that genuinely needs a second reader adds a line here with its reason, which
#: is a deliberate edit somebody has to justify in review rather than a rule somebody forgot.
#: The two already foreseen: BE-06's write path has to read and write ``location`` to keep
#: ``region_key`` derived from it, and BE-16's seed interprets ``sensitivity`` into the flag —
#: though that one is a script and not in these packages at all.
OWNERS: dict[str, tuple[frozenset[str], frozenset[str]]] = {
    "sensitive country": (REDACTION_COLUMNS, frozenset({"_redaction.py"})),
    "consent": (CONSENT_COLUMNS, frozenset({"_consent.py"})),
    "media authorization": (MEDIA_COLUMNS, frozenset({"_media_sharing.py"})),
}

#: Routes under ``/api/shema`` whose response may carry a place unreduced — **by method and
#: path**, never by path alone.
#:
#: BE-04 wrote this as a set of paths and expected one line in it. BE-06 found that one path
#: carries two methods with two answers: ``POST /api/shema/projects`` returns the record it
#: just created and must be here, while ``GET /api/shema/projects`` is BE-05's collection read
#: and must **not** be — exempting the path would have switched the audit off for the busiest
#: leaving shape in the module, silently and in the same line that looked like an exemption for
#: something else. So the key is the pair, which is also what the failure message already
#: printed.
#:
#: ``GET /api/shema/session`` is not listed because it needs no exemption: a persona carries no
#: project data at all.
#:
#: **The three entries are BE-06's record, read and written.** A project read by somebody
#: allowed to open it is a **coordination** surface and carries the truth, because hiding the
#: country from its own author is data loss rather than privacy (FE-44 §8.1 rule 5, and §9.0
#: in one line). The create and the patch answer the same shape for the same reason: FE-44 §9.3
#: has both return the recomputed record, so a reduced reply to a save would show the author a
#: withheld version of what they had just typed. Every other read — the collection, the wall,
#: the report, the file — leaves coordination and goes through the boundary.
COORDINATION_ROUTES: frozenset[tuple[str, str]] = frozenset(
    {
        ("GET", f"{PREFIX}/projects/{{project_id}}"),
        ("POST", f"{PREFIX}/projects"),
        ("PATCH", f"{PREFIX}/projects/{{project_id}}"),
    }
)


def _guarded_reads(source: Path, columns: frozenset[str]) -> set[str]:
    """Every guarded name this file reaches for, as an attribute or through ``getattr``.

    Prose is not a read. Neither is an import or a re-export: naming a function that happens
    to share a column's name is what ``app/services/shema/__init__.py`` does for a living.
    """
    tree = ast.parse(source.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in columns:
            found.add(node.attr)
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in ("getattr", "setattr", "hasattr")
        ):
            for argument in node.args[1:2]:
                if isinstance(argument, ast.Constant) and argument.value in columns:
                    found.add(str(argument.value))
    return found


def test_each_guarded_column_set_has_exactly_one_reader() -> None:
    """**The DoD's first line, as a property of the tree rather than of a review.**

    Reads both packages at once, because the rule is not *services are careful* — it is that
    there is one reader, and a router that reaches for a column is the same defect arriving
    through a door where it is harder to see.
    """
    offenders: dict[str, list[str]] = {}
    for label, (columns, owners) in OWNERS.items():
        for package in GUARDED_PACKAGES:
            for source in sorted(package.glob("*.py")):
                if source.name in owners:
                    continue
                reads = _guarded_reads(source, columns)
                if reads:
                    key = f"{label}: {source.relative_to(REPO_ROOT)}"
                    offenders[key] = sorted(reads)

    assert offenders == {}, (
        "a guarded column is read outside its one owner — the rule is now applied per file, "
        f"which is the rule the next file forgets: {offenders}"
    )


def test_each_owner_actually_reads_what_it_owns() -> None:
    """The other half, so the globs above cannot pass by the owners being empty files.

    A test that only forbids is a test that goes green when the thing it guards is deleted.
    """
    silent = []
    for label, (columns, owners) in OWNERS.items():
        for name in owners:
            source = REPO_ROOT / "app" / "services" / "shema" / name
            if not source.exists() or not _guarded_reads(source, columns):
                silent.append(f"{label}: {name}")

    assert silent == [], f"an owner that reads none of what it owns: {silent}"


def _models_in(annotation: Any, depth: int = 0) -> set[type[BaseModel]]:
    """Every Pydantic model reachable from a response annotation, through the generics.

    ``list[ProjectOut]``, ``dict[str, ProjectOut]`` and a shape with a nested project are all
    the same leak with different packaging. Depth-limited because a self-referential model is
    a legitimate shape and would otherwise hang the suite rather than fail it.
    """
    from typing import get_args

    if depth > 6 or annotation is None:
        return set()
    found: set[type[BaseModel]] = set()
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        found.add(annotation)
        for field in annotation.model_fields.values():
            found |= _models_in(field.annotation, depth + 1)
        return found
    for argument in get_args(annotation):
        found |= _models_in(argument, depth + 1)
    return found


def _names_a_place(model: type[BaseModel]) -> list[str]:
    """The fields that make a shape able to name where a project is."""
    telling = set(PLACE_FIELDS) | set(CONTACT_FIELDS) | {"sensitive_country"}
    return sorted(name for name in model.model_fields if name in telling)


def test_every_route_that_can_name_a_place_leaves_through_the_boundary() -> None:
    """**The DoD's third line, read off the application the server actually builds.**

    *Adding a new endpoint without knowledge of the rule still yields protected output.* The
    mechanism is two-sided: a response model that inherits
    :class:`~app.models.shema_privacy.LeavingShape` is redacted by declaring its fields, and a
    response model that does not inherit it and can still name a place fails here. So the
    author who has never heard of this rule gets a protected payload; the author who routes
    around it gets a red build; and the author who genuinely needs the truth adds a line to
    :data:`COORDINATION_ROUTES` and explains it once, in a diff.

    Asking the route table rather than the source is what makes an inherited shape count —
    the whole point being that the subclass does not mention the rule.
    """
    app = create_app()
    unprotected = []
    for route in app.routes:
        if not isinstance(route, APIRoute) or not route.path.startswith(PREFIX):
            continue
        methods = sorted(set(route.methods or ()) - {"HEAD", "OPTIONS"})
        if all((method, route.path) in COORDINATION_ROUTES for method in methods):
            continue
        for model in _models_in(route.response_model):
            place = _names_a_place(model)
            if place and not issubclass(model, LeavingShape):
                unprotected.append(f"{methods} {route.path} -> {model.__name__}{place}")

    assert unprotected == [], (
        "a response model can name a project's place and does not inherit LeavingShape, so "
        f"the redaction is not applied to it: {unprotected}"
    )


def test_every_field_the_boundary_guards_has_a_replacement() -> None:
    """The two lists cannot drift into a field that is declared guarded and emitted whole.

    Exercised over every region rather than one, because the replacement for a coordinate is
    read out of a table with a row per region and a missing row would be a ``KeyError`` on
    exactly the region nobody tested.
    """
    for region in ShemaRegionKey:
        for field_name in WITHHELD_FIELDS:
            replacement = withheld_value(field_name, region)
            assert replacement is not None, f"{field_name} has no withheld value"
            if field_name in ("location", "country"):
                assert replacement == region.value


def test_the_place_fields_are_all_withheld_fields() -> None:
    """The audit's trigger set may not be wider than what the boundary actually replaces."""
    assert set(PLACE_FIELDS) <= set(WITHHELD_FIELDS)
    assert set(CONTACT_FIELDS) <= set(WITHHELD_FIELDS)
