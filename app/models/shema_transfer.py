"""What leaves in an export and what an import answers — BE-14's shapes, and the file itself.

**The export is a report that leaves, not a backup that returns** (FE-44 §8.4). Its row is an
**allowlist**: :class:`ExportedProject` declares the 24 fields of the console's
``ExportedProject`` and nothing else, so a column added to ``shema_projects`` later stays *out*
of the file until somebody declares it here — the inverse of a denylist, and deliberate. Personal
contacts, people's names, media and materials are not declared at all; the prayer requests arrive
as texts ``_consent.py`` already let through; the notes are asked of ``can_export_notes`` under
``publico``, which answers no.

**The row is a leaving shape, built for nobody.** It inherits
:class:`~app.models.shema_privacy.LeavingShape` and is validated straight off the
``ShemaProject`` row with no reader, which is ``outside``: a withheld project leaves with the
region key where the place was, an empty base and ``locationWithheld: true`` — **whoever
exports**, the region's own coordinator included, because a file is what leaves the system.
Nothing in this module can build one for a reader; ``tests/test_shema/test_privacy_owners.py``
holds that as a property of the tree.

**The header is written here, with the file, and it is addressed.** What the file contains, when
it was generated and by whom, over which scope, that it is confidential and which export record
it is — on every file. How many places were withheld is a line for coordination only
(GATE-04, 1.3): the service decides who the exporter is and passes the count or ``None``, and a
``None`` prints nothing, so an ``obtLab`` export and a coordinator's export of a scope with no
sensitive project read the same.

**The words are here and not in the service**, for ``shema_prayer.py``'s reason: a file that
leaves has no i18next to render it, so the sentences are the console's catalogue values
(``export_*`` and the column labels, in ``pt-BR`` and ``en``), copied rather than re-derived.
**The cells are data, not labels**: dates are ISO days, status and health are FE-44's frozen
vocabulary values, and a withheld row's location is the region key the leaving shape put there —
a second copy of the console's label tables would be one more thing to drift.

**Two CSV rules the console already carried, and the server inherits** (FE-44 §9.12): every cell
that a spreadsheet would read as a formula is neutralised, and the file opens with a BOM so a
non-Latin name survives Excel. The separator is ``;``, the ``pt-BR`` default.
"""

from __future__ import annotations

import enum
import json
import re
from collections.abc import Callable
from datetime import date, datetime
from typing import Any, Final, NamedTuple

from pydantic import (
    AliasGenerator,
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
)
from pydantic.alias_generators import to_camel

from app.db.models.shema_enums import ShemaHealthLevel, ShemaProjectStatus
from app.models.shema_prayer import PulseLanguage
from app.models.shema_privacy import LeavingShape, ShemaAudience
from app.utils.shema_derivations import OverallHealth, overall_health, project_status

#: Who a file is written for — FE-44's ``EXPORT_AUDIENCE``. A file gets e-mailed onward, so it is
#: ``publico``, the audience the product cannot take anything back from.
EXPORT_AUDIENCE: Final = ShemaAudience.PUBLICO

#: Read models speak camelCase outward and snake_case inward — BE-05's ``_OUTWARD``.
_OUTWARD = ConfigDict(
    from_attributes=True,
    populate_by_name=True,
    alias_generator=AliasGenerator(serialization_alias=to_camel),
)


class ExportFormat(enum.StrEnum):
    """The formats the server writes — FE-44 §9.12's ``json|csv``, and no more yet."""

    JSON = "json"
    CSV = "csv"


class ExportedProject(LeavingShape):
    """One project as it leaves in a file — FE-44 §8.4's ``ExportedProject``, 24 keys.

    Validated off the row with no reader, so the boundary reduces :attr:`location` and
    :attr:`base` before anything reads them. The three values a row cannot answer —
    :attr:`open_needs`, :attr:`shared_prayer_requests` and :attr:`exported_notes` — are attached by
    ``app/services/shema/export_projects.py`` with ``model_copy``, which keeps the reduction.

    ``status`` and ``overallHealth`` are FE-44 §7's derivations, computed by their one owner
    (``app/utils/shema_derivations.py``) from fields read off the row and never emitted: the
    stored status, the four dimensions and :attr:`last_progress_date`, which the status rule does
    not read and which is declared only because the derivations take one shape for all nine.
    """

    model_config = _OUTWARD

    id: str
    language_name: str = ""
    language_code: str = ""
    bridge_language: str = ""
    vitality_status: str = ""
    speaker_count: str = ""
    #: ``team`` on the row — one column since BE-02. Emptied by the boundary for a withheld row.
    base: str = Field(default="", validation_alias="team")
    #: The place, or the region key where the place is withheld.
    location: str = ""
    objective: list[str] = Field(default_factory=list)
    translation_type: list[str] = Field(default_factory=list)
    start_date: date | None = None
    deadline: date | None = None
    translated_units: int = 0
    community_checked_units: int = 0
    approved_units: int = 0
    total_units: int = 0
    open_needs: int = 0
    shared_prayer_requests: list[str] = Field(default_factory=list)
    last_updated: date | None = None
    #: **Named so a row cannot fill it.** ``from_attributes`` reads a field by its own name, and
    #: the row has no ``exported_notes`` — so the notes are never in this object unless the
    #: service put them there, which it does only when ``can_export_notes`` says the file's
    #: audience may carry them. Emitted as ``notes``, and left out of the row when ``None``.
    exported_notes: str | None = Field(default=None, serialization_alias="notes")

    status: ShemaProjectStatus | None = Field(default=None, exclude=True)
    health_emotional: ShemaHealthLevel | None = Field(default=None, exclude=True)
    health_relational: ShemaHealthLevel | None = Field(default=None, exclude=True)
    health_spiritual: ShemaHealthLevel | None = Field(default=None, exclude=True)
    health_physical: ShemaHealthLevel | None = Field(default=None, exclude=True)
    last_progress_date: date | None = Field(default=None, exclude=True)

    @field_validator("objective", "translation_type", mode="before")
    @classmethod
    def _tolerate_a_null_array(cls, value: Any) -> Any:
        """A JSON array column written NULL reads as the empty list, as on the card."""
        return [] if value is None else value

    @computed_field(alias="sensitiveCountry")  # type: ignore[prop-decorator]
    @property
    def flagged(self) -> bool:
        """``sensitiveCountry`` — the same bit as ``locationWithheld``, under the contract's name.

        Read off the marker and not off the flag, which the boundary never emits: on a row the two
        are one fact, and on anything that could not answer the marker is the fail-closed one.
        """
        return self.location_withheld

    @computed_field(alias="status")  # type: ignore[prop-decorator]
    @property
    def derived_status(self) -> ShemaProjectStatus:
        """FE-44 §7.1: the stored status when it is one of the six, else derived from progress."""
        return project_status(self)

    @computed_field(alias="overallHealth")  # type: ignore[prop-decorator]
    @property
    def health(self) -> OverallHealth:
        """FE-44 §7.4: the worst of the four, and ``na`` when none was rated."""
        return overall_health(self)

    def as_row(self) -> dict[str, Any]:
        """The row as the file carries it, camelCase, ``notes`` only when it was allowed in."""
        row = self.model_dump(mode="json", by_alias=True)
        if self.exported_notes is None:
            row.pop("notes", None)
        return row


class ExportMeta(BaseModel):
    """The file's header, as data — what the JSON carries under ``meta``.

    ``locationsWithheld`` and ``withheldNote`` are ``None`` for everybody who is not
    coordination and for a file with nothing withheld, and the two cases read the same on
    purpose: the header says something only when it has something to say to this reader.
    """

    model_config = _OUTWARD

    export_id: str
    contains: str
    confidential: str
    generated_at: datetime
    generated_by: str
    #: ``None`` is every region, as ``regionScope`` is on the session (FE-44 §9.13).
    scope: list[str] | None
    format: ExportFormat
    project_count: int
    locations_withheld: int | None = None
    withheld_note: str | None = None


class _ExportCopy(NamedTuple):
    contains: str
    confidential: str
    generated: str
    scope: str
    everywhere: str
    record: str
    withheld_one: str
    withheld_many: str
    yes: str
    no: str
    columns: dict[str, str]


_COPY: Final[dict[PulseLanguage, _ExportCopy]] = {
    PulseLanguage.PT_BR: _ExportCopy(
        contains=(
            "Projetos do Ecossistema Shemá — identidade, escopo, progresso, saúde, necessidades "
            "em aberto e pedidos de oração compartilhados. Sem contatos pessoais, notas internas "
            "nem mídias."
        ),
        confidential=(
            "Confidencial — uso interno da coordenação. Não repasse sem combinar com a equipe "
            "responsável."
        ),
        generated="Gerado em {when} por {who}",
        scope="Escopo: {scope}",
        everywhere="todas as regiões",
        record="Registro deste arquivo: {id}",
        withheld_one=(
            "{count} projeto em país sensível sai com local e base recolhidos — no lugar do "
            "local, a região."
        ),
        withheld_many=(
            "{count} projetos em países sensíveis saem com local e base recolhidos — no lugar do "
            "local, a região."
        ),
        yes="Sim",
        no="Não",
        columns={
            "id": "ID",
            "languageName": "Nome da Língua",
            "languageCode": "Código ISO",
            "bridgeLanguage": "Língua Ponte",
            "vitalityStatus": "Vitalidade",
            "speakerCount": "Número de falantes",
            "base": "Base",
            "location": "País / Região / Localização",
            "sensitiveCountry": "País sensível",
            "objective": "Objetivo",
            "translationType": "Tipo de Tradução",
            "status": "Status",
            "startDate": "Data de início",
            "deadline": "Prazo de entrega",
            "translatedUnits": "Traduzido",
            "communityCheckedUnits": "Checado",
            "approvedUnits": "Aprovado",
            "totalUnits": "Total Planejado",
            "overallHealth": "Saúde",
            "openNeeds": "Necessidades em aberto",
            "sharedPrayerRequests": "Pedidos de oração compartilhados",
            "lastUpdated": "Última atualização",
        },
    ),
    PulseLanguage.EN: _ExportCopy(
        contains=(
            "Shemá Ecosystem projects — identity, scope, progress, health, open needs and shared "
            "prayer requests. No personal contacts, internal notes or media."
        ),
        confidential=(
            "Confidential — for the coordination's internal use. Do not pass it on without "
            "agreeing with the responsible team."
        ),
        generated="Generated at {when} by {who}",
        scope="Scope: {scope}",
        everywhere="every region",
        record="Record of this file: {id}",
        withheld_one=(
            "{count} project in a sensitive country leaves with its location and base withheld "
            "— the region shown in place of the location."
        ),
        withheld_many=(
            "{count} projects in sensitive countries leave with their locations and bases "
            "withheld — the region shown in place of the location."
        ),
        yes="Yes",
        no="No",
        columns={
            "id": "ID",
            "languageName": "Language name",
            "languageCode": "ISO code",
            "bridgeLanguage": "Bridge language",
            "vitalityStatus": "Vitality",
            "speakerCount": "Speakers (estimated)",
            "base": "Base",
            "location": "Country / Region",
            "sensitiveCountry": "Sensitive country",
            "objective": "Objective",
            "translationType": "Translation type",
            "status": "Status",
            "startDate": "Start date",
            "deadline": "Deadline",
            "translatedUnits": "Translated",
            "communityCheckedUnits": "Checked",
            "approvedUnits": "Approved",
            "totalUnits": "Total planned",
            "overallHealth": "Health",
            "openNeeds": "Open needs",
            "sharedPrayerRequests": "Shared prayer requests",
            "lastUpdated": "Last update",
        },
    ),
}

#: Every sentence a file may open with — how an import recognises the CSV it is handed.
OPENING_SENTENCES: Final[tuple[str, ...]] = tuple(copy.contains for copy in _COPY.values())


def export_copy(language: PulseLanguage) -> tuple[str, str]:
    """What the file contains and that it is confidential, in ``language`` — the header's data."""
    copy = _COPY[language]
    return copy.contains, copy.confidential


def withheld_sentence(count: int | None, language: PulseLanguage) -> str | None:
    """The withheld line for ``count`` rows, or ``None`` — never a sentence about zero."""
    if not count:
        return None
    copy = _COPY[language]
    template = copy.withheld_one if count == 1 else copy.withheld_many
    return template.format(count=count)


def export_filename(day: date, file_format: ExportFormat) -> str:
    """``shema-projetos-<day>.<ext>`` — the console's own name, with no place and no person."""
    return f"shema-projetos-{day.isoformat()}.{file_format.value}"


def _stamp(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%d %H:%M UTC")


def render_json(meta: ExportMeta, rows: list[ExportedProject]) -> str:
    """``{meta, projects}`` — the console's JSON export, with the server's provenance in ``meta``.

    ``ensure_ascii=False``, so ``Ngäbere`` is ``Ngäbere`` in the file and not an escape sequence
    a person reading it has to decode.
    """
    document = {
        "meta": meta.model_dump(mode="json", by_alias=True),
        "projects": [row.as_row() for row in rows],
    }
    return json.dumps(document, ensure_ascii=False, indent=2) + "\n"


CSV_BOM: Final = "﻿"
CSV_SEPARATOR: Final = ";"
#: What a spreadsheet reads as the start of a formula — the console's ``FORMULA_LEAD``.
_FORMULA_LEAD = re.compile(r"^[=+\-@\t\r]")
_NEEDS_QUOTING = re.compile(r'[";\n\r]')
#: How a list lands in one cell — the console's ``CSV_JOIN``.
CSV_JOIN: Final = " · "


def csv_cell(value: str | int | None) -> str:
    """One cell: a formula lead neutralised with ``'``, then quoted if it has to be.

    The console's ``csvCell``, and the order is the point: the guard is applied to the text
    before quoting, so a quoted cell cannot smuggle a lead past it.
    """
    text = "" if value is None else str(value)
    guarded = f"'{text}" if _FORMULA_LEAD.match(text) else text
    if _NEEDS_QUOTING.search(guarded):
        return '"' + guarded.replace('"', '""') + '"'
    return guarded


def _day(value: date | None) -> str:
    return "" if value is None else value.isoformat()


_CSV_CELLS: Final[dict[str, Callable[[ExportedProject, _ExportCopy], str | int]]] = {
    "id": lambda row, _: row.id,
    "languageName": lambda row, _: row.language_name,
    "languageCode": lambda row, _: row.language_code,
    "bridgeLanguage": lambda row, _: row.bridge_language,
    "vitalityStatus": lambda row, _: row.vitality_status,
    "speakerCount": lambda row, _: row.speaker_count,
    "base": lambda row, _: row.base,
    "location": lambda row, _: row.location,
    "sensitiveCountry": lambda row, copy: copy.yes if row.flagged else copy.no,
    "objective": lambda row, _: CSV_JOIN.join(row.objective),
    "translationType": lambda row, _: CSV_JOIN.join(row.translation_type),
    "status": lambda row, _: row.derived_status.value,
    "startDate": lambda row, _: _day(row.start_date),
    "deadline": lambda row, _: _day(row.deadline),
    "translatedUnits": lambda row, _: row.translated_units,
    "communityCheckedUnits": lambda row, _: row.community_checked_units,
    "approvedUnits": lambda row, _: row.approved_units,
    "totalUnits": lambda row, _: row.total_units,
    "overallHealth": lambda row, _: row.health.value,
    "openNeeds": lambda row, _: row.open_needs,
    "sharedPrayerRequests": lambda row, _: CSV_JOIN.join(row.shared_prayer_requests),
    "lastUpdated": lambda row, _: _day(row.last_updated),
}


def render_csv(meta: ExportMeta, rows: list[ExportedProject], language: PulseLanguage) -> str:
    """The console's CSV: the header lines, a blank line, the column names, one line per row.

    The provenance lines come first so a file cut short still says what it is. Every line —
    header included — goes through :func:`csv_cell`, because the exporter's name and the
    request texts are typed by people and a leading ``=`` in either is a formula to Excel.
    """
    copy = _COPY[language]
    scope = copy.everywhere if meta.scope is None else ", ".join(meta.scope)
    preamble: list[list[str | int | None]] = [
        [meta.contains],
        [copy.generated.format(when=_stamp(meta.generated_at), who=meta.generated_by)],
        [copy.scope.format(scope=scope)],
        [meta.confidential],
        [copy.record.format(id=meta.export_id)],
    ]
    if meta.withheld_note is not None:
        preamble.append([meta.withheld_note])
    preamble.append([])
    header: list[str | int | None] = [copy.columns[key] for key in _CSV_CELLS]
    cells: list[list[str | int | None]] = [
        [cell(row, copy) for cell in _CSV_CELLS.values()] for row in rows
    ]
    lines = [*preamble, header, *cells]
    body = "\r\n".join(CSV_SEPARATOR.join(csv_cell(value) for value in line) for line in lines)
    return f"{CSV_BOM}{body}\r\n"


class ImportResult(BaseModel):
    """``POST /import/projects``'s answer — FE-44 §9.12's ``{applied}``, plus what was ignored.

    ``ignoredFields`` is additive, and it is the import's half of *the withholding is visible*: a
    file that carried a health history, a media list or an authorization the server does not take
    from a file is told so by name, rather than left to believe everything it held went in.
    """

    model_config = ConfigDict(populate_by_name=True, alias_generator=to_camel)

    applied: int
    ignored_fields: list[str] = Field(default_factory=list)


class ImportRefusal(enum.StrEnum):
    """Why a file was refused — the five keys the console's import dialog already names."""

    INVALID_JSON = "import_invalid_json"
    IS_EXPORT = "import_is_export"
    NOT_LIST = "import_not_list"
    BAD_RECORD = "import_bad_record"
    DUPLICATE_ID = "import_duplicate_id"
