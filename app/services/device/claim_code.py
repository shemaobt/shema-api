"""Minting, hashing and timing the short-lived code a device shows at installation.

A claim code is not a credential. It is a one-time bearer artefact that exists for the
few minutes between a tablet being switched on and a facilitator standing in front of it,
and its only power is to attach that device to a project exactly once. What the device
gets in exchange for spending it — a long-lived credential — is ENG-443, deliberately not
here.

Three decisions live in this module, and each one is a trade the reviewer should be able
to see:

**Lifetime.** Fifteen minutes. Long enough that a facilitator can read the code off a
screen and walk to another room; short enough that a code left on a switched-on tablet at
the end of the day is dead by morning. It is an installation-moment artefact, not a
password, and nothing in the product needs it to survive a coffee break.

**Alphabet and length.** Seven characters as ``XXX-XXXX``, drawn from twenty-five glyphs.
Every pair that collides when a code is read across a table and typed by the person
hearing it is gone: ``0``/``O``, ``1``/``I``/``L``, ``5``/``S``, ``2``/``Z``, ``8``/``B``.
That leaves 25**7, about 6.1e9 codes. Note that the prototype's own example, ``R7K-M2Q4``,
contains a ``2`` — the shape survived that review and the glyph did not.

Six billion is a large number for a code that lives fifteen minutes and works once, and
it is a small number for an attacker who can guess without limit. The safety of this
artefact rests on three things: the short life, the single use, and rate limiting at the
route that spends it.

**The third one does not exist, and the route does.** ``POST /api/facilitator/devices/claim``
is in ``app/api/facilitator/devices.py`` and carries no limit of any kind, while
``app/core/rate_limit.py`` already guards four routes across two other products. This
paragraph said the debt could not be paid because the route had not been built; the route was
built in ENG-443 and the sentence stayed, which left the only place the debt is recorded
telling whoever read it that there was nothing to do.

The debt is **open and unpaid**, and it is now **ENG-547**. A number is searchable; a
paragraph is only found by whoever opens this file.

Short life and single use are the wrong defence for this, and that is why the gap matters
rather than merely existing: both work against **reuse** of one code. An attacker trying many
different codes is slowed by neither.

**What the row keeps.** The code is never stored. The row keeps a SHA-256 of it, which is
enough to recognise a replayed code as *spent* rather than *unknown* — the distinction
the log needs — while leaving no usable string in a table or a backup. Be honest about
what that buys: seven characters from a known alphabet is trivially brute-forced offline,
so the hash does not protect a code that leaks while it is still alive. What it protects
is every code afterwards, in every dump taken since, which is the case that actually
recurs.
"""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Final

CLAIM_CODE_TTL: Final = timedelta(minutes=15)

#: Twenty-five glyphs: A-Z and 0-9 with every spoken-collision pair removed.
CLAIM_CODE_ALPHABET: Final = "ACDEFGHJKMNPQRTUVWXY34679"

_HEAD_LENGTH: Final = 3
_TAIL_LENGTH: Final = 4


def utcnow() -> datetime:
    """The clock a claim code is minted and checked against.

    A seam, not an abstraction. The codebase has no clock service, and the pattern it
    already uses for time in tests is to replace a module-level function with
    ``monkeypatch.setattr`` — see ``tests/test_sound_necklace/test_working_time.py``.
    This is the smallest thing that matches it, which is why callers reach it through the
    module rather than importing the name.
    """
    return datetime.now(UTC)


def generate_claim_code() -> str:
    """A fresh code in the ``XXX-XXXX`` shape a facilitator reads out loud."""
    drawn = "".join(secrets.choice(CLAIM_CODE_ALPHABET) for _ in range(_HEAD_LENGTH + _TAIL_LENGTH))
    return f"{drawn[:_HEAD_LENGTH]}-{drawn[_HEAD_LENGTH:]}"


def hash_claim_code(code: str) -> str:
    """The value stored in the row, so that the code itself never is."""
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def has_expired(expires_at: datetime, *, at: datetime) -> bool:
    """Whether a code minted with ``expires_at`` is past its life at ``at``.

    SQLite hands back a naive datetime for a ``DateTime(timezone=True)`` column while
    Postgres hands back an aware one, and comparing the two raises. Reading the stored
    value as UTC is correct on both, because UTC is the only thing this ever writes.
    """
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    return at >= expires_at
