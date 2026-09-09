"""A `missing` finding names `where` it sits, and the server turns that into an address.

The analyst answers only with the telling-back it was given, never the recording, and it
cannot echo a stretch id back reliably — so it names a chunk and now also `where` the
missing content sits relative to that chunk (`before` / `inside` / `after`). This is the
server-side half: `_segment_pointed_at` reading `where` into the address table the product
owner asked for, exercised the way `test_the_analyst_pointer_is_resolved_to_the_stretch_it_names`
in `test_internalization_room_back_translation.py` exercises the plain `chunk` case.
"""

import logging
import sys
from typing import Any

import pytest

from app.core.config import Settings
from app.db.models.internalization_room import IRPromptKey, IRSegment
from app.services.internalization_room._default_prompts import default_prompt
from app.services.internalization_room.back_translation import (
    CLOSING_MISSING_TO_REHEARSAL,
    FindingKind,
    analyse_telling_back,
    closing_block,
)

ANALYST = default_prompt(IRPromptKey.BT_ANALYST)["prompt"]
P = "P03"


def _settings() -> Settings:
    return Settings(database_url="sqlite+aiosqlite:///./test.db", google_api_key="fake")


def _segment(number: int, text: str) -> IRSegment:
    return IRSegment(
        id=f"segmento-{number}",
        session_id="sessao-1",
        ordinal=number,
        take_id="ensaio-1",
        starts_ms=(number - 1) * 9000,
        ends_ms=number * 9000,
        transcript=text,
    )


def _told() -> list[IRSegment]:
    """Five stretches, in listening order — Rute 1:15-18 minus the verse nobody told."""
    return [
        _segment(1, "Noemi disse a elas: voltem para a casa de suas maes."),
        _segment(2, "Orfa beijou Noemi e voltou."),
        _segment(3, "Rute disse que ia junto, aonde Noemi fosse."),
        _segment(4, "Rute jurou ficar com Noemi ate a morte."),
        _segment(5, "Noemi viu que Rute estava decidida."),
    ]


@pytest.fixture
def patch_analyst(monkeypatch: pytest.MonkeyPatch):
    module = sys.modules["app.services.internalization_room.back_translation"]

    def _install(reply: str):
        async def agent(*, system_prompt: str, user_content: str, **kwargs: Any) -> str:
            agent.system = system_prompt
            return reply

        monkeypatch.setattr(module, "call_agent", agent)
        return agent

    return _install


async def _findings_for(reply: str, patch_analyst):
    patch_analyst(reply)
    analysis = await analyse_telling_back(
        segments=_told(),
        scope=P,
        pericope_num=P,
        analyst_prompt=ANALYST,
        settings=_settings(),
    )
    assert analysis is not None
    return analysis.findings


@pytest.mark.asyncio
async def test_after_on_the_last_chunk_sends_the_team_to_rehearsal(patch_analyst) -> None:
    """Case 1: nothing to point at past the last chunk, and the room goes on recording."""
    findings = await _findings_for(
        '{"findings":['
        '{"kind":"missing","chunk":5,"where":"after","note":"o juramento fica, mas o fim nao"}'
        "]}",
        patch_analyst,
    )

    assert findings[0].segment_id is None
    assert closing_block(findings[0]) == CLOSING_MISSING_TO_REHEARSAL


@pytest.mark.asyncio
async def test_after_in_the_middle_points_at_the_next_chunk(patch_analyst) -> None:
    """Case 2: missing after chunk 3 is missing at the start of chunk 4."""
    findings = await _findings_for(
        '{"findings":[{"kind":"missing","chunk":3,"where":"after","note":"faltou algo"}]}',
        patch_analyst,
    )

    assert findings[0].segment_id == "segmento-4"


@pytest.mark.asyncio
async def test_inside_points_at_the_named_chunk(patch_analyst) -> None:
    """Case 3 (guard): the missing content is inside the chunk itself."""
    findings = await _findings_for(
        '{"findings":[{"kind":"missing","chunk":3,"where":"inside","note":"faltou algo"}]}',
        patch_analyst,
    )

    assert findings[0].segment_id == "segmento-3"


@pytest.mark.asyncio
async def test_before_on_the_first_chunk_points_at_the_first_chunk(patch_analyst) -> None:
    """Case 4 (guard): before chunk 1 is still chunk 1 — there is no chunk 0."""
    findings = await _findings_for(
        '{"findings":[{"kind":"missing","chunk":1,"where":"before","note":"faltou o inicio"}]}',
        patch_analyst,
    )

    assert findings[0].segment_id == "segmento-1"


@pytest.mark.asyncio
async def test_without_where_the_chunk_is_used_as_is(patch_analyst) -> None:
    """Case 5 (guard): a reply with no `where` at all keeps today's behaviour."""
    findings = await _findings_for(
        '{"findings":[{"kind":"missing","chunk":5,"note":"faltou algo"}]}',
        patch_analyst,
    )

    assert findings[0].segment_id == "segmento-5"


@pytest.mark.asyncio
async def test_a_null_chunk_still_sends_the_team_to_rehearsal(patch_analyst) -> None:
    """Case 5 (guard): a legacy `null` chunk still means no stretch to point at."""
    findings = await _findings_for(
        '{"findings":[{"kind":"missing","chunk":null,"note":"faltou algo"}]}',
        patch_analyst,
    )

    assert findings[0].segment_id is None


@pytest.mark.asyncio
async def test_an_unrecognised_where_is_ignored_and_leaves_a_trace(
    patch_analyst, caplog: pytest.LogCaptureFixture
) -> None:
    """Case 6: a `where` the table does not name falls back to naming the chunk, and warns."""
    with caplog.at_level(
        logging.WARNING, logger="app.services.internalization_room.back_translation"
    ):
        findings = await _findings_for(
            '{"findings":[{"kind":"missing","chunk":3,"where":"sideways","note":"faltou algo"}]}',
            patch_analyst,
        )

    assert findings[0].segment_id == "segmento-3"
    assert any(
        record.levelno == logging.WARNING and "sideways" in record.getMessage()
        for record in caplog.records
    )


@pytest.mark.asyncio
async def test_other_kinds_ignore_where(patch_analyst) -> None:
    """Case 7 (guard): `where` only means something for a `missing` finding."""
    findings = await _findings_for(
        '{"findings":[{"kind":"meaning_change","chunk":2,"where":"after","note":"mudou"}]}',
        patch_analyst,
    )

    assert findings[0].kind is FindingKind.MEANING_CHANGE
    assert findings[0].segment_id == "segmento-2"
