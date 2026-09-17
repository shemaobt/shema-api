"""The Guide's coverage block is her three parts, in labels a Guide can say.

Every turn the Guide was handed a REMAINING list and nothing else — one line per element,
each carrying the internal key in brackets and the audit kind in capitals. It was never told
which scene the team was in, nor what they had already worked, so it guessed, reopened
finished scenes, and could read `preserved:R6` aloud into a room with no screen. DOCTRINE
§2.1: the app owns "the coverage ledger … All of it information; none of it instruction."
"""

from app.services.internalization_room.canon.elements import ElementKind, elements_for
from app.services.internalization_room.coverage import (
    CoverageStatus,
    current_scene,
    initial_state,
    merge,
)

P = "P01"


def _scene_keys(scene: int) -> list[str]:
    return [element.key for element in elements_for(P) if element.scene == scene]


def _engaged(*keys: str) -> dict[str, str]:
    return merge(initial_state(P), pericope_num=P, engaged=list(keys))


def test_the_scene_pointer_is_read_off_the_ledger_not_off_the_planner() -> None:
    """Scene 1 finished and scene 2 begun puts the team in scene 2, whatever was said."""
    nothing = initial_state(P)
    scene_one_done = _engaged(*_scene_keys(1))
    scene_two_begun = _engaged(*_scene_keys(1), "scene:2")
    every_scene = _engaged(*(key for n in (1, 2, 3, 4) for key in _scene_keys(n)))

    assert current_scene(nothing, P) is None, (
        "no turno zero o Guia lia CURRENT SCENE = Scene 1 antes de a equipe abrir a boca"
    )
    assert current_scene(scene_one_done, P) == "S2"
    assert current_scene(scene_two_begun, P) == "S2"
    assert current_scene(every_scene, P) is None, (
        "com toda cena engajada não há cena para apontar — é a integração da passagem"
    )


def test_a_bead_short_of_engaged_holds_the_pointer_on_its_scene() -> None:
    scene_one_echoed = {
        **_engaged(*_scene_keys(1)),
        next(key for key in _scene_keys(1) if key.startswith(ElementKind.ABSENCE)): (
            CoverageStatus.SURFACED.value
        ),
    }

    assert current_scene(scene_one_echoed, P) == "S1", (
        "a ausência só levantada pelo Guia deixava a cena 1 para trás como feita"
    )
