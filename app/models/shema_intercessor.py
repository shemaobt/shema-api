"""The network on the wire — and the two places the frozen shape deliberately does not hold.

FE-44 §5.5 freezes ``Intercessor`` as ``{id, name, country, contact, addedAt}``. **The
collection shapes here carry no** ``contact``, and that is this issue's answer to its own last
DoD line: *no endpoint returns bulk contact details without a specific, justified need*. The
issue's sentence is sharper than the DoD's — *a directory endpoint that returns every phone
number in one call is a data-loss incident waiting for one compromised session* — and it is a
statement about the **plural**, which no per-role guard fixes: the bulk read is the hazard,
whoever is holding the session.

So the list carries ``contactChannel`` and ``contactHint`` (``app/utils/shema_contacts.py``),
which answer *how is this person reached* and *which of the two Marias is this* and are worth
nothing to somebody who stole the response. The real string is
``GET /api/shema/prayer/intercessors/{id}/contact``: one person, one call, logged.

**The deviation is declared and the moment is deliberate.** INT-10 — the screen that consumes
this — is blocked by this issue and has not been written, so the contract's consumer is
adjusted before it exists rather than after. FE-44 §1 freezes the *types*; §9 is what wave
1's screens ask for, and a server requirement the issue states in three places outranks a
field a screen has not yet read.

**The second departure is** ``sensitiveCountry``. ``CLAUDE.md`` §6.1 asks that the
sensitive-country rule be a cross-cutting invariant every output surface goes through, and
FE-44 §8.1 rule 5 already carries it from a project's ``location`` to the personal contacts on
the record. A network contact is the same kind of subject with no project around them, so the
flag rides on their own row. It is **visible on this read and withheld on every path that
leaves** — ``docs/shema.md`` §6.4's split, not a second rule — and the leaving shape is
``app/services/shema/_directory.py``'s.

Dates are ``YYYY-MM-DD`` (FE-44 §9.0) and the day is the UTC day, for the reason
``app/models/shema_org_chart.py`` states once: nothing in this repository stores a timezone
per account.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.utils.shema_contacts import contact_channel
from app.utils.shema_countries import is_country_code


def _clean_country(value: str) -> str:
    """Uppercase, then check membership — the generosity and the rule, in that order.

    ``docs/shema.md`` §5.7 gives the service the uppercasing and the database the length; the
    two meet here, which is the layer §3.3 puts payload validation in. ``br`` is a typo worth
    accepting and ``Brasil`` is not: the whole point of a code is that the network cannot
    fragment into three spellings of one country.
    """
    code = value.strip().upper()
    if not is_country_code(code):
        raise ValueError(
            "country must be an ISO 3166-1 alpha-2 code the console offers, such as 'BR'"
        )
    return code


def _clean_contact(value: str) -> str:
    """Refuse a contact nobody can be reached at, naming the field.

    FE-44 §9.6 asks that the error say **which** field is missing, because the screen names
    it; a Pydantic failure carries the field's location, which is what the console's form
    already reads for the other two.
    """
    contact = value.strip()
    if contact_channel(contact) is None:
        raise ValueError("contact must be an e-mail address or a phone number of at least 8 digits")
    return contact


def _clean_name(value: str) -> str:
    name = value.strip()
    if not name:
        raise ValueError("name is required")
    return name


class IntercessorCreate(BaseModel):
    """A new contact, with the consent that lets the row exist at all.

    ``consent_basis`` is **required and not a courtesy field**. ``docs/shema.md`` §10 item 8
    asks *what consent was given and how it is evidenced* and records that shipping the
    storage before answering it is how silent retention starts. A create that could omit it
    would be that storage: the row and its basis arrive in one transaction or neither
    arrives.

    The other two contexts are not offered here. A person is asked three separate questions
    and answering one is not answering the others, so the ladder is climbed by explicit
    calls to ``PUT .../consents/{context}`` rather than by a create that quietly grants all
    three.
    """

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    name: str
    country: str
    contact: str
    sensitive_country: bool = Field(default=False, alias="sensitiveCountry")
    #: How the ``network`` consent was obtained and how it is evidenced, as a person wrote it.
    consent_basis: str = Field(alias="consentBasis", min_length=1, max_length=300)

    _check_name = field_validator("name")(_clean_name)
    _check_country = field_validator("country")(_clean_country)
    _check_contact = field_validator("contact")(_clean_contact)


class IntercessorUpdate(BaseModel):
    """An edit. Absent means unchanged; ``addedAt`` is not editable and never appears here.

    FE-44 §9.6: *``addedAt`` survives an edit of an intercessor*. It is when the platform
    began holding this person's data, which is the fact a retention question is asked
    against, so it is not a field an edit can reach.
    """

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    name: str | None = None
    country: str | None = None
    contact: str | None = None
    sensitive_country: bool | None = Field(default=None, alias="sensitiveCountry")

    _check_name = field_validator("name")(_clean_name)
    _check_country = field_validator("country")(_clean_country)
    _check_contact = field_validator("contact")(_clean_contact)


class ConsentGrant(BaseModel):
    """Stating one consent. The basis is the field, and it may not be empty."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    basis: str = Field(min_length=1, max_length=300)


class Consent(BaseModel):
    """One consent that stands. **Its existence is the consent** — there is no granted flag."""

    model_config = ConfigDict(populate_by_name=True)

    context: str
    basis: str
    recorded_at: date = Field(alias="recordedAt")


class IntercessorEntry(BaseModel):
    """One person as a **collection** carries them. No contact string, by rule.

    ``contactChannel`` is ``null`` only for a row written before the rule existed — the write
    refuses a string with no channel — and the console shows it as *unreachable* rather than
    as a blank, because a contact nobody can use is the one entry worth noticing.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    country: str
    contact_channel: str | None = Field(alias="contactChannel")
    contact_hint: str = Field(alias="contactHint")
    sensitive_country: bool = Field(alias="sensitiveCountry")
    added_at: date = Field(alias="addedAt")
    consents: list[Consent]


class IntercessorDirectory(BaseModel):
    """The list, and how many people it is not showing.

    **The withheld count is not decoration.** FE-44 §8.1 rule 2 makes the map announce, in a
    visible overlay, how many projects it is withholding, *because a silently incomplete map
    is its own hazard*. A directory filtered by consent has the same hazard and gets the same
    answer: the reader is told the list is short, without being told of whom.
    """

    model_config = ConfigDict(populate_by_name=True)

    people: list[IntercessorEntry]
    #: People in the network with no ``directory`` consent. A number and never a name.
    withheld_count: int = Field(alias="withheldCount")


class IntercessorContact(BaseModel):
    """One contact, revealed on purpose. The response of a route that logs its own use."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    contact: str
