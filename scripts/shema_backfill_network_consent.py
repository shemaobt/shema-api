"""Record the ``network`` consent, in one batch, for everybody in the prayer network who lacks it.

    uv run python -m scripts.shema_backfill_network_consent \\
        --basis "<how the consent was obtained and how it is evidenced>" \\
        --recorded-by <the e-mail of your own account>
    # ...read what it says it would do, then the same line with --apply

**It is not run by the issue that wrote it (OBT-531), and it must not be run until the client
states the basis.** Karina answered on 22/sep (4.1) that *everybody in the network gave their
authorization, and we know how* — and the *how* has not arrived. A consent row without its basis
is the state ``app/db/models/shema_consent.py`` exists to make unrepresentable, so the basis is
a required argument, checked by the same rule the API applies to one person
(``ConsentGrant``), and nothing in this repository calls this file.

**Against a network built through the API it finds nobody.** ``add_intercessor`` will not store
a person without the ``network`` consent, and withdrawing it erases the person. What this is
for is rows written some other way — the network the client already keeps, imported in bulk,
whose people were asked once, together, on one stated basis.

Three properties, each of them the reason it is safe to run by hand:

* **Dry-run is the default and** ``--apply`` **is the opt-in**, as ``import_shema_projects.py``
  does: the first real run is preceded by one that changes nothing.
* **Idempotent.** It inserts only where the row is missing and never restamps a consent that
  stands — ``_directory.record_where_missing``, the owner of the table, is the whole write — so
  a second run finds nobody, and a person who answered on their own keeps their own answer.
* **``recorded_by`` is whoever ran it**, resolved from the e-mail of their account: the column
  is a foreign key to ``users``, and *who stated this basis for these people* is the question
  somebody will ask. An address with no account stops the run.

It prints **counts and nothing else**. A terminal is scrolled back, pasted and logged, and the
people this touches are the ones the network promised to protect.
"""

import argparse
import asyncio
import sys
from dataclasses import dataclass

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.db.models.shema_consent import ShemaConsentContext
from app.models.shema_intercessor import ConsentGrant
from app.services.auth import get_user_by_email
from app.services.shema._directory import people_lacking, record_where_missing

CONTEXT = ShemaConsentContext.NETWORK


class UnknownOperator(LookupError):
    """The e-mail given as ``--recorded-by`` is not an account, so nobody can be named."""


@dataclass(frozen=True)
class Outcome:
    """What a run found and what it wrote. Counts, never people."""

    lacking: int
    recorded: int
    write: bool


def checked_basis(raw: str) -> str:
    """The basis as the API would accept it for one person, or ``ValueError`` naming why."""
    try:
        return ConsentGrant(basis=raw).basis
    except ValidationError as error:
        raise ValueError(error.errors()[0]["msg"]) from error


async def backfill(db: AsyncSession, *, basis: str, recorded_by_email: str, write: bool) -> Outcome:
    """Find who lacks ``network`` and, when ``write``, record it for them on ``basis``."""
    operator = await get_user_by_email(db, recorded_by_email)
    if operator is None:
        raise UnknownOperator(f"{recorded_by_email} is not an account on this server")

    lacking = await people_lacking(db, CONTEXT)
    recorded = 0
    if write and lacking:
        recorded = await record_where_missing(db, CONTEXT, basis=basis, recorded_by=operator.id)
    return Outcome(lacking=len(lacking), recorded=recorded, write=write)


def report(outcome: Outcome) -> str:
    """The run in one or two lines — how many, never who."""
    if not outcome.write:
        return (
            f"dry-run: {outcome.lacking} person(s) in the network have no '{CONTEXT.value}' "
            "consent. Nothing was written; re-run with --apply to record it."
        )
    return (
        f"applied: '{CONTEXT.value}' consent recorded for {outcome.recorded} person(s). "
        "A second run finds nobody."
    )


async def _run(basis: str, recorded_by_email: str, *, write: bool) -> int:
    async with AsyncSessionLocal() as db:
        try:
            outcome = await backfill(
                db, basis=basis, recorded_by_email=recorded_by_email, write=write
            )
        except UnknownOperator as error:
            print(f"refused: {error}", file=sys.stderr)
            return 2
    print(report(outcome))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Record the 'network' consent, in one batch, for whoever in the prayer "
        "network lacks it. Dry-run unless --apply."
    )
    parser.add_argument(
        "--basis",
        required=True,
        help="how the consent was obtained and how it is evidenced, as the client stated it. "
        "Up to 300 characters, and not blank.",
    )
    parser.add_argument(
        "--recorded-by",
        required=True,
        help="the e-mail of the account running this — stored as who recorded the consent.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="actually write. Without it the run changes nothing and says what it would do.",
    )
    args = parser.parse_args(argv)
    try:
        basis = checked_basis(args.basis)
    except ValueError as error:
        parser.error(f"--basis: {error}")
    return asyncio.run(_run(basis, args.recorded_by, write=args.apply))


if __name__ == "__main__":
    raise SystemExit(main())
