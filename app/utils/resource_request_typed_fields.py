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

Parsing only. The **range** of money is ``_fits_the_money_column``'s in the DTO module,
which refuses a third decimal rather than rounding it; splitting that check across two
files would be two statements of one rule.
"""

from datetime import date
from decimal import Decimal, InvalidOperation

_TWO_PLACES = Decimal("0.01")

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
