"""The station a saved state opens at.

``step_for`` is the only place the API decides where a session stands. It reads a
mapping the SPA produced and never checks it against domain rules: the client owns
what "review complete" means, and the API only reads the boolean it was handed.
"""

from __future__ import annotations

import pytest

from app.db.models.sound_necklace import SessionStep
from app.services.sound_necklace import step_for


def test_mapeamento_with_the_review_flag_reaches_the_saving_station():
    assert step_for({"mode": "mapeamento", "reviewComplete": True}) is SessionStep.SAVE


def test_mapeamento_without_the_flag_stays_in_the_conversation():
    """Every session saved before the flag existed, and every client yet to ship."""
    assert step_for({"mode": "mapeamento"}) is SessionStep.CONVERSATION


@pytest.mark.parametrize("value", ["false", "true", 1, None, {}, []])
def test_a_non_boolean_flag_counts_as_absent(value):
    """Truthiness would promote the string ``"false"``; only the literal boolean counts."""
    assert step_for({"mode": "mapeamento", "reviewComplete": value}) is SessionStep.CONVERSATION


@pytest.mark.parametrize(
    ("fields", "expected"),
    [
        ({"mode": "triagem"}, SessionStep.TRIAGE),
        ({"mode": "segmentacao"}, SessionStep.PHRASES),
        ({}, SessionStep.LISTEN),
        ({"whole": {"confirmed": True}}, SessionStep.CUT),
    ],
)
def test_the_flag_is_ignored_outside_mapeamento(fields, expected):
    """A stale flag must not let a session skip the station it is actually at."""
    assert step_for({**fields, "reviewComplete": True}) is expected
