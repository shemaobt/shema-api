"""The sensitive-country list on the wire — what the Admin reads and sends back whole (OBT-616).

``GET`` and ``PUT /api/shema/sensitive-countries``, both the Admin's. One shape each way, camelCase
by alias like the module's other shapes; the list travels whole because the screen edits it whole,
and a body that names a country is the country's name and its spellings and nothing else.

**No field is called** ``country``. ``tests/test_shema/test_privacy_owners.py`` reads a field of
that name as a project's place, and this list names no project — a country here is the Admin's
vocabulary, not where somebody is.

**The body is refused, not repaired, where repairing would change what the list matches.** Blank
spellings are dropped and repeats collapse, because they match nothing; a blank name, a comma, or
one spelling that names two countries is a 422 naming the problem. A comma, because ``location`` is
split on commas (``countries_named``) and a name holding one could never match a part of it. Two
countries sharing a spelling, because the place that writes it would be read as either.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.utils.shema_derivations import spelling_keys

_REQUEST = ConfigDict(populate_by_name=True, extra="forbid")
_RESPONSE = ConfigDict(populate_by_name=True)

#: The longest name or spelling the column holds.
NAME_MAX = 120


def _no_comma(value: str) -> str:
    if "," in value:
        raise ValueError("a country's name or spelling has no comma: the place is split on commas")
    return value


class SensitiveCountry(BaseModel):
    """One listed country: its name in the list's words, and the other ways a place may write it."""

    model_config = _RESPONSE

    name: str
    spellings: list[str] = Field(default_factory=list)


class SensitiveCountryList(BaseModel):
    """The list as the Admin reads it, ordered by name — accents aside."""

    model_config = _RESPONSE

    countries: list[SensitiveCountry] = Field(default_factory=list)


class SensitiveCountryWrite(BaseModel):
    """One country of the list the Admin sends."""

    model_config = _REQUEST

    name: str = Field(min_length=1, max_length=NAME_MAX)
    spellings: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("name")
    @classmethod
    def _a_name(cls, value: str) -> str:
        name = value.strip()
        if not name:
            raise ValueError("a country needs a name")
        return _no_comma(name)

    @field_validator("spellings")
    @classmethod
    def _spellings(cls, values: list[str]) -> list[str]:
        kept: list[str] = []
        for value in values:
            spelling = value.strip()
            if not spelling or spelling in kept:
                continue
            if len(spelling) > NAME_MAX:
                raise ValueError(f"a spelling is at most {NAME_MAX} characters")
            kept.append(_no_comma(spelling))
        return kept


class SensitiveCountryListWrite(BaseModel):
    """``PUT /sensitive-countries`` — the whole list, as it is to stand."""

    model_config = _REQUEST

    countries: list[SensitiveCountryWrite] = Field(max_length=250)

    @model_validator(mode="after")
    def _one_country_per_spelling(self) -> SensitiveCountryListWrite:
        owner: dict[str, str] = {}
        named: set[str] = set()
        for country in self.countries:
            if country.name in named:
                raise ValueError(f"{country.name!r} is on the list twice")
            named.add(country.name)
            for spelling in (country.name, *country.spellings):
                for key in spelling_keys(spelling):
                    other = owner.setdefault(key, country.name)
                    if other != country.name:
                        raise ValueError(
                            f"{spelling!r} names two countries on the list: "
                            f"{other!r} and {country.name!r}"
                        )
        return self
