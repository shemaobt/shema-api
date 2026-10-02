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
   so the two lists cannot drift into a field that is declared guarded and is emitted whole —
   and, since OBT-528, every field a withheld read reduces is a field that reader is refused
   on write.
4. **The reader nets** (OBT-528). The truth of a sensitive place is coordination's, so the
   routes that take the caller's reader are a list (:data:`READER_ROUTES`) and the services that
   build a shape for it are two files — an export that reached for the session's reader would be
   a route that carries the truth out of the system, and it is red here until somebody lists it.

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
from app.models.shema_eten import EtenLocationShown
from app.models.shema_privacy import (
    BASE_FIELDS,
    CONTACT_FIELDS,
    COORDINATION_WRITES,
    PLACE_FIELDS,
    REASON_FIELDS,
    WITHHELD_FIELDS,
    WITHHELD_WRITES,
    LeavingShape,
    withheld_value,
)
from tests.test_shema.conftest import PREFIX
from tests.test_shema.test_access import _reaches

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
    {
        "location",
        "location2",
        "latitude",
        "longitude",
        "sensitive_country",
        "sensitivity",
        "public_language_name",
    }
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
    "sensitive country": (
        REDACTION_COLUMNS,
        # ``_needs.py``'s ``urgent_need_notice``/``urgent_needs_notice`` read
        # ``ShemaNeedLine.location`` — never ``ShemaProject.location``. By the time either
        # function sees it, ``_redaction.py``'s boundary has already reduced it to the region
        # key or emptied it, because ``ShemaNeedLine`` is a ``LeavingShape`` and the reduction
        # runs in its own model validator on construction (``app/models/shema_privacy.py``).
        # The glob cannot see a Pydantic attribute apart from an ORM column by name alone, so
        # the second reader here is real by the letter of the check and safe by what it reads —
        # BE-15 names it rather than widening the columns the check watches.
        #
        # BE-13's two are about a **person**, never a project. ``_directory.py`` is the
        # network's own owner — the only file in either package that names
        # ``ShemaIntercessor`` — and reads that row's ``sensitive_country`` to withhold a
        # person's country on every path that leaves (``docs/shema.md`` §6.4's note;
        # ``test_people_privacy.py`` is its net). ``add_intercessor.py`` reads
        # ``IntercessorCreate.sensitive_country`` — the client's own declaration in a request
        # shape, which this file keeps outside the guarded packages on purpose — and hands it
        # to the owner unchanged. Neither touches a project column.
        frozenset({"_redaction.py", "_needs.py", "_directory.py", "add_intercessor.py"}),
    ),
    "consent": (CONSENT_COLUMNS, frozenset({"_consent.py"})),
    "media authorization": (MEDIA_COLUMNS, frozenset({"_media_sharing.py"})),
}

#: Routes under ``/api/shema`` whose response may carry a place unreduced — **by method and
#: path**, never by path alone. **Empty since OBT-528.**
#:
#: BE-04 wrote this as a set of paths and expected one line in it; BE-06 keyed it by method and
#: path and put the record's read, create and patch here, and BE-07 the health-assessment
#: ``POST`` that answers the same record. GATE-04 then moved the truth from the record to its
#: reader: the record is a :class:`~app.models.shema_privacy.LeavingShape` built for the caller,
#: so the route that serves a coordinator the truth serves everybody else the region, and it
#: needs no exemption from this audit. Which routes take the caller's reader is
#: :data:`READER_ROUTES`' question below; this list stays, empty, for a route that one day has
#: to be exempt — a line somebody writes and argues.
#:
#: ``GET /api/shema/session`` is not listed because it needs no exemption: a persona carries no
#: project data at all.
COORDINATION_ROUTES: frozenset[tuple[str, str]] = frozenset()

#: The routes whose dependency tree reaches the caller's reader (``_deps.Reading``) — the only
#: routes that may build a payload carrying the truth of a sensitive place, because the reader
#: is the only thing that lets a shape skip the reduction (OBT-528).
#:
#: The four record and collection routes, and the health-assessment ``POST``, build their
#: answer for it. The two form imports take it because an import is a person writing the record,
#: and ``save_project`` asks the writer's reader which fields they may write; their answer names
#: no place. The Admin's list of pending projects (OBT-547) reads the place the team typed, for
#: the Admin to confirm or correct it, as a console read. A route added here is one that reads as
#: the caller — an export, a report or a download must not be, because what leaves is built for
#: ``outside`` whoever asked for it.
#:
#: **BE-14's two, and why neither is that route.** The projects import is the form imports'
#: case — a person writing records, answered with a count — and asks the reader one question
#: more, whether the importer coordinates anything, because only coordination imports. The
#: export takes the reader to **address its header** — how many places were withheld is
#: coordination's to be told (GATE-04, 1.3) — and builds every row for ``outside``:
#: ``export_projects.py`` calls no ``read_by``, which
#: :func:`test_only_the_console_reads_build_a_shape_for_the_sessions_reader` holds, and
#: ``tests/test_shema/test_transfer.py`` exports as the region's own coordinator and finds no
#: place in the file.
READER_ROUTES: frozenset[tuple[str, str]] = frozenset(
    {
        ("GET", f"{PREFIX}/projects"),
        ("GET", f"{PREFIX}/projects/{{project_id}}"),
        ("POST", f"{PREFIX}/projects"),
        ("PATCH", f"{PREFIX}/projects/{{project_id}}"),
        ("POST", f"{PREFIX}/projects/{{project_id}}/health-assessments"),
        # OBT-556: the history's notes are coordination's on a withheld project; no place.
        ("GET", f"{PREFIX}/projects/{{project_id}}/health-assessments"),
        ("POST", f"{PREFIX}/forms/submissions"),
        # OBT-560: the inbox prints the language's name, which can name the place.
        ("GET", f"{PREFIX}/forms/submissions"),
        # OBT-556: a received Pulse's free text is coordination's on a withheld project.
        ("GET", f"{PREFIX}/forms/submissions/{{submission_id}}"),
        ("POST", f"{PREFIX}/forms/submissions/{{submission_id}}/import"),
        ("GET", f"{PREFIX}/pending-projects"),
        ("GET", f"{PREFIX}/export/projects"),
        ("POST", f"{PREFIX}/import/projects"),
    }
)

#: The services that build a shape for the session's reader: the Projetos screen's cards, the
#: record, and — OBT-547 — the Admin's list of pending projects, a console read of the place the
#: team typed that the Admin confirms or corrects. Every other leaving shape in the module is built
#: with no reader, which is ``outside``.
SESSION_READS = frozenset({"browse_projects.py", "read_record.py", "list_pending_projects.py"})

#: Routes under ``/api/shema`` whose subject is a **person**, not a project, so the project
#: vocabulary above misreads their fields — BE-13's two directories.
#:
#: The org chart's ``team`` is a list of accounts and a homonym of the base name BE-02
#: collapsed ``ywamBase`` into; there is no place in it to withhold. The intercessor entry
#: does name a country, and it is protected — by ``_directory.py``'s ``leaving_person``,
#: the owner named in :data:`OWNERS`, under FE-44 §9.6's own marker (``country: ""``
#: beside ``sensitiveCountry``) rather than a region key; and ``sensitiveCountry`` itself
#: is the flag the resource circle sets and reads on the entry, which :class:`LeavingShape`
#: would exclude. So the shape is not a ``LeavingShape`` and is not unguarded:
#: ``tests/test_shema/test_people_privacy.py`` is the audit these seven answer to — the
#: seventh is OBT-531's review, which answers the same entry. Listed by the pair, as above,
#: so a future project-shaped route on a neighbouring path is still asked.
PEOPLE_ROUTES: frozenset[tuple[str, str]] = frozenset(
    {
        ("GET", f"{PREFIX}/regions"),
        ("GET", f"{PREFIX}/regions/{{region_key}}/team"),
        ("GET", f"{PREFIX}/prayer/intercessors"),
        ("POST", f"{PREFIX}/prayer/intercessors"),
        ("PATCH", f"{PREFIX}/prayer/intercessors/{{intercessor_id}}"),
        ("PUT", f"{PREFIX}/prayer/intercessors/{{intercessor_id}}/consents/{{context}}"),
        ("POST", f"{PREFIX}/prayer/intercessors/{{intercessor_id}}/review"),
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


#: Models a computed field builds **from a leaving shape that has already been reduced** — so
#: they carry a place only after the boundary decided what it may be, and are not leaving
#: shapes of their own. BE-11's ``EtenLocationShown`` is FE-44's ``LocationDisplay`` open half:
#: ``EtenYearSnapshot.country`` builds it from the ``location`` its own ``LeavingShape``
#: reduced, and inheriting the boundary here would add ``locationWithheld`` to a shape the
#: contract froze as ``{withheld, location}``. A new name here is a line somebody has to argue.
DISPLAYS_OF_A_REDUCED_SHAPE: frozenset[type[BaseModel]] = frozenset({EtenLocationShown})


def _models_in(annotation: Any, depth: int = 0) -> set[type[BaseModel]]:
    """Every Pydantic model reachable from a response annotation, through the generics.

    ``list[ProjectOut]``, ``dict[str, ProjectOut]`` and a shape with a nested project are all
    the same leak with different packaging. Depth-limited because a self-referential model is
    a legitimate shape and would otherwise hang the suite rather than fail it.

    **Computed fields are walked too** (BE-11). A ``@computed_field`` is serialised like any
    field and is absent from ``model_fields``, so a model that returned a place from one would
    otherwise be invisible to the audit — the net would have a hole exactly where the ETEN
    report's ``country`` is.
    """
    from typing import get_args

    if depth > 6 or annotation is None:
        return set()
    found: set[type[BaseModel]] = set()
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        found.add(annotation)
        for field in annotation.model_fields.values():
            found |= _models_in(field.annotation, depth + 1)
        for computed in annotation.model_computed_fields.values():
            found |= _models_in(computed.return_type, depth + 1)
        return found
    for argument in get_args(annotation):
        found |= _models_in(argument, depth + 1)
    return found


def _names_a_place(model: type[BaseModel]) -> list[str]:
    """The fields that make a shape able to name where a project is.

    :data:`~app.models.shema_privacy.BASE_FIELDS` is in here for the reason the PR argues
    ``team`` has to be withheld at all — ``YWAM Egypt`` names Egypt — and for one the other
    fields do not have: ``team`` is deliberately outside the owner globs above, so a shape
    that declares it and nothing else would be the one guarded field with no net on it. A
    later notification or Pulse entry with a ``team`` and no ``location`` is exactly the shape
    that would pass an audit that only looked for a place column.
    """
    telling = (
        set(PLACE_FIELDS)
        | set(BASE_FIELDS)
        | set(CONTACT_FIELDS)
        | set(REASON_FIELDS)
        | {"sensitive_country"}
    )
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
        exempt = COORDINATION_ROUTES | PEOPLE_ROUTES
        if all((method, route.path) in exempt for method in methods):
            continue
        for model in _models_in(route.response_model):
            place = _names_a_place(model)
            if model in DISPLAYS_OF_A_REDUCED_SHAPE:
                continue
            if place and not issubclass(model, LeavingShape):
                unprotected.append(f"{methods} {route.path} -> {model.__name__}{place}")

    assert unprotected == [], (
        "a response model can name a project's place and does not inherit LeavingShape, so "
        f"the redaction is not applied to it: {unprotected}"
    )


def test_the_audit_sees_a_place_returned_by_a_computed_field() -> None:
    """The walk reaches a computed field's model, so the allowlist above is load-bearing.

    Without this, deleting ``EtenLocationShown`` from :data:`DISPLAYS_OF_A_REDUCED_SHAPE` could
    leave the route audit green for the wrong reason — because it never looked.
    """
    from app.models.shema_eten import EtenYearReport

    reached = _models_in(EtenYearReport)
    assert EtenLocationShown in reached
    assert _names_a_place(EtenLocationShown) == ["location"]


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


def test_every_field_a_withheld_read_reduces_is_refused_on_write() -> None:
    """*Não dá para editar o que não se vê* (OBT-528), as a property of the two lists.

    A field the read hands a reader reduced and the write lets the same reader set is a field
    they can overwrite without seeing it — the base read as ``""`` and typed over. So every
    withheld field is refused somewhere: on every record, or on a withheld one.
    """
    assert set(WITHHELD_FIELDS) <= COORDINATION_WRITES | WITHHELD_WRITES
    assert "sensitive_country" in COORDINATION_WRITES


def test_only_the_listed_routes_take_the_callers_reader() -> None:
    """**The successor of the exemption list, read off the application the server builds.**

    The reader is what lets a leaving shape carry the truth, so a route whose dependencies reach
    it is a route that may. A new one — an export, a report, a download that took the caller's
    ``Reading`` and handed it to ``browse_projects`` — would pass the route audit above, because
    its shape is a leaving shape, and ship the truth out of the system. It is red here instead,
    until somebody adds it to :data:`READER_ROUTES` and argues it.
    """
    from app.api.shema._deps import _reading

    app = create_app()
    taking = set()
    for route in app.routes:
        if not isinstance(route, APIRoute) or not route.path.startswith(PREFIX):
            continue
        if _reaches(route.dependant, _reading):
            for method in set(route.methods or ()) - {"HEAD", "OPTIONS"}:
                taking.add((method, route.path))

    assert taking == READER_ROUTES


def _builds_for_a_reader(source: Path) -> bool:
    """Whether the module calls ``read_by`` or names the reader's context key."""
    tree = ast.parse(source.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "read_by":
            return True
        if isinstance(node, ast.Name) and node.id == "READER_KEY":
            return True
    return False


def test_only_the_console_reads_build_a_shape_for_the_sessions_reader() -> None:
    """*Outside is what the export, the ETEN report, the Pulse and the leader's link already use
    — não muda*, as a property of the tree.

    A shape built with no reader is ``outside``. The two files that build one for the session
    are the cards and the record; a third — a notice, a file, a report — that reached for a
    reader would be the one path out of the system carrying the truth.
    """
    builders = sorted(
        source.name
        for package in GUARDED_PACKAGES
        for source in package.glob("*.py")
        if _builds_for_a_reader(source)
    )
    assert builders == sorted(SESSION_READS)
