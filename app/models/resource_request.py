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
from datetime import datetime
from decimal import Decimal
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from app.db.models.resource_request import (
    RRCurrency,
    RRDecision,
    RRMovementKind,
    RRRequest,
    RRRequestFieldHistory,
    RRRequestType,
    RRStage,
)
from app.utils.resource_request_totals import sum_budget, sum_score
from app.utils.resource_request_typed_fields import (
    SPINE_DAY_FIELDS,
    SPINE_MONEY_FIELDS,
    fits_the_money_column,
    parse_day,
    parse_money,
)
from app.utils.resource_request_vocabularies import (
    BUDGET_CATEGORY_KEYS,
    CHECK_VALUES,
    CRITERION_KEYS,
    MAX_SCORE_PER_CRITERION,
    REQUIRED_TEXT_FIELDS,
    TABLE_ROW_KEYS,
    TYPES_WITH_TABLE,
    TYPES_WITH_TEAM,
    TYPES_WITH_TRAINING_PROFILE,
    VOCABULARY_VALUES,
    section_field_keys,
)

_BUDGET_CATEGORY_SET = frozenset(BUDGET_CATEGORY_KEYS)


def _named(keys: Iterable[str]) -> str:
    return ", ".join(sorted(keys))


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
        return fits_the_money_column(value)


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

    @field_validator("fields")
    @classmethod
    def _the_three_typed_answers_parse(cls, value: dict[str, str]) -> dict[str, str]:
        """Three of the 45 stop being text when they land, so they have to be answerable.

        ``amount_requested`` is ``Numeric(14, 2)`` on the spine and the two signature dates
        are ``Date``. The wire carries all 45 as strings, which is right — the client is
        filling a form. But ``"mil e duzentos"`` is not a refusal the service layer should
        be discovering: it would be a 500 from a cast, where every other refusal in this
        module is a located 422.

        It **validates and returns the strings unchanged**; the conversion happens where the
        columns are written. Both sides call the same parser, so *parses here* and *parses
        there* cannot come apart — and keeping ``fields`` a ``dict[str, str]`` keeps the
        contract's own statement of what the 45 are.
        """
        for key in SPINE_MONEY_FIELDS:
            if key in value:
                fits_the_money_column(parse_money(value[key]))
        for key in SPINE_DAY_FIELDS:
            if key in value:
                parse_day(value[key])
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

    @field_validator("langs", "team", "chrono")
    @classmethod
    def _asked_and_answerable_rows(
        cls, value: list[dict[str, str]], info: ValidationInfo
    ) -> list[dict[str, str]]:
        """The rule ``fields`` gets, one level down — a row is answers to columns.

        Both halves are read from the emission: which types render the table at all,
        off the same Parte A/B composition ``section_field_keys`` reads, and which keys
        one of its rows may carry, off the frontend's empty-row seeds. Without the
        second half a row could carry any key with any value and be stored as though
        the question had been put, which is the distinction the class docstring above
        says the mesa reads.
        """
        table = str(info.field_name)
        request_type = info.data.get("request_type")
        if request_type is None:
            return value
        if value and request_type.value not in TYPES_WITH_TABLE[table]:
            raise ValueError(f"{request_type.value} has no {table} table")

        columns = TABLE_ROW_KEYS[table]
        not_asked = {key for row in value for key in row} - columns
        if not_asked:
            raise ValueError(f"{table} has no column: {_named(not_asked)}")
        return value

    @field_validator("stated_total")
    @classmethod
    def _total_matches_the_rows(cls, value: Decimal | None, info: ValidationInfo) -> Decimal | None:
        budget = info.data.get("budget")
        if value is None or budget is None:
            return value
        fits_the_money_column(value)
        computed = sum_budget(line.amount for line in budget)
        if value != computed:
            raise ValueError(f"does not match the rows: they sum to {computed}")
        return value


class DiscardedOut(BaseModel):
    """Told to a client whose copy lost, with both timestamps so it can say why.

    Never a silent merge and never a silent overwrite: the issue asks for the warning to
    name **which side won and when each was saved**, and those three fields are that
    sentence. A client holding this still has the payload it tried to send.
    """

    winner: str
    client_saved_at: datetime | None
    server_saved_at: datetime


class FieldChangeOut(BaseModel):
    """One row of the field-by-field trail: who changed which field, from what, to what.

    The values are the wire's own strings — what the flattened document showed before and
    after — so a client renders them as it renders the document, with no type map on the
    side. ``None`` against ``""`` keeps the contract's distinction: a field that had no
    value at all against one that was asked and left blank. ``changed_by`` is a user id
    and deliberately not a resolved name: the trail is append-only and a name is not — it
    is resolved at display time, so a rename does not contradict the record.
    """

    field_key: str
    old_value: str | None
    new_value: str | None
    changed_by: str
    changed_at: datetime

    @classmethod
    def of(cls, row: RRRequestFieldHistory) -> Self:
        return cls(
            field_key=row.field_key,
            old_value=row.old_value,
            new_value=row.new_value,
            changed_by=row.changed_by,
            changed_at=row.changed_at,
        )


class RequestOut(BaseModel):
    """A request on the wire: mutable envelope outside, frozen-able document inside.

    The split is the point. ``document`` is byte for byte what a submission freezes into
    ``rr_snapshots`` and byte for byte what ``PATCH`` accepts back, so a round trip through
    this API cannot reshape a team's answers. Everything beside it — the id, the stage, the
    timestamps, the link back to what a revision revises — is state that moves, and is
    deliberately outside the thing that must not.

    **The team's four-mark progress bar is served from these fields alone, and that is what
    keeps it clear of §5.3.** *Rascunho → Enviado → Em análise → Decisão* reads out whole:
    ``submitted_at`` separates the first two — the ``stage`` does not, because a draft
    carries the column's ``triagem`` default and is not on the board yet — ``stage`` being
    ``analise`` is the third, and the four decision stages are the fourth, from which the
    last mark takes its label and its colour. **Nothing in ``rr_evaluations`` is read**: the
    day the bar fetches a score or a comment to colour a mark, §5.3 was broken by a progress
    bar.

    **Four marks of journey and not of decision is ours to decide — Daniel, 28/aug/2026 —
    and not the client's sentence.** The four ``RRDecision`` values are mutually exclusive,
    so four boxes of which exactly one ever lights is not progress; it is a status wearing a
    bar's clothes. It gets shown to the client with the screen in hand (FE-28).

    ``endorsed_by``/``endorsed_at`` ride in the envelope, not the document (BE-16): the
    act is state that moves around the frozen thing, exactly like ``submitted_at`` — and
    the team seeing *endorsed on this date* is status, which GATE-03 D4 allows, not the
    evaluation, which §5.3 closes. The display pair the paper form had (``leader_name``,
    ``leader_date``) stays inside the document, where the contract's 45 keys put it.
    """

    id: str
    stage: RRStage
    created_by: str | None
    revision_of_id: str | None
    submitted_at: datetime | None
    endorsed_by: str | None
    endorsed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    document: dict[str, Any]

    @classmethod
    def of(cls, request: RRRequest, document: dict[str, Any], **extra: Any) -> Self:
        """Build the envelope from a request row.

        Here and not in the router because ``CLAUDE.md`` §2 keeps SQLAlchemy models out of
        the api layer, and shaping a response is this layer's job anyway. ``request`` is
        typed, and the first version of this was not: the argument for ``Any`` was that
        naming ``RRRequest`` would reach somewhere new, and it does not — this module already
        imports four enums from ``app.db.models.resource_request``. Seven attribute reads off
        an untyped parameter is where a renamed column stops being caught, which is the whole
        of what mypy is for here (PR #269, review).

        ``Self`` and not ``RequestOut``, so the two subclasses keep their own type: the
        answer to a write carries ``discarded`` and the answer to a submission carries
        ``snapshot_id``, and a base-typed constructor would hand both back as the parent and
        let a route promise a field it never returns.
        """
        return cls(
            id=request.id,
            stage=request.stage,
            created_by=request.created_by,
            revision_of_id=request.revision_of_id,
            submitted_at=request.submitted_at,
            endorsed_by=request.endorsed_by,
            endorsed_at=request.endorsed_at,
            created_at=request.created_at,
            updated_at=request.updated_at,
            document=document,
            **extra,
        )


class RequestSavedOut(RequestOut):
    """A write's answer. ``discarded`` is null on the ordinary save."""

    discarded: DiscardedOut | None = None


class SubmissionOut(RequestOut):
    """What submitting answers.

    ``submitted_at`` is the server's stamp and ``snapshot_id`` names the frozen document, so
    a client can show *received, on this date* without a second call.

    **The receipt is the date and the time, and the question is closed.** Asked on
    28/aug/2026 what a submission hands back on the spot, the client answered *"data e
    hora"* — so ``submitted_at`` **is** the receipt, and this class already returned it.
    Contract §7 marked the question as blocking *the submission issue*, this one; it closes
    with the shape unmoved, and BE-13 quotes that date in the e-mail it sends.

    **``snapshot_id`` is not a receipt number and must not be shown as one.** It names the
    frozen document, which is what a client needs to fetch what was submitted; the day it
    appears on a screen as *your request is 3f9a…* it has become the way people refer to a
    request, and a real number can no longer replace it. A number for people stays additive
    afterwards — the point of the answer is that **nothing waits for it**.
    """

    snapshot_id: str


class FundOut(BaseModel):
    """A fund card's server truth: the name and the three figures FE-14 renders.

    ``allocated`` and ``committed`` are sums over the ledger and ``available`` is their
    difference, all computed by ``fund_balances`` on every read — none of the three is a
    column anywhere (contract §3.2). ``available`` travels rather than being left to the
    client because the subtraction is the rule, not presentation, and a second
    implementation of it is a second place for it to be wrong.

    Money serializes as strings on the wire — Pydantic's own ``Decimal`` handling, kept
    because a JSON float is exactly the representation the ledger's ``Numeric`` exists to
    avoid.

    ``retired`` is the field BE-10 (OBT-471) added *with* its reader, which is what
    ``provisional`` never had and why that column is gone rather than served here. A
    retired fund still travels: its *comprometido* is money the ledger holds, and
    filtering it out of this read would erase that money from the Painel. It is the list
    of choice that drops it, on this flag.
    """

    id: str
    name: str
    retired: bool
    allocated: Decimal
    committed: Decimal
    available: Decimal


class FundNameIn(BaseModel):
    """What a caller may say about a fund: what it is called, and nothing else.

    One payload for creating and for renaming, because the two say the same sentence — the
    id is never in it. Minting it is ``create_fund``'s (``uuid4().hex``, opaque so a rename
    cannot be tempted to touch it) and an id arriving from a client would be a name space
    the client owns. ``extra="forbid"`` is what makes that refusal audible rather than
    silent: a payload carrying ``id`` answers 422 naming the field instead of being
    quietly ignored.

    The length is the column's own ``String(120)``. Emptiness is refused here **and** in
    the service, the same two-door shape ``AllocationIn`` and ``set_allocation`` keep: the
    wire gets a field-level 422, and a caller that does not come through the wire still
    cannot write a nameless fund.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)


class FundAdminOut(BaseModel):
    """A fund as its administration screen holds it: id, name, and whether it ended.

    No money. The three figures are ``FundOut``'s, summed over the ledger on every read,
    and repeating them in the answer to a rename would say that renaming a fund is an
    event in its balance. ``retired_at`` travels as the timestamp rather than as a boolean
    for the reason the column is one: *when it ended* is what a movement dated last year
    raises.

    ``id`` travels even though no screen shows it — the client needs it to address the
    next call, which is a different thing from displaying it.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    retired_at: datetime | None


class MovementOut(BaseModel):
    """One ledger entry on the wire: what moved, who moved it, when, and why.

    ``created_by``/``created_at``/``reason`` are the row's own authorship — for an
    ``ALLOCATION`` they *are* GATE-01 D6's "who edited it and when". ``reverses_id``
    names the movement a compensation undoes, so a history reads as what happened
    rather than as a net.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    fund_id: str
    request_id: str | None
    kind: RRMovementKind
    amount: Decimal
    currency: RRCurrency
    reverses_id: str | None
    reason: str
    created_by: str
    created_at: datetime


class AllocationIn(BaseModel):
    """The alocado as the Gestor states it — the field's value, never a delta.

    GATE-01 D6's editable field shows a total and the edit states the new one; what that
    becomes in the ledger (one ``ALLOCATION``, or a compensating correction) is
    ``set_allocation``'s to decide, not the payload's to say. **Zero is a value** — the
    state every fund is born in — and a negative one is refused here, field-located, the
    same 422 every other refusal of this module answers. The money rule is
    ``fits_the_money_column``, because this is the first place a client POSTs money that
    lands in ``Numeric(14, 2)`` directly rather than through a budget line.

    ``reason`` is the author's why, carried onto each movement the edit writes; who and
    when never travel here — they are the session's and the row's own (BE-06's rule,
    already this module's).
    """

    model_config = ConfigDict(extra="forbid")

    amount: Decimal
    reason: str = ""

    @field_validator("amount")
    @classmethod
    def _a_value_a_fund_can_hold(cls, value: Decimal) -> Decimal | None:
        """The fit runs first because the comparison is the arithmetic that can blow:
        ``NaN < 0`` signals ``InvalidOperation``, and ``fits_the_money_column`` is the
        function already hardened to refuse before any Decimal operation can — §8.5's
        lesson, one operator earlier again."""
        checked = fits_the_money_column(value)
        if checked is not None and checked < 0:
            raise ValueError(f"an alocado states money put in, and {checked} is less than none")
        return checked


class AllocationOut(BaseModel):
    """What FE-26 renders: the alocado summed, and D6's who-and-when mark.

    ``allocated`` is ``fund_balances``' sum, serialized the way ``FundOut`` already
    serializes money — a string on the wire, never a JSON float. ``allocated_by`` is the
    author's e-mail (the identifier the frontend renders and stores; the ledger's history
    keeps the user id) and ``allocated_at`` the row's own stamp; both are ``None`` on a
    fund nobody has allocated, because a mark on a value nobody entered would be
    fabricated authorship.
    """

    fund_id: str
    allocated: Decimal
    allocated_by: str | None
    allocated_at: datetime | None


class RequestSubmissionIn(RequestDraftIn):
    """A request being submitted. Everything above, plus what a draft may still lack.

    The required set is short on purpose. The contract's *empty means not answered* is
    the norm for the profile — A1, A2 and A3 may all be submitted blank, and the mesa
    reads the blanks — so what is demanded here is the request itself: its project name,
    what it is for, the three essays the Parte C criteria score, the amount asked, the
    declaration, and the requester's name. The paper form's signature dates and the
    Líder's line are not demanded any more — submitting is the electronic acceptance
    (OBT-483), and ``vocabularies.py`` says why where the list lives. The list lives
    there so it can move in one place; it is BE-05's reading of the form and not a
    requirement the PRD enumerates field by field.
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
