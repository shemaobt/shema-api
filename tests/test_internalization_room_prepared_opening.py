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


def test_the_line_is_handed_over_only_once() -> None:
    """A second session opened after the same panorama must not be given the same opening."""
    panorama = _session(id="ov", prepared_speech="Olá.", prepared_audio_key="tts/x.mp3")

    assert hand_over(panorama, _session(id="p1")) is True
    assert panorama.prepared_speech is None
    assert panorama.prepared_audio_key is None
    assert hand_over(panorama, _session(id="p2")) is False


def test_another_passage_is_not_given_the_first_passage_line() -> None:
    """The panorama writes ahead for P01 only; P03 would hear P01's framing as its own."""
    panorama = _session(id="ov", prepared_speech="Olá.", prepared_audio_key="tts/x.mp3")
    other = _session(id="p", pericope="P03")

    assert hand_over(panorama, other) is False
    assert other.prepared_speech is None
    assert panorama.prepared_speech == "Olá."


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
