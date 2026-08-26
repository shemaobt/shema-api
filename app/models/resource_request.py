"""Validation for what a client sends about a resource request (BE-05, OBT-454).

Three things the module is built around, each decided before it was written.

**The field-level error rides on Pydantic, not on a new exception.**
``app/core/exceptions.py`` renders every business exception as ``{"detail", "code"}``
and none of them can name a field, while unifying that shape would rewrite the body of
every validation error this API returns. A ``field_validator`` raising ``ValueError``
produces an error located on the field, which FastAPI already renders as a 422 with the
standard ``detail`` list — ``docs/resource_requests.md`` §8.5 measured it. Where the
offending thing is a *key inside* ``fields``, the location is ``fields`` and the message
names the keys: Pydantic locates by structure, and giving each key its own location
would mean turning every answer into an object on the wire, which is a payload shape
nobody asked for.

**Draft and submission are two classes, not one class and a flag.** A draft is filled
over days and may be incomplete; a submission may not. Writing that as a boolean would
put the rule inside every validator and make "which rules ran" a runtime question.

**A stated total is a claim.** The server recomputes it from the rows and refuses a
mismatch instead of correcting it, because a silent correction hides the bug on the
client that produced it. The tolerance is zero, and that is not severity: sub-cent input
is already refused on the way in, so both sides are exact ``Decimal`` values and there
is no rounding left to tolerate — a one-cent margin would only license a one-cent lie.

Every vocabulary, key space and per-type composition comes from
``app/utils/resource_request_vocabularies.py``, which reads the frontend's own emission.
Nothing in this file lists an option.
"""

from collections.abc import Iterable
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from app.db.models.resource_request import RRCurrency, RRDecision, RRRequestType
from app.utils.resource_request_totals import sum_budget, sum_score
from app.utils.resource_request_vocabularies import (
    BUDGET_CATEGORY_KEYS,
    CHECK_VALUES,
    CRITERION_KEYS,
    MAX_SCORE_PER_CRITERION,
    REQUIRED_TEXT_FIELDS,
    TYPES_WITH_TEAM,
    TYPES_WITH_TRAINING_PROFILE,
    VOCABULARY_VALUES,
    section_field_keys,
)

_BUDGET_CATEGORY_SET = frozenset(BUDGET_CATEGORY_KEYS)

#: Money is ``Numeric(14, 2)`` in BE-02's schema, so a third decimal has nowhere to land.
_MONEY_EXPONENT = Decimal("0.01")


def _named(keys: Iterable[str]) -> str:
    return ", ".join(sorted(keys))


def _reject_sub_cent(value: Decimal | None) -> Decimal | None:
    """Money is ``Numeric(14, 2)``: a third decimal has nowhere to land.

    Refused rather than rounded, the same rule the stated total follows — the frontend
    renders up to three decimals and a value the server quietly reshaped would make the
    two sides disagree about what was sent.
    """
    if value is not None and value != value.quantize(_MONEY_EXPONENT):
        raise ValueError(f"more than two decimal places: {value}")
    return value


class BudgetLineIn(BaseModel):
    """One of the 26 fixed categories, keyed and never positional."""

    model_config = ConfigDict(extra="forbid")

    category_key: str
    description: str = ""
    quantity: Decimal | None = None
    amount: Decimal | None = None

    @field_validator("category_key")
    @classmethod
    def _known_category(cls, value: str) -> str:
        if value not in _BUDGET_CATEGORY_SET:
            raise ValueError(f"unknown budget category: {value}")
        return value

    @field_validator("quantity", "amount")
    @classmethod
    def _two_decimals(cls, value: Decimal | None) -> Decimal | None:
        return _reject_sub_cent(value)


class ScoreIn(BaseModel):
    """One criterion's score. ``None`` is *not scored*, which is not a scored zero."""

    model_config = ConfigDict(extra="forbid")

    criterion_key: str
    score: int | None = Field(default=None, ge=0, le=MAX_SCORE_PER_CRITERION)


class ChecksIn(BaseModel):
    """A5's two checkbox sets, both already keyed in the frontend."""

    model_config = ConfigDict(extra="forbid")

    teamtype: list[str] = Field(default_factory=list)
    trainformat: list[str] = Field(default_factory=list)

    @field_validator("teamtype", "trainformat")
    @classmethod
    def _known_options(cls, value: list[str], info: ValidationInfo) -> list[str]:
        allowed = CHECK_VALUES[str(info.field_name)]
        unknown = [option for option in value if option not in allowed]
        if unknown:
            raise ValueError(f"unknown option: {_named(unknown)}")
        return value


class EvaluationIn(BaseModel):
    """The mesa's evaluation — its own aggregate, never nested in the request.

    ``request_type`` is here because the six criteria are per type and a score can only
    be checked against the set its own type renders. Evaluator and date are absent on
    purpose: BE-06 stamps them from the session, and a payload that could carry them
    would be a payload that could lie about who scored.
    """

    model_config = ConfigDict(extra="forbid")

    request_type: RRRequestType
    scores: list[ScoreIn]
    decision: RRDecision | None = None
    comments: str = ""
    stated_total: int | None = None

    @field_validator("scores")
    @classmethod
    def _the_six_of_this_type(cls, value: list[ScoreIn], info: ValidationInfo) -> list[ScoreIn]:
        request_type = info.data.get("request_type")
        if request_type is None:
            return value
        expected = set(CRITERION_KEYS[request_type.value])
        sent = [score.criterion_key for score in value]
        if len(sent) != len(set(sent)):
            raise ValueError("criterion sent twice")
        missing = expected - set(sent)
        unknown = set(sent) - expected
        if unknown:
            raise ValueError(
                f"criterion does not belong to {request_type.value}: {_named(unknown)}"
            )
        if missing:
            raise ValueError(f"missing criterion: {_named(missing)}")
        return value

    @field_validator("stated_total")
    @classmethod
    def _total_matches_the_scores(cls, value: int | None, info: ValidationInfo) -> int | None:
        scores = info.data.get("scores")
        if value is None or scores is None:
            return value
        computed = sum_score(score.score for score in scores)
        if value != computed:
            raise ValueError(f"does not match the scores: they sum to {computed}")
        return value


class RequestDraftIn(BaseModel):
    """A request as it is being filled. Shape is enforced; completeness is not.

    What holds here holds at submission too: an answer outside its vocabulary, a
    category that does not exist, a score out of range and a total that disagrees with
    its rows are wrong whenever they arrive, not merely incomplete. A key belonging to a
    section the type never renders is refused for the same reason — the contract's
    *empty means not answered, absent means not asked* is a distinction the mesa reads,
    and storing an answer to a question that was never put erases it.
    """

    model_config = ConfigDict(extra="forbid")

    request_type: RRRequestType
    currency: RRCurrency = RRCurrency.BRL
    fields: dict[str, str] = Field(default_factory=dict)
    declaration: bool = False
    langs: list[dict[str, str]] = Field(default_factory=list)
    team: list[dict[str, str]] = Field(default_factory=list)
    chrono: list[dict[str, str]] = Field(default_factory=list)
    checks: ChecksIn = Field(default_factory=ChecksIn)
    budget: list[BudgetLineIn] = Field(default_factory=list)
    stated_total: Decimal | None = None

    @field_validator("fields")
    @classmethod
    def _asked_and_answerable(cls, value: dict[str, str], info: ValidationInfo) -> dict[str, str]:
        request_type = info.data.get("request_type")
        if request_type is None:
            return value
        asked = section_field_keys(request_type.value)
        not_asked = set(value) - asked
        if not_asked:
            raise ValueError(f"{request_type.value} does not ask: {_named(not_asked)}")

        for key, answer in value.items():
            allowed = VOCABULARY_VALUES.get(key)
            if allowed is not None and answer != "" and answer not in allowed:
                raise ValueError(f"{key}: answer outside its vocabulary")
        return value

    @field_validator("budget")
    @classmethod
    def _no_repeated_category(cls, value: list[BudgetLineIn]) -> list[BudgetLineIn]:
        keys = [line.category_key for line in value]
        if len(keys) != len(set(keys)):
            raise ValueError("budget category sent twice")
        return value

    @field_validator("checks")
    @classmethod
    def _only_where_a5_renders(cls, value: ChecksIn, info: ValidationInfo) -> ChecksIn:
        request_type = info.data.get("request_type")
        if request_type is None:
            return value
        if (value.teamtype or value.trainformat) and (
            request_type.value not in TYPES_WITH_TRAINING_PROFILE
        ):
            raise ValueError(f"{request_type.value} has no A5 section")
        return value

    @field_validator("team")
    @classmethod
    def _only_where_a4_renders(
        cls, value: list[dict[str, str]], info: ValidationInfo
    ) -> list[dict[str, str]]:
        request_type = info.data.get("request_type")
        if request_type is None:
            return value
        if value and request_type.value not in TYPES_WITH_TEAM:
            raise ValueError(f"{request_type.value} has no team table")
        return value

    @field_validator("stated_total")
    @classmethod
    def _total_matches_the_rows(cls, value: Decimal | None, info: ValidationInfo) -> Decimal | None:
        budget = info.data.get("budget")
        if value is None or budget is None:
            return value
        _reject_sub_cent(value)
        computed = sum_budget(line.amount for line in budget)
        if value != computed:
            raise ValueError(f"does not match the rows: they sum to {computed}")
        return value


class RequestSubmissionIn(RequestDraftIn):
    """A request being submitted. Everything above, plus what a draft may still lack.

    The required set is short on purpose. The contract's *empty means not answered* is
    the norm for the profile — A1, A2 and A3 may all be submitted blank, and the mesa
    reads the blanks — so what is demanded here is the request itself: its project name,
    what it is for, the three essays the Parte C criteria score, the amount asked, the
    declaration, and the two signatures with their dates. The list lives in
    ``vocabularies.py`` so it can move in one place; it is BE-05's reading of the form
    and not a requirement the PRD enumerates field by field.
    """

    @field_validator("fields")
    @classmethod
    def _answered(cls, value: dict[str, str], info: ValidationInfo) -> dict[str, str]:
        request_type = info.data.get("request_type")
        if request_type is None:
            return value
        blank = {
            key
            for key in REQUIRED_TEXT_FIELDS[request_type.value]
            if not value.get(key, "").strip()
        }
        if blank:
            raise ValueError(f"unanswered at submission: {_named(blank)}")
        return value

    @field_validator("declaration")
    @classmethod
    def _declared(cls, value: bool) -> bool:
        if not value:
            raise ValueError("the declaration must be accepted to submit")
        return value

    @field_validator("budget")
    @classmethod
    def _all_twenty_six_and_nothing_negative(cls, value: list[BudgetLineIn]) -> list[BudgetLineIn]:
        missing = _BUDGET_CATEGORY_SET - {line.category_key for line in value}
        if missing:
            raise ValueError(f"missing category at submission: {_named(missing)}")
        negative = [
            line.category_key for line in value if line.amount is not None and line.amount < 0
        ]
        if negative:
            raise ValueError(f"negative amount: {_named(negative)}")
        return value

    @field_validator("team")
    @classmethod
    def _team_where_a4_renders(
        cls, value: list[dict[str, str]], info: ValidationInfo
    ) -> list[dict[str, str]]:
        request_type = info.data.get("request_type")
        if request_type is None:
            return value
        if request_type.value in TYPES_WITH_TEAM and not value:
            raise ValueError(f"{request_type.value} needs at least one team row")
        return value

    @field_validator("checks")
    @classmethod
    def _training_profile_where_a5_renders(cls, value: ChecksIn, info: ValidationInfo) -> ChecksIn:
        request_type = info.data.get("request_type")
        if request_type is None:
            return value
        if request_type.value in TYPES_WITH_TRAINING_PROFILE and not (
            value.teamtype and value.trainformat
        ):
            raise ValueError("section A5 needs a trained team and a format")
        return value
