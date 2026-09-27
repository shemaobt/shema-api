"""BE-20 (OBT-525) — one token module for every link, held to what each of its functions promises.

The module exists because a token that reinvents its hash and its states is how one of them
ends up with no expiry. Each test below is one promise, with a fixture chosen so the wrong
implementation answers differently: ``token_hex(32)`` is 64 characters and not 43, a code
drawn as ``str(n)`` loses its zeros, the invite's order reads *used* where the leader link
reads *expired*. Each one was seen to fail against that wrong implementation before it was
trusted.
"""

from __future__ import annotations

import ast
import re
import secrets
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

import pytest

from app.services.auth.hash_refresh_token import hash_refresh_token
from app.services.common import tokens

NOW = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)
LIVE = NOW + timedelta(days=1)
DEAD = NOW - timedelta(days=1)
STAMP = NOW - timedelta(hours=1)

#: Every combination of (revoked, expired, used) and the one state it reads as — the whole
#: precedence, so no order that differs anywhere can pass it.
PRECEDENCE = [
    (True, True, True, "revoked"),
    (True, True, False, "revoked"),
    (True, False, True, "revoked"),
    (True, False, False, "revoked"),
    (False, True, True, "expired"),
    (False, True, False, "expired"),
    (False, False, True, "used"),
    (False, False, False, "pending"),
]
PRECEDENCE_IDS = [
    "+".join(n for n, on in zip(("revoked", "expired", "used"), case[:3], strict=True) if on)
    or "fresh"
    for case in PRECEDENCE
]


@dataclass
class _Row:
    expires_at: datetime
    revoked_at: datetime | None = None
    used_at: datetime | None = None


def _row(revoked: bool, expired: bool, used: bool) -> _Row:
    return _Row(
        expires_at=DEAD if expired else LIVE,
        revoked_at=STAMP if revoked else None,
        used_at=STAMP if used else None,
    )


# --- mint -----------------------------------------------------------------------------


def test_a_minted_token_is_256_bits_of_url_safe_text_paired_with_its_digest() -> None:
    raw, raw_digest = tokens.mint()

    assert re.fullmatch(r"[A-Za-z0-9_-]{43}", raw)
    assert raw_digest == tokens.digest(raw)
    assert re.fullmatch(r"[0-9a-f]{64}", raw_digest)


def test_no_two_mints_repeat() -> None:
    minted = [tokens.mint() for _ in range(100)]

    assert len({raw for raw, _ in minted}) == 100
    assert len({stored for _, stored in minted}) == 100


# --- digest ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [secrets.token_urlsafe(32), secrets.token_hex(32), "004217"],
    ids=["leader-link", "invite", "code"],
)
def test_a_token_stored_before_the_module_still_matches_its_digest(raw: str) -> None:
    """Every row written before BE-20 was hashed by ``hash_refresh_token``, and it is looked
    up by :func:`tokens.digest` now — a link already in someone's hands must still open."""
    assert tokens.digest(raw) == hash_refresh_token(raw)


# --- status ---------------------------------------------------------------------------


@pytest.mark.parametrize(("revoked", "expired", "used", "expected"), PRECEDENCE, ids=PRECEDENCE_IDS)
def test_status_reads_revoked_over_expired_over_used_over_pending(
    revoked: bool, expired: bool, used: bool, expected: str
) -> None:
    assert tokens.status(_row(revoked, expired, used), NOW) == expected


def test_a_token_dies_at_the_instant_its_clock_reaches() -> None:
    assert tokens.status(_Row(expires_at=NOW), NOW) == "expired"
    assert tokens.status(_Row(expires_at=NOW + timedelta(microseconds=1)), NOW) == "pending"


def test_a_stored_expiry_with_no_offset_is_read_as_utc() -> None:
    """SQLite hands a ``timestamptz`` back naive; compared raw against an aware clock it
    raises instead of answering."""
    ahead = (NOW + timedelta(seconds=1)).replace(tzinfo=None)
    behind = (NOW - timedelta(seconds=1)).replace(tzinfo=None)

    assert tokens.status(_Row(expires_at=ahead), NOW) == "pending"
    assert tokens.status(_Row(expires_at=behind), NOW) == "expired"


# --- expiry ---------------------------------------------------------------------------


def test_expiry_adds_the_life_in_the_unit_it_is_named_in() -> None:
    assert tokens.expiry(NOW, days=14) == NOW + timedelta(days=14)
    assert tokens.expiry(NOW, seconds=60) == NOW + timedelta(seconds=60)


@pytest.mark.parametrize(
    ("call", "error"),
    [
        (lambda: tokens.expiry(NOW), ValueError),
        (lambda: tokens.expiry(NOW, days=1, seconds=1), ValueError),
        (lambda: tokens.expiry(NOW, 60), TypeError),
        (lambda: tokens.expiry(NOW, seconds=0), ValueError),
        (lambda: tokens.expiry(NOW, days=-1), ValueError),
        (lambda: tokens.expiry(NOW.replace(tzinfo=None), days=1), ValueError),
    ],
    ids=["no-unit", "two-units", "bare-number", "zero-life", "negative-life", "naive-clock"],
)
def test_expiry_refuses_what_it_cannot_date_honestly(call, error) -> None:
    with pytest.raises(error):
        call()


# --- mint_code ------------------------------------------------------------------------


def test_a_code_is_six_digits_and_keeps_its_leading_zeros(monkeypatch) -> None:
    for _ in range(50):
        assert re.fullmatch(r"[0-9]{6}", tokens.mint_code()[0])

    monkeypatch.setattr(secrets, "randbelow", lambda bound: 42)
    code, code_digest = tokens.mint_code()

    assert code == "000042"
    assert code_digest == tokens.digest("000042")


def test_a_code_is_drawn_by_secrets_from_the_whole_million(monkeypatch) -> None:
    """A draw over 100000 to 999999 never starts with a zero, and a tenth of the codes are gone."""
    bounds: list[int] = []
    draws = iter([0, 999_999])

    def draw(bound: int) -> int:
        bounds.append(bound)
        return next(draws)

    monkeypatch.setattr(secrets, "randbelow", draw)

    assert [tokens.mint_code()[0] for _ in range(2)] == ["000000", "999999"]
    assert bounds == [10**6, 10**6]


# --- the leader link, the module's first consumer -------------------------------------


@pytest.mark.parametrize(("revoked", "expired", "used", "expected"), PRECEDENCE, ids=PRECEDENCE_IDS)
def test_the_leader_link_reads_its_state_through_the_module(
    revoked: bool, expired: bool, used: bool, expected: str
) -> None:
    """The same vector as the module's, over the leader link's own row and its own reader."""
    from app.db.models.shema_form import ShemaIntakeLink
    from app.services.shema._intake_tokens import link_status

    row = _row(revoked, expired, used)
    link = ShemaIntakeLink(
        expires_at=row.expires_at, revoked_at=row.revoked_at, used_at=row.used_at
    )

    assert link_status(link, now=NOW) == expected


def _imported_modules(tree: ast.AST) -> set[str]:
    """Every module a file imports, with ``from a import b`` read as both ``a`` and ``a.b``."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
            names.update(f"{node.module}.{alias.name}" for alias in node.names)
    return names


def test_the_leader_link_has_no_mint_or_hash_of_its_own() -> None:
    """**The DoD's third line, read off the source.** ``tests/test_shema/`` proves the link
    behaves as it did; this proves it does so through the module and not beside it — a
    ``secrets`` or a hash imported back into the file is a second mint, and the next token
    copies whichever one it finds first."""
    source = (
        Path(__file__).resolve().parents[1] / "app" / "services" / "shema" / "_intake_tokens.py"
    )
    imported = _imported_modules(ast.parse(source.read_text(encoding="utf-8")))

    assert "app.services.common.tokens" in imported, "the scan did not read the leader link"
    assert imported.isdisjoint({"secrets", "hashlib", "app.services.auth.hash_refresh_token"}), (
        sorted(imported & {"secrets", "hashlib", "app.services.auth.hash_refresh_token"})
    )


@pytest.mark.parametrize(("ceiling", "days"), [(90, 45), (30, 30)], ids=["shipped", "lowered"])
def test_a_coordinator_who_states_nothing_gets_the_default_or_the_ceiling_whichever_is_shorter(
    monkeypatch, ceiling: int, days: int
) -> None:
    """The ceiling is a configuration key since BE-20, so it can be set below the default —
    and a coordinator who stated no date must then get a shorter link, not a refusal about a
    date they never gave."""
    from app.core.exceptions import ValidationError
    from app.services.shema import _intake_tokens

    monkeypatch.setattr(_intake_tokens, "MAX_LINK_DAYS", ceiling)
    today = date(2026, 9, 27)

    last_day = today + timedelta(days=days)
    assert _intake_tokens.expiry_from(None, today=today) == datetime.combine(
        last_day + timedelta(days=1), time.min, tzinfo=UTC
    )
    with pytest.raises(ValidationError):
        _intake_tokens.expiry_from(today + timedelta(days=ceiling + 1), today=today)
