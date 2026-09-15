"""The Shemá module's pure derivations — read off a record and a clock, never off a query.

``docs/shema.md`` §3.1 puts these in ``app/utils/`` rather than in ``app/services/shema/``
and gives the reason a test enforces:
``tests/test_app_boots.py::test_no_dto_module_reaches_up_into_the_service_layer`` forbids
``app/models/`` from importing ``app/services/``, and FE-44 §7's derivations are needed by
the Pydantic response models *and* by the services. ``app/utils/description_rule.py`` is the
precedent and the same shape; ``app/utils/`` is flat, so the file carries a ``shema_``
prefix rather than forming a package its siblings do not have.

**This file holds one of FE-44 §7's nine derivations, and BE-05 grows it with the other
eight.** BE-16 needed the region to write ``shema_projects.region_key`` — the column
``docs/shema.md`` §6.1 stores rather than computes, so the one predicate every scoped list
query carries stays sargable — and ``docs/shema.md`` §6.1 asks that the derivation keep
**exactly one owner**. A second copy of the country map inside a seed script is the thing
that ownership rule exists to prevent, so the file is opened here with the region in it and
nothing else. Status, progress roll-up, staleness, overall health, the period keys, the
presets and the ETEN accounting are still BE-05's, and so is vendoring
``dataJsParity.json`` and replaying it (``docs/shema.md`` §6.5).

**The country map is keyed on the export's own spellings, and that is the whole point.**
``São Tomé e Príncipe`` is Portuguese, ``East Timor`` is English, and the file mixes the two
because 127 rows were typed by different people over years. Normalising a key — trimming,
case-folding, transliterating — breaks the mapping for exactly the rows that need it most.
The map is ``src/constants/regions.ts``'s ``COUNTRY_REGION`` letter for letter.

**``other`` is not a bin to be cleaned up later.** Two records carry an empty ``location``
and land there legitimately, and a country the map does not name lands there by design
rather than by mistake — which is also why this module never falls back to a geocoder or to
the coordinates. ``docs/shema.md`` §4.9 leaves the repository's geocoding alone on purpose.
"""

from app.db.models.shema_enums import ShemaRegionKey

#: ``src/constants/regions.ts``, copied key for key. Twenty-five entries; the export also
#: names ``Laos`` and ``Vietnam``, which the frontend's map does not carry either — both
#: appear only as the second and third country of ``China, Laos, Vietnam``, so neither has
#: ever decided a region. Adding them here would be this file answering a question the
#: frontend's own map has not been asked; the two implementations must not drift.
COUNTRY_REGION: dict[str, ShemaRegionKey] = {
    "Brazil": ShemaRegionKey.SOUTH_AMERICA,
    "Peru": ShemaRegionKey.SOUTH_AMERICA,
    "Colombia": ShemaRegionKey.SOUTH_AMERICA,
    "Mexico": ShemaRegionKey.NORTH_AMERICA,
    "Panama": ShemaRegionKey.NORTH_AMERICA,
    "United States": ShemaRegionKey.NORTH_AMERICA,
    "Canada": ShemaRegionKey.NORTH_AMERICA,
    "Egypt": ShemaRegionKey.AFRICA,
    "Mozambique": ShemaRegionKey.AFRICA,
    "South Africa": ShemaRegionKey.AFRICA,
    "South Sudan": ShemaRegionKey.AFRICA,
    "Sudan": ShemaRegionKey.AFRICA,
    "Guinea-Bissau": ShemaRegionKey.AFRICA,
    "São Tomé e Príncipe": ShemaRegionKey.AFRICA,
    "Togo": ShemaRegionKey.AFRICA,
    "Uganda": ShemaRegionKey.AFRICA,
    "India": ShemaRegionKey.ASIA,
    "China": ShemaRegionKey.ASIA,
    "Indonesia": ShemaRegionKey.ASIA,
    "East Timor": ShemaRegionKey.ASIA,
    "Nepal": ShemaRegionKey.ASIA,
    "Australia": ShemaRegionKey.OCEANIA,
    "Papua New Guinea": ShemaRegionKey.OCEANIA,
    "Fiji": ShemaRegionKey.OCEANIA,
    "Micronesia": ShemaRegionKey.OCEANIA,
}

#: What a ``location`` that names nothing derives to. ``src/constants/regions.ts``'s
#: ``FALLBACK_REGION``.
FALLBACK_REGION = ShemaRegionKey.OTHER


def countries_named(location: str) -> tuple[str, ...]:
    """Every country the free-text ``location`` names, in the order it names them.

    ``location`` is free text and five records name more than one country — ``China, Laos,
    Vietnam``, ``Canada, United States``, ``India, Nepal``, ``Mexico, United States``,
    ``Colombia, Peru``. The frontend has no function for this: ``getCountry`` takes the
    first and the region follows from it alone (§7.6), which is right for a region and
    wrong for a safety question. **BE-16's fail-closed flag asks about all of them**, so the
    split lives here, once, beside the reader that uses its first element — rather than
    twice, with a seed script holding its own copy of what a comma means.

    The separator is the comma and only the comma. ``&`` and ``/`` separate people in this
    export, never places, and the record's own fields keep them unsplit for that reason.
    """
    return tuple(part.strip() for part in location.split(",") if part.strip())


def country_of(location: str) -> str:
    """The country the region is derived from: the first one named, or ``""``.

    FE-44 §7.6's ``getCountry``, which is ``location.split(",")[0].trim()``. Two records
    have an empty ``location`` and this answers ``""`` for both — a state, not a gap, and
    the one the fallback region exists for.
    """
    named = countries_named(location)
    return named[0] if named else ""


def region_of(location: str) -> ShemaRegionKey:
    """The region key a record belongs to, derived from the first country of its location.

    FE-44 §7.6's ``getRegion``. Never stored as a membership and never typed by hand: the
    column exists so the scoped query has an index, and this function is what writes it.
    """
    return COUNTRY_REGION.get(country_of(location), FALLBACK_REGION)
