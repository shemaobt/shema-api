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
* :func:`withheld_note` — the collection-level announcement, addressed to a reader, because
  since OBT-528 only coordination is told how many (GATE-04);
* :func:`log_reference` and :func:`searchable_text` — the two paths that are not payloads at
  all, and the two this module would otherwise leak through unwatched;
* :func:`derive_region` — the write path's one question about ``location``, which lives here
  because ``location`` lives here (BE-06; the function's own docstring carries the trade);
* :func:`unwritable_fields` — the write path's other question (OBT-528): which of the fields a
  save sent this reader may not write, because a field that is withheld from a reader is not
  one that reader may type over;
* :func:`never_lowered` — the import's one-way rule on the flag (BE-14): a file may raise it and
  may not clear it;
* :func:`reads_the_truth` — the one spelling of *this reader reads this project as it is*
  (OBT-556), which every path that is not a shape asks instead of writing the condition out;
* :func:`withheld_from`, :func:`free_text_as_read`, :func:`assessments_as_read` and
  :func:`need_text_as_written` — the four paths OBT-556 found a withheld record's text leaving
  by: the conflict a save meets, the needs and the assessments nested in the record, the
  assessment history, and the needs a save sends back.

**This is the only file in** ``app/services/shema/`` **and** ``app/api/shema/`` **allowed to
read the guarded columns.** ``tests/test_shema/test_privacy_owners.py`` globs both packages
and fails on a second reader, with an allowlist that is one entry long today and that a later
issue extends by writing a line somebody has to justify. It is the mechanism ``_scope.py``
uses for the module's only ``select(ShemaProject)``, for the same stated reason: a rule
applied per endpoint is a rule the next endpoint forgets; a glob is not.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from collections.abc import Set as AbstractSet
from typing import Any, Final

from app.db.models.shema import ShemaProject
from app.db.models.shema_enums import ShemaRegionKey
from app.models.shema_need import ShemaNeedWrite
from app.models.shema_privacy import (
    COORDINATION_WRITES,
    WITHHELD_FIELDS,
    WITHHELD_WRITES,
    LeavingShape,
    ShemaReader,
)
from app.models.shema_record import ShemaHealthAssessmentEntry, ShemaProjectRecord
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


def withheld_note(records: Iterable[LeavingShape], reader: ShemaReader) -> int | None:
    """How many of ``records`` are withheld, announced to ``reader`` — or ``None``.

    **Announced to coordination only** (GATE-04 1.3, OBT-528). The caller says who the
    announcement is for, and that is not always who the rows were built for: the Projetos screen
    announces to its own caller, and a file a coordinator exports carries rows built for
    ``outside`` with a header addressed to the coordinator (BE-14). Anybody else is told
    nothing — which hides nothing, because each row still carries its own ``locationWithheld``
    (BE-04's *make the withholding visible*); GATE-04 decided the notice, not the bit.

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
    if reader is not ShemaReader.COORDINATION:
        return None
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


def searchable_text(project: ShemaProject, reader: ShemaReader) -> str:
    """The text a search may match this project on, for ``reader``.

    **A search is an output path, and the cheapest one to forget**, because it returns no
    location at all — it returns whether a query matched. A caller who may list a project but
    not learn where it is can type a country and read the answer off the result count, and
    every row they *cannot* see answers the same question by being absent. So the haystack a
    withheld project offers a reader who is not coordination holds nothing it is not already
    willing to say in that reader's payload: its language, its bridge language and its region.
    A coordination reader reads the place on the card, and finds the card by it (OBT-528).

    The names of people are not in either haystack. They are not this rule's to reduce — FE-44
    §8.1 gates the three *contact* fields and says nothing about ``team_leader`` or ``mentor``
    — and putting them here would be inventing a second rule in the file that argues against
    inventing rules surface by surface. ``docs/shema.md`` §9.4's gate is where that question
    belongs.
    """
    fields = [project.language_name, project.bridge_language, project.region_key.value]
    if reads_the_truth(project, reader):
        fields.extend([project.location, project.location2 or "", project.team])
    return " ".join(part for part in fields if part)


def reads_the_truth(project: ShemaProject, reader: ShemaReader) -> bool:
    """Whether ``reader`` reads ``project`` as it is: coordination does, and so does everybody on
    a project whose place is not withheld.

    :class:`~app.models.shema_privacy.LeavingShape` answers the same question for the fields a
    shape declares. Everything that is not a shape — the search's haystack, the text nested in a
    record, the assessment history, a received Pulse, the conflict a save meets — asks this one
    function instead of writing the condition out (OBT-556), so the paths cannot disagree about
    when a reader is handed the reduction.
    """
    return reader is ShemaReader.COORDINATION or not is_withheld(project)


def withheld_from(project: ShemaProject, reader: ShemaReader) -> frozenset[str]:
    """The fields a read of ``project`` hands ``reader`` reduced — empty when it reads the truth.

    What the conflict a save meets may not name (OBT-556). A 409 that tells a reader the place or
    the notes moved, and who moved them, says what the record they read does not; so the list is
    the boundary's own, and the conflict and the record cannot disagree about it.
    """
    return frozenset() if reads_the_truth(project, reader) else frozenset(WITHHELD_FIELDS)


def assessments_as_read(
    project: ShemaProject,
    reader: ShemaReader,
    entries: Sequence[ShemaHealthAssessmentEntry],
) -> list[ShemaHealthAssessmentEntry]:
    """The assessment history as ``reader`` reads it: on a withheld project, with no notes.

    The health notes are :data:`~app.models.shema_privacy.FREE_TEXT_FIELDS`' — and the flat
    ``health_notes`` on the record is only the projection of the newest entry, so emptying it and
    serving the entries whole would be a redaction a scroll undoes. The note per dimension goes
    with the blob it is compiled into; the ratings, the day and who assessed stay, because they
    name no place.
    """
    if reads_the_truth(project, reader):
        return list(entries)
    return [entry.model_copy(update={"notes": "", "dimension_notes": None}) for entry in entries]


def free_text_as_read(
    project: ShemaProject, reader: ShemaReader, record: ShemaProjectRecord
) -> dict[str, Any]:
    """What a record's nested free text becomes for ``reader`` — an update, or nothing.

    The record's own four are reduced by the shape it is built as. Its needs and its assessments
    arrive on it afterwards, by ``model_copy`` and not through the boundary, so their text is
    held back here, in ``_consent.request_as_read``'s mould: a reader who reads the truth gets
    ``{}``, and anybody else every need's description as ``""`` and the history without notes.
    """
    if reads_the_truth(project, reader):
        return {}
    needs = [need.model_copy(update={"description": ""}) for need in record.needs_items]
    history = record.health_history
    if history is not None:
        history = assessments_as_read(project, reader, history)
    return {"needs_items": needs, "health_history": history}


#: The one name a refused need text is given, in the client's spelling.
NEED_TEXT: Final = "needsItems.description"


def need_text_as_written(
    project: ShemaProject, rows: Sequence[ShemaNeedWrite], reader: ShemaReader
) -> tuple[list[ShemaNeedWrite], bool]:
    """``rows`` as ``reader`` may write them on ``project``, and whether one types over unseen text.

    The nested half of :func:`unwritable_fields` (OBT-556), **read off the values where that one
    reads the names**, for the reason ``_consent.undecidable_shares`` gives: the console sends
    every need back whole, description included, on every save of the needs. A reader who is not
    coordination was handed a withheld record's descriptions as ``""``, so a row that sends ``""``
    back is that reading returned, and it is dropped from what the row writes — the description
    stays, and the share does not fall with it. A row that sends anything else is a text typed
    over one the reader cannot see, which the caller refuses. Comparing with the ``""`` they were
    given, and never with the stored text, is what keeps the answer from being an oracle.

    A row with no id is a new need, and its author sees what they type: there is nothing to
    overwrite, which is OBT-528's own exception for a create.
    """
    if reads_the_truth(project, reader):
        return list(rows), False
    kept: list[ShemaNeedWrite] = []
    typed = False
    for row in rows:
        if row.id is None or "description" not in row.model_fields_set:
            kept.append(row)
        elif row.description:
            typed = True
            kept.append(row)
        else:
            kept.append(
                ShemaNeedWrite.model_construct(
                    _fields_set=row.model_fields_set - {"description"}, **row.model_dump()
                )
            )
    return kept, typed


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


def unwritable_fields(
    project: ShemaProject, sent: AbstractSet[str], reader: ShemaReader
) -> list[str]:
    """The fields of ``sent`` that ``reader`` may not write on ``project`` — sorted, or empty.

    **Não dá para editar o que não se vê** (OBT-528), in two tiers:

    * on **every** record, the place, the flag and the reason beside it
      (:data:`~app.models.shema_privacy.COORDINATION_WRITES`) are coordination's — moving a
      project's location moves its region and can move it into a sensitive country, and the
      flag is the decision the whole rule rests on;
    * on a **withheld** record, the base and the contacts too
      (:data:`~app.models.shema_privacy.WITHHELD_WRITES`), because the reader was given ``""``
      for each and a value typed there would overwrite a truth they cannot see.

    It answers from the **names** the payload set and never from their values, so the refusal
    is not an oracle: comparing a sent base with the stored one would tell a reader who may not
    see it whether they guessed it. Coordination may write all of them.
    """
    if reader is ShemaReader.COORDINATION:
        return []
    refused = set(sent) & COORDINATION_WRITES
    if is_withheld(project):
        refused |= set(sent) & WITHHELD_WRITES
    return sorted(refused)


def never_lowered(project: ShemaProject, sent: Mapping[str, Any]) -> dict[str, Any]:
    """``sent`` without a ``False`` for the flag of a record that is withheld — the import's rule.

    **A file may raise the flag and may never lower it** (BE-14). Raising protects and lowering
    exposes, so only one of the two directions is allowed to happen by the momentum of a bulk
    operation: a backup taken before somebody flagged a project, imported back, would otherwise
    publish that project's place in every file and on every card from then on, and nobody would
    have decided it. BE-16's Notion import holds the same line for the same reason
    (``docs/shema.md`` §9.5). Coordination still clears a flag one record at a time, on the record,
    where the decision is a person's.

    ``sent`` is a write's fields by name; the answer is the same mapping, less the flag when it
    would have cleared it. The caller says what it dropped.
    """
    kept = dict(sent)
    if is_withheld(project) and kept.get("sensitive_country") is False:
        del kept["sensitive_country"]
    return kept
