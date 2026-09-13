"""The sensitive-country owner on the service side — ``docs/shema.md`` §6.4's first row.

Some of these 127 projects are in places where being identified as involved in Bible
translation is a real risk to real people. That is a property of the system and not a
checkbox on a screen (the ecosystem's ``CLAUDE.md`` §6.1), and this module is the half of it
that lives where the queries are.

**The rule itself is not here, and that is deliberate.** It is in
``app/models/shema_privacy.py``, applied by :class:`~app.models.shema_privacy.LeavingShape`
in a model validator, because a rule a service has to *call* is a rule the next service
forgets, while a rule a response model *inherits* is applied by the act of declaring a field.
That module's docstring carries the argument and the one reason the rule could not live in
this file: ``app/models/`` may not import ``app/services/``.

**What is here is the other half — the one this side must own.** A ``Select`` cannot inherit
a validator, so the three things a query-side caller needs are:

* :func:`is_withheld` — the predicate, for a decision taken before any shape exists
  (``_media_sharing.py`` composes with it);
* :func:`withheld_note` — the collection-level announcement, so a file that reduced rows
  says how many;
* :func:`log_reference` and :func:`searchable_text` — the two paths that are not payloads at
  all, and the two this module would otherwise leak through unwatched;
* :func:`derive_region` — the write path's one question about ``location``, which lives here
  because ``location`` lives here (BE-06; the function's own docstring carries the trade).

**This is the only file in** ``app/services/shema/`` **and** ``app/api/shema/`` **allowed to
read the guarded columns.** ``tests/test_shema/test_privacy_owners.py`` globs both packages
and fails on a second reader, with an allowlist that is one entry long today and that a later
issue extends by writing a line somebody has to justify. It is the mechanism ``_scope.py``
uses for the module's only ``select(ShemaProject)``, for the same stated reason: a rule
applied per endpoint is a rule the next endpoint forgets; a glob is not.
"""

from __future__ import annotations

from collections.abc import Iterable

from app.db.models.shema import ShemaProject
from app.db.models.shema_enums import ShemaRegionKey
from app.models.shema_privacy import LeavingShape
from app.utils.shema_derivations import get_region


def is_withheld(project: ShemaProject) -> bool:
    """Whether this project's place is withheld from everything that leaves coordination.

    The single reader of ``sensitive_country``, which BE-02 made the authoritative column of
    the pair: ``sensitivity`` beside it is the export's free text and agrees with the flag by
    accident of the data rather than by construction, so reading the text for a safety
    decision would be reading provenance as policy.

    There is no ``| None`` to fail closed over here — the column is ``NOT NULL`` with a
    ``false`` default, so a row always answers. The fail-closed floor lives one layer out, in
    :class:`~app.models.shema_privacy.LeavingShape`, where a shape can legitimately be built
    from something that is not a row.
    """
    return project.sensitive_country


def withheld_note(records: Iterable[LeavingShape]) -> int | None:
    """How many of ``records`` were reduced, or ``None`` when none were.

    **The announcement, and why it is not a count that can be zero.** FE-44 §8.1 has the map
    state in a visible overlay how many projects are being withheld, because a silently
    incomplete map is its own hazard, and §8.4 asks the export's header for the same line. But
    *"0 locations withheld"* on a file with no sensitive projects is a sentence about the
    absence of sensitive projects — it answers a question nobody asked, on every file, and the
    one time it is interesting it is the one time it should not be said. ``None`` is the
    header having nothing to add.

    It counts the **payloads**, not the rows, which is the half that cannot drift: a shape
    withheld because the rule could not be evaluated is counted exactly like one withheld
    because the flag was set, because from the reader's side they are the same fact.
    """
    total = sum(1 for record in records if record.location_withheld)
    return total or None


def log_reference(project: ShemaProject) -> dict[str, object]:
    """The only safe way to name a project in a log line or in an error message.

    **A log is read by more people and kept longer than a response body**, and it usually
    lands in a system with a different access control — so a stack trace or a warning that
    names a project's country has moved the fact this module protects into a place where
    nobody is checking who may know it. That is the failure this function exists to make
    inconvenient to cause.

    What is in the line: the id, which is the caller's own address for the record, and the
    region, which is what a withheld payload already carries. What is not: the location, the
    base, the coordinates, the contacts and the free-text ``sensitivity``. An investigator
    who is allowed to know those joins them from the id, in a place where being allowed is
    checked — the argument ``_scope.py``'s ``refuse_out_of_scope`` already makes for the
    refusal it logs, and ``shema_project_id`` is spelled the way that function spells it so
    two lines about one record join on the same field.

    ``shema_location_withheld`` is in the line on purpose: an investigator who cannot see why
    a payload was reduced will go and look at the row, which is the trip this saves them.
    """
    return {
        "shema_project_id": project.id,
        "shema_region": project.region_key.value,
        "shema_location_withheld": is_withheld(project),
    }


def searchable_text(project: ShemaProject) -> str:
    """The text a search may match this project on.

    **A search is an output path, and the cheapest one to forget**, because it returns no
    location at all — it returns whether a query matched. A caller who may list a project but
    not learn where it is can type a country and read the answer off the result count, and
    every row they *cannot* see answers the same question by being absent. So the haystack a
    withheld project offers holds nothing it is not already willing to say in a payload: its
    language, its bridge language and its region.

    The names of people are not in either haystack. They are not this rule's to reduce — FE-44
    §8.1 gates the three *contact* fields and says nothing about ``team_leader`` or ``mentor``
    — and putting them here would be inventing a second rule in the file that argues against
    inventing rules surface by surface. ``docs/shema.md`` §9.4's gate is where that question
    belongs.
    """
    fields = [project.language_name, project.bridge_language, project.region_key.value]
    if not is_withheld(project):
        fields.extend([project.location, project.location2 or "", project.team])
    return " ".join(part for part in fields if part)


def derive_region(project: ShemaProject) -> ShemaRegionKey:
    """The region this project's ``location`` puts it in — the write path's one question.

    ``shema_projects.region_key`` is a stored column maintained by whoever writes ``location``
    (``docs/shema.md`` §6.1: the region predicate rides on every scoped list query and a
    per-query derivation would make it unsargable). So the record's write has to read
    ``location`` back off the row after applying a payload — and ``location`` has **one
    reader** in this package, which is this file.

    **That is why a derivation lives in the redaction owner.** The alternative was an
    allowlist entry in ``tests/test_shema/test_privacy_owners.py`` naming the write path as a
    second reader of six guarded columns, to buy one line; the glob's own note foresees that
    entry and it is still the worse trade — a second reader is second for every column, not
    only for the one that was wanted. The rule itself is not duplicated here:
    ``app/utils/shema_derivations.get_region`` is the single owner of the country map and this
    is one call to it.
    """
    return get_region(project.location)
