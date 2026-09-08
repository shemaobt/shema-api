"""Every reading the analyst or the corrector accepts leaves a rastro, not only a recusa.

ENG-719 (#305) and #312 made a refused reply visible: unparseable JSON, an unknown finding
kind, a count with no verdict — all of it already reaches this logger as a WARNING. What was
still invisible was the opposite case: a reply that parses cleanly and is simply *wrong*. When
that happens the model's own words are gone the moment the call returns, and nobody can go back
and read what it actually said.

These cases are about the trace left behind, never about what the analyst or the corrector
decide — that is `test_internalization_room_back_translation.py`'s and
`test_ir_a_correction_is_verified_on_its_own.py`'s to hold. Read from `caplog`, and always by
field on the record (`record.__dict__[...]`, via `extra=`), never by matching the sentence: the
sentence is free to change, the fields the operator depends on are not.
"""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

import pytest

from app.core.config import Settings
from app.db.models.internalization_room import IRPromptKey, IRSegment
from app.services.internalization_room._default_prompts import default_prompt
from app.services.internalization_room.back_translation import (
    Finding,
    FindingKind,
    analyse_telling_back,
    verify_correction,
)

LOGGER_NAME = "app.services.internalization_room.back_translation"
ANALYST = default_prompt(IRPromptKey.BT_ANALYST)["prompt"]
CORRECTION = default_prompt(IRPromptKey.BT_CORRECTION)["prompt"]
P = "P03"
SESSION_ID = "sessao-do-rastro"


def _settings() -> Settings:
    return Settings(database_url="sqlite+aiosqlite:///./test.db", google_api_key="fake")


def _segment(number: int, text: str, *, segment_id: str | None = None) -> IRSegment:
    return IRSegment(
        id=segment_id or f"segmento-{number}",
        session_id=SESSION_ID,
        ordinal=number,
        take_id="ensaio-1",
        starts_ms=(number - 1) * 9000,
        ends_ms=number * 9000,
        transcript=text,
    )


def _told() -> list[IRSegment]:
    return [
        _segment(1, "Noemi mandou Rute voltar."),
        _segment(2, "Rute disse que ia junto."),
    ]


@pytest.fixture
def patch_model(monkeypatch: pytest.MonkeyPatch):
    """Answer the one call `analyse_telling_back`/`verify_correction` make, with `reply`."""
    module = sys.modules["app.services.internalization_room.back_translation"]

    def _install(reply: str):
        async def agent(*, system_prompt: str, user_content: str, **kwargs: Any) -> str:
            return reply

        monkeypatch.setattr(module, "call_agent", agent)
        return agent

    return _install


def _records(caplog: pytest.LogCaptureFixture, reading: str) -> list[logging.LogRecord]:
    return [
        record
        for record in caplog.records
        if record.name == LOGGER_NAME and record.__dict__.get("reading") == reading
    ]


@pytest.mark.asyncio
async def test_an_accepted_analysis_reading_leaves_an_info_record(
    patch_model, caplog: pytest.LogCaptureFixture
) -> None:
    raw = json.dumps(
        {
            "findings": [
                {"kind": "addition", "note": "você me disse que ela ficaria junto das servas"}
            ]
        }
    )
    patch_model(raw)

    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        analysis = await analyse_telling_back(
            segments=_told(),
            scope=P,
            pericope_num=P,
            analyst_prompt=ANALYST,
            settings=_settings(),
            session_id=SESSION_ID,
        )

    assert analysis is not None
    accepted = _records(caplog, "analysis")
    assert len(accepted) == 1, "uma leitura aceita deixa exatamente um record"
    record = accepted[0]
    assert record.levelno == logging.INFO
    assert record.__dict__["session_id"] == SESSION_ID
    assert record.__dict__["findings"] == 1
    assert raw in record.getMessage()


@pytest.mark.asyncio
async def test_an_accepted_correction_reading_leaves_an_info_record(
    patch_model, caplog: pytest.LogCaptureFixture
) -> None:
    raw = json.dumps(
        {
            "resolved": True,
            "findings": [],
            "carried": [{"element": "Boaz falou das servas", "still_told": True}],
        }
    )
    patch_model(raw)
    finding = Finding(
        kind=FindingKind.MEANING_CHANGE, note="Boaz não falou nisso", segment_id="segmento-1"
    )
    earlier = _segment(1, "Boaz fala pra Rute colher espigas em outros campos.")
    corrected = _segment(
        2, "Boaz fala pra Rute colher espigas somente no campo dele.", segment_id="segmento-2"
    )

    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        check = await verify_correction(
            finding=finding,
            earlier=earlier,
            corrected=corrected,
            scope=P,
            pericope_num=P,
            correction_prompt=CORRECTION,
            settings=_settings(),
            session_id=SESSION_ID,
        )

    assert check is not None
    accepted = _records(caplog, "correction")
    assert len(accepted) == 1, "uma verificação aceita deixa exatamente um record"
    record = accepted[0]
    assert record.levelno == logging.INFO
    assert record.__dict__["session_id"] == SESSION_ID
    assert record.__dict__["segment_id"] == corrected.id
    assert record.__dict__["resolved"] is True
    assert record.__dict__["findings"] == 0
    assert raw in record.getMessage()


@pytest.mark.asyncio
async def test_the_teams_own_words_do_not_reach_this_logger(
    patch_model, caplog: pytest.LogCaptureFixture
) -> None:
    """The rastro is what the model said, never what the team said.

    A marker planted in the team's own transcript, and nowhere in the model's reply, must
    not show up in this logger's text — that would mean the team's speech leaked into an
    operations log nobody agreed to.
    """
    marker = "MARCADOR-QUE-O-MODELO-NUNCA-CITA-7f3a"
    raw = json.dumps({"resolved": True, "findings": []})
    patch_model(raw)
    finding = Finding(kind=FindingKind.MISSING, note="Orfa não apareceu", segment_id="segmento-1")
    earlier = _segment(1, f"{marker} — a versão que a equipe contou antes.")
    corrected = _segment(
        2, f"{marker} — a nova versão que a equipe contou.", segment_id="segmento-2"
    )

    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        check = await verify_correction(
            finding=finding,
            earlier=earlier,
            corrected=corrected,
            scope=P,
            pericope_num=P,
            correction_prompt=CORRECTION,
            settings=_settings(),
            session_id=SESSION_ID,
        )

    assert check is not None
    logger_text = "\n".join(
        record.getMessage() for record in caplog.records if record.name == LOGGER_NAME
    )
    assert marker not in logger_text


@pytest.mark.asyncio
async def test_a_refused_reading_leaves_only_the_refusal_trace(
    patch_model, caplog: pytest.LogCaptureFixture
) -> None:
    """A reply that cannot be trusted at all must not also count as an accepted reading."""
    patch_model("desculpe, não consigo comparar isso")

    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        analysis = await analyse_telling_back(
            segments=_told(),
            scope=P,
            pericope_num=P,
            analyst_prompt=ANALYST,
            settings=_settings(),
            session_id=SESSION_ID,
        )

    assert analysis is None
    same_logger = [record for record in caplog.records if record.name == LOGGER_NAME]
    assert len(same_logger) == 1, "a recusa é o único rastro; não deixa um segundo record"
    assert same_logger[0].levelno == logging.WARNING
    assert same_logger[0].__dict__.get("reading") is None
