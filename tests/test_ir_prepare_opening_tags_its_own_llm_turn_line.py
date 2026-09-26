"""`prepare_opening` names its own turn on the seam that logs it, not just at the seam itself.

`validated_turn._timed` can tag a turn's `[llm-turn]` line as prepared, but only for whoever
tells it to. This is the other half: `prepare_opening` is the one caller that must, and it
must tell it the pericope it actually resolved — never the constant `pericope_num` some other
call happens to be judging against, because in this call they are the same thing but nothing
enforces that they always will be.
"""

from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSession, IRSessionStatus
from app.services.internalization_room import prepare_opening as prepare_opening_module
from app.services.internalization_room.prepare_opening import prepare_opening
from app.services.internalization_room.run_turn import TurnOutcome


def _panorama(**over: object) -> IRSession:
    fields: dict[str, object] = {
        "id": "panorama-1",
        "pericope": "OV-Ruth",
        "status": IRSessionStatus.IN_PROGRESS,
        "messages": [],
        "coverage_state": {},
        "kept_takes": {},
        "back_translation": {},
        "language": "pt",
    }
    fields.update(over)
    return IRSession(**fields)


async def test_prepare_opening_tags_its_run_turn_call_with_the_pericope_it_resolved(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_session.add(_panorama())
    await db_session.commit()

    seen: dict[str, Any] = {}

    async def _spy(**kwargs: Any) -> TurnOutcome:
        seen.update(kwargs)
        return TurnOutcome(speech="", transcript="", used_fail_safe=True)

    monkeypatch.setattr(prepare_opening_module, "run_turn", _spy)

    await prepare_opening("panorama-1", pericope="P01")

    assert seen["prepared_pericope"] == "P01"
