"""The six answers that are columns, and the two types among them that are not text.

The contract's 45 text keys are the questions the form asks. Six of them are **promoted
to columns** on ``rr_requests`` because the board, the lists and the cycle indicators
query them — ``reg_name``, ``amount_requested``, ``tpp_name``, ``tpp_date``,
``leader_name`` and ``leader_date`` — and the model states the rule that follows: a value
with two homes is a value with no owner, so a promoted key is **not** also stored among
the section answers.

The wire does not know that. ``RequestDraftIn.fields`` is ``dict[str, str]`` and carries
all 45 together, which is right — the client is filling a form, not populating a schema.
So something has to move six of them across, and two of the six stop being strings when
they land: ``amount_requested`` is ``Numeric(14, 2)`` and the two dates are ``Date``.

**Why this lives in ``app/utils/`` and not beside either of its two callers.** The
validator that refuses an unparsable answer belongs in ``app/models/resource_request.py``,
so the client gets the located 422 that every other refusal in that module returns; the
split that writes the columns belongs in the service layer. A DTO module may not import
the service layer — ``tests/test_app_boots.py`` enforces it, after an import cycle closed
that way once — so the shared half sits here, which is the same reasoning that put
``resource_request_vocabularies.py`` here.

The **range** of money lives here too, since BE-07: ``fits_the_money_column`` was the DTO
module's alone while the DTO was its only caller, and the ledger's writer is the second —
a payload and a movement are refused by the same statement of ``Numeric(14, 2)``'s shape,
never by two that can drift.
"""

from datetime import date
from decimal import Decimal, InvalidOperation

_TWO_PLACES = Decimal("0.01")
_MONEY_LIMIT = Decimal(10) ** 12

#: Answers that land in a ``String`` column of ``rr_requests``, unchanged.
SPINE_TEXT_FIELDS: tuple[str, ...] = ("reg_name", "tpp_name", "leader_name")

#: The one answer that lands in ``Numeric(14, 2)``. Item 9, typed by hand, and never the
#: budget total — that one is derived and stored nowhere (BE-05).
SPINE_MONEY_FIELDS: tuple[str, ...] = ("amount_requested",)

#: The two answers that land in ``Date``, from the signature block of Parte B item 11.
SPINE_DAY_FIELDS: tuple[str, ...] = ("tpp_date", "leader_date")

#: The six, as one set. Every read of *is this key a column* goes through this name.
PROMOTED_TO_SPINE: frozenset[str] = frozenset(
    SPINE_TEXT_FIELDS + SPINE_MONEY_FIELDS + SPINE_DAY_FIELDS
)


def parse_money(answer: str) -> Decimal | None:
    """``""`` is *not answered*; anything else must be a number.

    Empty is a legitimate draft state and stays ``None`` in the column, which is the same
    distinction the contract draws everywhere else: empty means the question was not
    answered, and it is a thing the mesa reads.
    """
    text = answer.strip()
    if not text:
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        raise ValueError(f"not an amount: {answer!r}") from None


def parse_day(answer: str) -> date | None:
    """ISO ``YYYY-MM-DD``, which is what ``<input type="date">`` submits."""
    text = answer.strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        raise ValueError(f"not a date in YYYY-MM-DD: {answer!r}") from None


def fits_the_money_column(value: Decimal | None) -> Decimal | None:
    """Money is ``Numeric(14, 2)``: neither a third decimal nor a thirteenth integer
    digit has anywhere to land.

    Refused rather than rounded, the same rule the stated total follows — the frontend
    renders up to three decimals and a value the server quietly reshaped would make the
    two sides disagree about what was sent. The refusal is a ``ValueError``: Pydantic
    turns it into the located 422 the DTO module answers with, and the ledger's writer
    re-raises it as this API's ``ValidationError``.

    The magnitude is checked **before** the quantize and not after, because ``quantize``
    signals ``InvalidOperation`` once the result would need more digits than the decimal
    context carries — ``"1E+30"`` reaches it — and Pydantic turns only ``ValueError``
    into a validation error, so that arithmetic left here as a 500 instead of the 422
    every other refusal in this module returns. ``is_finite`` guards the same signal for
    ``NaN``, which Pydantic already refuses on its own; it is stated here so the function
    is correct against a ``Decimal`` rather than against a default that could move — and
    for the ledger it is load-bearing, since even comparing a ``NaN`` raises.
    """
    if value is None:
        return value
    if not value.is_finite() or abs(value) >= _MONEY_LIMIT:
        raise ValueError(f"outside the range money is stored in: {value}")
    if value != value.quantize(_TWO_PLACES):
        raise ValueError(f"more than two decimal places: {value}")
    return value


def render_money(value: Decimal | None) -> str:
    """Back to the wire's string, at the column's own two decimals — always.

    ``"1200.5"`` comes back ``"1200.50"``. The quantize is the load-bearing part and it is
    **not** cosmetic: without it the same amount renders differently depending on where the
    ``Decimal`` came from. Straight off the wire it is ``1200.5``; after a round trip through
    ``Numeric(14, 2)`` PostgreSQL hands back ``1200.50``. A snapshot frozen from objects
    still in the session would then differ from every later read of the same request by a
    trailing zero, and the guarantee that the mesa evaluated what the team submitted would
    fail on a comparison nobody would think to distrust.

    It is a normalisation and not a loss: the DTO refused a third decimal on the way in, so
    the only digit this can add is a zero the client did not send.
    """
    return "" if value is None else str(value.quantize(_TWO_PLACES))


def render_day(value: date | None) -> str:
    return "" if value is None else value.isoformat()
