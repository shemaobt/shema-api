"""The turn record's scene pointer is read with the team's history, as the pointer asks.

`current_scene_id` stopped naming a scene before the team has spoken and grew a third
argument for it; the record's caller still handed it two, and every real turn died with a
TypeError after the Guide had already spoken — the room went silent on a working
network. This pins the call.
"""

from app.api.internalization_room.sessions import _scene_of
from app.db.models.internalization_room import IRSession


def _session(messages: list[dict[str, str]]) -> IRSession:
    return IRSession(pericope="P01", language="pt", coverage_state={}, messages=messages)


def test_a_turn_on_a_fresh_session_names_no_scene() -> None:
    assert _scene_of(_session([])) is None


def test_a_turn_after_the_team_spoke_names_the_first_open_scene() -> None:
    spoken = [
        {"role": "guide", "text": "Olá, equipe."},
        {"role": "team", "text": "Teve fome em Belém e Elimeleque foi para Moabe."},
    ]
    assert _scene_of(_session(spoken)) == "S1"


def test_a_panorama_turn_names_no_scene() -> None:
    session = _session([{"role": "team", "text": "Que tipo de livro é esse?"}])
    session.pericope = "OV-Ruth"
    assert _scene_of(session) is None
