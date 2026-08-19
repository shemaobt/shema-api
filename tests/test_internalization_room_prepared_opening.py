"""The passage's first line, written while the team is still hearing the panorama.

Every other turn waits on what the team just said. The opening does not — the team has not
spoken, the coverage is untouched, the conversation is empty — so it is the one line that can
be written before it is asked for. Doing that turns a five-second wait into none.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSession, IRSessionStatus
from app.services.internalization_room.prepare_opening import hand_over, take_prepared


def _session(**over: object) -> IRSession:
    fields: dict[str, object] = {
        "id": "s1",
        "pericope": "P01",
        "status": IRSessionStatus.IN_PROGRESS,
        "messages": [],
        "coverage_state": {},
        "kept_takes": {},
        "back_translation": {},
    }
    fields.update(over)
    return IRSession(**fields)


def test_a_ready_line_is_handed_to_the_session_that_speaks_it() -> None:
    panorama = _session(id="ov", prepared_speech="Olá.", prepared_audio_key="tts/x.mp3")
    passage = _session(id="p")

    assert hand_over(panorama, passage) is True
    assert passage.prepared_speech == "Olá."
    assert passage.prepared_audio_key == "tts/x.mp3"


def test_a_panorama_still_writing_hands_over_nothing() -> None:
    """The team may enter before it is ready; then the session simply writes its own."""
    assert hand_over(_session(id="ov"), _session(id="p")) is False


def test_half_a_line_is_not_a_line() -> None:
    only_text = _session(id="ov", prepared_speech="Olá.")
    assert hand_over(only_text, _session(id="p")) is False

    only_audio = _session(id="ov", prepared_audio_key="tts/x.mp3")
    assert hand_over(only_audio, _session(id="p")) is False


@pytest.mark.asyncio
async def test_the_prepared_line_is_spoken_once_and_then_gone(db_session: AsyncSession) -> None:
    """A second turn must never repeat the opening — it is consumed when taken."""
    session = _session(prepared_speech="Olá.", prepared_audio_key="tts/x.mp3")
    db_session.add(session)
    await db_session.commit()

    assert await take_prepared(db_session, session) == ("Olá.", "tts/x.mp3")
    assert await take_prepared(db_session, session) is None


@pytest.mark.asyncio
async def test_a_session_with_nothing_prepared_says_so(db_session: AsyncSession) -> None:
    session = _session()
    db_session.add(session)
    await db_session.commit()

    assert await take_prepared(db_session, session) is None


def test_the_prepared_line_belongs_to_the_passage_it_was_written_for() -> None:
    """It is written from one passage's meaning map, and delivered as that passage's words.

    A team choosing P03 heard P01's opening as P03's framing, to people who cannot read
    and have no way to check.
    """
    panorama = IRSession(id="ov", pericope="OV-Ruth")
    panorama.prepared_speech = "a primeira fala da P01"
    panorama.prepared_audio_key = "tts/v/p01.mp3"

    outra = IRSession(id="s2", pericope="P03")

    assert hand_over(panorama, outra) is False
    assert outra.prepared_speech is None


def test_a_prepared_line_is_handed_over_once() -> None:
    panorama = IRSession(id="ov", pericope="OV-Ruth")
    panorama.prepared_speech = "a primeira fala"
    panorama.prepared_audio_key = "tts/v/p01.mp3"

    first = IRSession(id="s1", pericope="P01")
    second = IRSession(id="s2", pericope="P01")

    assert hand_over(panorama, first) is True
    assert hand_over(panorama, second) is False, (
        "a origem nunca era limpa, então a mesma fala ia para toda sessão seguinte"
    )
