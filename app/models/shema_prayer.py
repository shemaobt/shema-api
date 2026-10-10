"""What leaves the prayer area: the wall's entry, and the Prayer Pulse's file.

**The entry is a leaving shape and it is built from the project row**, which is the whole of the
sensitive-country half of BE-09 (``docs/shema.md`` §6.4, §9.3). ``location`` and ``base`` are
declared so that :class:`~app.models.shema_privacy.LeavingShape` reduces them in its own
validator, before anything serialises them: a withheld project's entry carries ``country: ""``,
an empty base and ``locationWithheld: true`` beside the ``region`` every entry carries — FE-44
§9.6's shape. The Pulse is rendered from these entries and from nothing else, so the transformation
happens once, before serialization, and the file inherits it.

**The Pulse's format is one function and nothing leans on it.** GATE-03 left it to us —
*o mais simples possível* — to be measured in a field test whose leader has not been named, so
:func:`render_prayer_pulse` is plain text, one entry after another, under the two sentences the
client asked the file itself to carry: it is for the intercessor network only, and what was sent
cannot be recalled (Karina, 22/sep, 3.1 and 3.3). Changing the format is replacing this function;
the gate, the scope and the reduction do not move.

**The words are here and not in the service**, for ``ShemaNeedLine.as_notice``'s reason: the
file prints the country, and ``tests/test_shema/test_privacy_owners.py`` reads the service
package's tree, not the type — ``app/models/`` is where a shape's rule and its sentences live.
The region names are the console's catalogue values (``continent_*`` in the PME's ``pt-BR`` and
``en``), copied rather than re-derived, as ``REGION_LABEL_KEYS`` copies the keys: a file that
leaves has no i18next to render them. **Six of the seven.** The console calls ``other``
*América Central*, and ``other`` is also where every country its map does not list and every
empty location fall (``ShemaRegionKey``, the PME's ``FALLBACK_REGION``) — so the key cannot tell
a team in Central America from a team the server could not place, and the Pulse, which cannot be
recalled, prints no place for it rather than a guess.
"""

from __future__ import annotations

import enum
from collections.abc import Sequence
from datetime import date
from typing import Final, NamedTuple

from pydantic import (
    AliasGenerator,
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
)
from pydantic.alias_generators import to_camel

from app.db.models.shema_enums import ShemaRegionKey
from app.models.shema_privacy import UNKNOWN_REGION, LeavingShape
from app.utils.shema_derivations import get_country

#: ``datetime.date`` under a second name, for the field FE-44 calls ``date``.
Day = date

#: Read models speak camelCase outward and snake_case inward — BE-05's ``_OUTWARD``.
_OUTWARD = ConfigDict(
    from_attributes=True,
    populate_by_name=True,
    alias_generator=AliasGenerator(serialization_alias=to_camel),
)

#: What an entry says when the record has no language name — ``buildPrayerRequests``'s ``"—"``.
NO_LANGUAGE: Final = "—"


class PrayerSource(enum.StrEnum):
    """Where a request came from — FE-44's ``PrayerSource``, values verbatim."""

    FORM = "Formulário"
    NEED = "Necessidade"


class PrayerRequestEntry(LeavingShape):
    """One entry of the wall — FE-44's ``PrayerRequest``, less ``audioUrl``.

    Validated off the project row, so the flag and the region are read by the boundary and never
    by the service; the request's own fields are set after, by ``model_copy``, and none of them
    names a place. ``audioUrl`` is not served: the recording column takes any string a save
    writes, and signing what it holds would let a writer mint a link to any object in the
    private bucket.
    """

    model_config = _OUTWARD

    id: str = ""
    project_id: str = ""
    language: str = Field(default="", validation_alias="language_name")

    #: Reduced by the boundary — the region key and ``""`` for a withheld project. ``location``
    #: never travels; it is what ``country`` is read from.
    location: str = Field(default="", exclude=True)
    base: str = Field(default="", validation_alias="team")

    text: str = ""
    #: ``source`` on the wire, and never under that name here: the row has a ``source`` column —
    #: the export row kept verbatim, whose ``prayerRequests`` is a fourth copy of the guarded
    #: text (``docs/shema.md`` §6.4) — and validating off the row would read it into the entry.
    prayer_source: PrayerSource = Field(default=PrayerSource.FORM, serialization_alias="source")
    answered: bool = False
    date: Day | None = None

    @field_validator("language")
    @classmethod
    def _named(cls, value: str) -> str:
        return value or NO_LANGUAGE

    @computed_field  # type: ignore[prop-decorator]
    @property
    def country(self) -> str:
        """The country the location names — ``""`` for a withheld project, FE-44 §9.6."""
        return "" if self.location_withheld else get_country(self.location)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def region(self) -> ShemaRegionKey:
        """The project's region, which travels whether or not the place does."""
        return self.region_key or UNKNOWN_REGION


class PulseLanguage(enum.StrEnum):
    """The two languages the console speaks, in its own locale spelling."""

    PT_BR = "pt-BR"
    EN = "en"


class _PulseCopy(NamedTuple):
    title: str
    network_only: str
    no_recall: str
    one: str
    many: str
    empty: str
    answered: str
    filename: str
    #: What a request of a sensitive project is headed by while coordination has registered
    #: no public name for its language (OBT-560): the boundary hands the region key in its
    #: place, and a file a person reads says it in words instead.
    sensitive_project: str
    regions: dict[ShemaRegionKey, str]


_COPY: Final[dict[PulseLanguage, _PulseCopy]] = {
    PulseLanguage.PT_BR: _PulseCopy(
        title="PULSO DE ORAÇÃO",
        network_only=(
            "Só para a rede de intercessores. Ao receber este arquivo, você se compromete a "
            "não repassá-lo."
        ),
        no_recall="Depois de enviado, o que está aqui não pode ser recolhido.",
        one="1 pedido",
        many="{count} pedidos",
        empty="Nenhum pedido autorizado para compartilhar agora.",
        answered="respondido",
        filename="pulso-de-oracao",
        sensitive_project="Projeto sensível",
        regions={
            ShemaRegionKey.SOUTH_AMERICA: "América do Sul",
            ShemaRegionKey.NORTH_AMERICA: "América do Norte",
            ShemaRegionKey.AFRICA: "África",
            ShemaRegionKey.ASIA: "Ásia",
            ShemaRegionKey.OCEANIA: "Pacífico",
            ShemaRegionKey.EUROPE: "Europa",
        },
    ),
    PulseLanguage.EN: _PulseCopy(
        title="PRAYER PULSE",
        network_only=(
            "For the intercessor network only. By receiving this file you commit not to forward it."
        ),
        no_recall="Once sent, what is here cannot be recalled.",
        one="1 request",
        many="{count} requests",
        empty="No authorized requests to share right now.",
        answered="answered",
        filename="prayer-pulse",
        sensitive_project="Sensitive project",
        regions={
            ShemaRegionKey.SOUTH_AMERICA: "South America",
            ShemaRegionKey.NORTH_AMERICA: "North America",
            ShemaRegionKey.AFRICA: "Africa",
            ShemaRegionKey.ASIA: "Asia",
            ShemaRegionKey.OCEANIA: "Pacific",
            ShemaRegionKey.EUROPE: "Europe",
        },
    ),
}


def pulse_filename(day: date, language: PulseLanguage) -> str:
    """The name the file is saved under — the day, and no project, place or person."""
    return f"{_COPY[language].filename}-{day.isoformat()}.txt"


def _counted(copy: _PulseCopy, count: int) -> str:
    if count == 0:
        return copy.empty
    return copy.one if count == 1 else copy.many.format(count=count)


def render_prayer_pulse(
    entries: Sequence[PrayerRequestEntry], *, day: date, language: PulseLanguage
) -> str:
    """The Prayer Pulse as the network reads it — **the format, and the only place it lives.**

    The two sentences come first, before any request, so a file cut short by a forward still
    says them. Each entry is the language and the country, or the region where the country is
    withheld — nothing where the region is ``other`` — then the request as the team wrote it.
    No project id: the slug is ``<language>-<place>``. No base, no date per entry: neither helps
    anybody pray, and each is one more thing a forwarded file carries.
    """
    copy = _COPY[language]
    lines = [
        f"{copy.title} · {day.isoformat()}",
        "",
        copy.network_only,
        copy.no_recall,
        "",
        _counted(copy, len(entries)),
    ]
    for entry in entries:
        place = entry.country or copy.regions.get(entry.region, "")
        unnamed = entry.language_name_withheld and entry.language == entry.region.value
        name = copy.sensitive_project if unnamed else entry.language
        heading = f"• {name} — {place}" if place else f"• {name}"
        if entry.answered:
            heading = f"{heading} ({copy.answered})"
        lines.extend(["", heading])
        lines.extend(f"  {line}" if line else "" for line in entry.text.splitlines())
    return "\n".join(lines) + "\n"


#: Request shapes speak camelCase inward and refuse a field nobody declared.
_INWARD = ConfigDict(
    populate_by_name=True,
    alias_generator=AliasGenerator(validation_alias=to_camel, serialization_alias=to_camel),
    extra="forbid",
)


class PrayerReviewEntry(BaseModel):
    """One request waiting for the coordination's release (OBT-575) — the queue's row.

    **Read by the coordination alone**, so it carries the team's text whole and the language's
    real name: the route answers nobody else. It names no place, so it is no leaving shape —
    the request's text is the coordination's to read, and the card's place is the record's.
    """

    model_config = _OUTWARD

    id: str
    project_id: str
    need_id: str | None
    language: str
    source: PrayerSource
    text: str


class PrayerRelease(BaseModel):
    """The coordination's release of one request — and, in ``text``, its edit (OBT-575).

    ``reviewed`` is the team's text as the coordination read it in the queue: a release is for
    that text, and a team that wrote another one since is a conflict rather than a text released
    unread. ``text`` omitted, or blank, releases the team's text as it stands.
    """

    model_config = _INWARD

    need_id: str | None = None
    reviewed: str = Field(min_length=1)
    text: str | None = None
