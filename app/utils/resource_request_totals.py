"""The two derived numbers, recomputed and never stored.

The contract's §5.1 lists both as functions of stored rows: the budget total sums the
rows' amounts, the evaluation total sums the six scores. A client sends either as a
*claim*, and the models in ``app/models/resource_request.py`` check the claim against
these — a mismatch is a validation failure, never a silent correction, because silent
correction hides the bug on the client.

They live in one file because they are the two halves of one rule, and neither touches
the database: nothing here is a query, so nothing here is one operation per file.

``sum_budget`` is the frontend's arithmetic ported, quirks included. The *Qtd. de itens*
column never multiplies anything — only the amount column sums — and a negative amount
subtracts. Whether a negative line may be *submitted* is a different question and is
decided in the model, not here: changing the sum would change what the two sides compute
from the same rows, which is exactly what the recomputation exists to detect.
"""

from collections.abc import Iterable
from decimal import Decimal


def sum_budget(amounts: Iterable[Decimal | None]) -> Decimal:
    """The budget total: the sum of the rows that carry an amount.

    A row with no amount is a category the team left blank, not a zero it typed, and
    the two are the same number here — the distinction matters upstream, where "all 26
    rows present" is a submission rule about rows and not about values.
    """
    total = Decimal("0.00")
    for amount in amounts:
        if amount is not None:
            total += amount
    return total


def sum_score(scores: Iterable[int | None]) -> int:
    """The evaluation total out of 30: the sum of the criteria that were scored.

    Unscored is ``None`` and contributes nothing, which is not the same as a scored
    zero — BE-02 keeps the two apart in the column for that reason, and a total that
    counted an unscored criterion as zero would report a judgement nobody made.
    """
    return sum(score for score in scores if score is not None)
