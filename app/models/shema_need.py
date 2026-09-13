"""What a client writes about a need, and what one need looks like once it leaves.

``app/models/shema_record.py`` holds :class:`~app.models.shema_record.ShemaNeedItem`, which is
one need **on the record** — a coordination surface, carrying the truth, read by the person
who filled it in. This file holds the other two halves BE-08 owns:

* :class:`ShemaNeedWrite`, what arrives in the record's ``PATCH`` under ``needsItems``. There
  is no needs endpoint in wave 1 (``docs/shema.md`` §5.4, FE-44 §9.5) and this is why there
  does not need to be one: a need travels with its project, and the batch is a field of the
  record's own write.
* :class:`ShemaNeedLine`, one need on its way out of coordination — the export row, the donor
  spreadsheet line, the body of an urgent notice. It is a
  :class:`~app.models.shema_privacy.LeavingShape`, so it withholds the place by **declaring**
  the fields rather than by remembering to call anything.

**Why the leaving shape is the financial shape.** An amount against a named project in a named
country is exactly the combination ``CLAUDE.md`` §6.1 protects, and it is also the field that
ends up in a spreadsheet somebody forwards to a donor. The two facts are one fact: the money
is the reason the row travels, so the row that carries the money is the row the boundary has
to reduce. ``tests/test_shema/test_privacy.py``'s export parametrisation carries this shape
beside BE-04's five for that reason — the proof is at the boundary, and BE-14 builds the file
on top of a shape that is already protected.

**Money, in one paragraph.** ``Numeric(14, 2)`` mapped to :class:`~decimal.Decimal`, and the
ISO-4217 code stored beside it — the sibling's decision (``docs/resource_requests.md`` §7.2)
and its reasons, plus the one this module adds: seven regions, no shared currency. **Nothing
converts.** There is no base currency in this module, no rate table, and no sum across
currencies or across categories — a need for a motorbike and a need for a translation
consultant do not add up, and neither do rupiah and reais.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import (
    AliasGenerator,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)
from pydantic.alias_generators import to_camel

from app.db.models.shema_enums import ShemaNeedStatus, ShemaNeedUrgency
from app.models.shema_privacy import LeavingShape
from app.utils.shema_facets import OPEN_NEED_STATUSES

#: The inward config of ``app/models/shema.py``, restated rather than imported: that module
#: imports :class:`ShemaNeedWrite` from this one, so the dependency already runs this way and
#: importing back would be a cycle. The decision it encodes is BE-06's and is argued there —
#: a **validation** alias, so a client patches in the spelling it reads, with
#: ``populate_by_name`` keeping the house's snake_case for a caller inside this repository.
_INWARD = ConfigDict(
    extra="forbid",
    populate_by_name=True,
    alias_generator=AliasGenerator(validation_alias=to_camel),
)

#: Read models speak camelCase outward and snake_case inward — ``app/models/shema_record.py``'s
#: ``_OUTWARD``, for the reason its docstring gives.
_OUTWARD = ConfigDict(
    from_attributes=True,
    populate_by_name=True,
    alias_generator=AliasGenerator(serialization_alias=to_camel),
)

#: An ISO-4217 alphabetic code, as ISO writes it.
_ISO_4217 = re.compile(r"^[A-Z]{3}$")

#: What ``Numeric(14, 2)`` can hold. Refused here so a typo meets a sentence naming the field
#: instead of a database error naming a constraint.
MAX_AMOUNT: Decimal = Decimal("999999999999.99")


def normalised_currency(value: str) -> str:
    """``value`` as ISO writes a currency code, or a :class:`ValueError` naming what is wrong.

    **Case is normalised and nothing else is.** The sibling's rule is that silent correction
    hides client bugs — it refuses a sub-cent amount rather than rounding it — and this does
    not break it: rounding changes the number, while upper-casing writes one value the one way
    ISO defines it. A symbol is **not** accepted, for the sibling's stated reason: several
    currencies share a glyph and ``$`` is the worst of them, so ``R$``↔``BRL`` is a mapping
    that belongs in the console, where a person chose the currency.
    """
    code = value.strip().upper()
    if not _ISO_4217.match(code):
        raise ValueError(f"{value!r} is not an ISO-4217 currency code, which is three letters")
    return code


class ShemaNeedWrite(BaseModel):
    """One row of the ``needsItems`` batch — a need to create, or one to move.

    **The ``id`` is the address, and that is** ``docs/shema.md`` **§10 item 6, answered.** A
    ``NeedItem`` carried none and a derived notification identified one by
    ``(project, category, submittedAt)``; that triple is not unique — two ``financial`` needs
    filed on one day are one collision — and a need nobody can address is a need nobody can
    acknowledge, fulfil or drop. So the row's own id is published and is what a save quotes.
    An item **without** an id is a new need; an id the project does not have is refused by
    name rather than quietly inserted, because a client sending an id believes it is editing
    something.

    **What the client may not write is the evidence.** ``acknowledgedAt``, who acknowledged and
    under what name are stamped by the server from the request's actor and its day — the same
    rule FE-44 §7.2 states for the progress entry and for the same reason: a client that
    supplied them could rewrite who saw what, when. What the client sends is the **gesture**,
    :attr:`acknowledged`, and the server writes the three columns.

    **Acknowledgement does not come back off.** ``acknowledged: false`` on a need already
    acknowledged is a no-op rather than an erasure: somebody did see it, and a field whose
    value can be taken back is not evidence. Un-seeing is not a gesture the product has.
    """

    model_config = _INWARD

    #: Absent is *a new need*. Present is *this one*, and it must be one of this project's.
    id: str | None = None

    category: str = Field(min_length=1, max_length=60)
    urgency: ShemaNeedUrgency = ShemaNeedUrgency.LOW
    status: ShemaNeedStatus = ShemaNeedStatus.OPEN
    description: str = ""

    #: The amount as somebody typed it, caveats and all — FE-44's own ``estimatedValue``. Kept
    #: beside the parsed pair rather than replaced by it: *about 5.000, more if the second
    #: village joins* is a sentence, and a number is not a translation of it.
    estimated_value: str | None = Field(default=None, max_length=120)
    #: The amount, exactly. **Two decimals**, never negative, and never rounded for the caller:
    #: a third decimal is refused with the field named rather than silently dropped by the
    #: column, which is the sibling's rule (``docs/resource_requests.md`` §7.2).
    estimated_amount: Decimal | None = None
    #: The ISO-4217 code the amount is in. Required whenever there is an amount — see
    #: :meth:`_an_amount_carries_its_currency`.
    estimated_currency: str | None = None

    deadline: date | None = None
    prayer_shared: bool = False
    prayer_answered: bool = False

    fulfilled_by: str | None = Field(default=None, max_length=200)
    fulfilled_date: date | None = None
    dropped_date: date | None = None
    submitted_by: str | None = Field(default=None, max_length=200)
    submitted_at: date | None = None

    #: **The gesture, not the evidence.** ``true`` says *somebody has seen this*; the server
    #: writes the day, the account and the name. Sending it ``false`` never clears a stamp.
    acknowledged: bool = False

    @field_validator("estimated_currency")
    @classmethod
    def _the_currency_is_a_code(cls, value: str | None) -> str | None:
        return None if value is None else normalised_currency(value)

    @field_validator("estimated_amount")
    @classmethod
    def _the_amount_is_money(cls, value: Decimal | None) -> Decimal | None:
        """Non-negative, at most two decimals, inside the column.

        A need is a request for help, so a negative one is not a budget line with a sign —
        it is a typo. The sibling left negatives to its own validation rule because a fund
        movement legitimately has two directions; an ask has one.

        ``NaN`` and ``Infinity`` are refused before anything is compared against them, because
        :class:`~decimal.Decimal` parses both from a string and every comparison with a ``NaN``
        is false — so the two checks below would pass it through to a column that cannot store
        it. That is the shape of a guard that reads as thorough and admits the one value it
        was written for.
        """
        if value is None:
            return value
        if not value.is_finite():
            raise ValueError(f"{value} is not an amount")
        if value < 0:
            raise ValueError("an amount asked for is not negative")
        exponent = value.as_tuple().exponent
        if isinstance(exponent, int) and exponent < -2:
            raise ValueError(f"{value} has more than two decimals; send the amount as money")
        if value > MAX_AMOUNT:
            raise ValueError(f"{value} is larger than this column holds ({MAX_AMOUNT})")
        return value

    @model_validator(mode="after")
    def _an_amount_carries_its_currency(self) -> ShemaNeedWrite:
        """**The DoD's fourth line, at the earliest place it can be said.**

        The database refuses the same pair with a ``CHECK`` — that is what makes it an
        invariant of the data rather than of one write path, and it is what holds for a seed,
        an import and a psql session. This is the half that can name the field and say which
        of the two is missing, which a constraint violation cannot.
        """
        if (self.estimated_amount is None) != (self.estimated_currency is None):
            missing = "estimatedCurrency" if self.estimated_currency is None else "estimatedAmount"
            raise ValueError(
                f"{missing} is required: an amount travels with the currency it is in, and "
                "nothing in this module converts one"
            )
        return self

    @model_validator(mode="after")
    def _acting_on_a_need_is_seeing_it(self) -> ShemaNeedWrite:
        """A need moved out of ``open`` was seen by whoever moved it.

        Stated on the payload rather than only in the service, so the two axes cannot disagree
        in the one direction that would matter: *in progress and nobody has seen it* is not a
        state the product has, and a sweep that had to special-case it would be a sweep with a
        second definition of unacknowledged in it.
        """
        if self.status is not ShemaNeedStatus.OPEN:
            self.acknowledged = True
        return self


class ShemaNeedLine(LeavingShape):
    """One need on its way out of coordination — the export row, and the donor's line.

    **It names the money and it does not name the place.** ``location`` and ``team`` are
    declared precisely so that :class:`~app.models.shema_privacy.LeavingShape` reduces them:
    the country becomes the region key, the base goes empty, and ``locationWithheld`` says so.
    An author who adds a column to the export inherits that by declaring the field, which is
    the property ``docs/shema.md`` §6.4 spends a section on.

    **The amount is not reduced**, and that is the split rather than an omission: what a
    sensitive project is protected from is being *located*, not being helped. A line that
    withheld its amount would be a line no Resource Circle could act on, which would make the
    protection cost the thing it is for.
    """

    model_config = _OUTWARD

    #: The need's own id, so a line can be traced back to the row it came from.
    id: str
    project_id: str
    language_name: str = ""

    #: Both reduced by the boundary. Declared so that they are.
    location: str = ""
    team: str = ""

    category: str = ""
    urgency: ShemaNeedUrgency = ShemaNeedUrgency.LOW
    status: ShemaNeedStatus = ShemaNeedStatus.OPEN

    estimated_amount: Decimal | None = None
    estimated_currency: str | None = None

    deadline: date | None = None
    submitted_at: date | None = None
    acknowledged_at: date | None = None

    @classmethod
    def of(cls, need: Any, project: Any) -> ShemaNeedLine:
        """Build one line from a need row and the project it hangs off.

        Two objects and therefore an explicit constructor: ``from_attributes`` reads one, and
        the sensitive flag and the region live on the **project** while the money lives on the
        **need**. Everything the boundary needs is passed, so the shape never falls back to
        the fail-closed default for want of a column somebody forgot to select — and if a
        caller does hand over something that cannot answer, the default withholds.
        """
        return cls.model_validate(
            {
                "id": need.id,
                "project_id": project.id,
                "language_name": project.language_name,
                "location": project.location,
                "team": project.team,
                "category": need.category,
                "urgency": need.urgency,
                "status": need.status,
                "estimated_amount": need.estimated_amount,
                "estimated_currency": need.estimated_currency,
                "deadline": need.deadline,
                "submitted_at": need.submitted_at,
                "acknowledged_at": need.acknowledged_at,
                "sensitive_country": project.sensitive_country,
                "region_key": project.region_key,
            }
        )


def is_still_open(status: ShemaNeedStatus) -> bool:
    """Whether a need in this state is still somebody's problem.

    One import of ``app/utils/shema_facets.py``'s set rather than a comparison written out,
    because a predicate spelled ``status != "fulfilled"`` is a bug the moment a fifth state
    exists — which is the sentence FE-44 §5.2 and ``docs/shema.md`` §5.4 both make about this
    exact field.
    """
    return status in OPEN_NEED_STATUSES
