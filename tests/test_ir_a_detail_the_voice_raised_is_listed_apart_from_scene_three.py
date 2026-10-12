from app.services.internalization_room.canon.elements import elements_for
from app.services.internalization_room.coverage import initial_state, merge
from app.services.internalization_room.prompt_blocks import coverage_status_block

P = "P01"

SCENE_ONE_ENGAGED_SCENE_TWO_SILENCE_RAISED = """\
LEDGER (the app's notes — information only; you decide what comes next)

WORKED WITH BY THE TEAM (engaged): S1 (v.1\N{EN DASH}2); Elimelech; Naomi; Mahlon; \
Chilion; Judges; Ephrathites; Bethlehem; Fields of Moab; the land of Judah; Famine; sojourning; \
In the Days When the Judges Judged; absence @ S1

RAISED BY YOU, NOT YET TAKEN UP BY THE TEAM:
  significant_absence: absence @ S2

NOT YET TOUCHED (still deserve a visit before the session ends):
  arc: Level-1 arc
  context: Level-1 context
  tone: Level-1 tone
  function: Level-1 function
  scene: S2 (v.3), S3 (v.4), S4 (v.5)
  being: Elimelech, Naomi, Mahlon, Chilion, Women of Moab, Orpah, Ruth, the woman
  place: Fields of Moab
  object: about ten years
  significant_absence: absence @ S3, absence @ S4
  preserved_element: R3, R5, R10"""


def test_a_scene_two_detail_the_voice_raised_is_listed_apart_from_scene_three_untouched() -> None:
    scene_one = [element.key for element in elements_for(P) if element.scene == 1]
    state = merge(initial_state(P), pericope_num=P, engaged=scene_one, surfaced=["absence:2"])

    assert coverage_status_block(state, P) == SCENE_ONE_ENGAGED_SCENE_TWO_SILENCE_RAISED, (
        "o que a voz levantou na cena 2 ia junto com o que ninguém tocou da cena 3"
    )
