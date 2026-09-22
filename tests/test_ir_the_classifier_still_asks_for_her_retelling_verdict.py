"""Stage 1 of ENG-753: kept retellings still wait on the Guide's verdict, not the
classifier's — this pins that the rendered prompt still asks for it.

`retelling.approved` has no reader yet (that is stage 2, its own ticket); this only pins
that the classifier is still asked for the judgment and still told which scenes exist.
"""

from __future__ import annotations

from app.db.models.internalization_room import IRPromptKey
from app.services.internalization_room._default_prompts import default_prompt
from app.services.internalization_room.classify_coverage import _scenes_block
from app.services.internalization_room.render import render

P = "P01"
CLASSIFIER = default_prompt(IRPromptKey.COVERAGE_CLASSIFIER)["prompt"]


def _rendered() -> str:
    return render(
        CLASSIFIER,
        SESSION_LANGUAGE="English",
        SCENES=_scenes_block(P),
        COVERAGE_ELEMENTS="[]",
        TEAM_UTTERANCE="Naomi and her husband left Bethlehem for Moab because of the famine",
        GUIDE_RESPONSE="and then what happened to Elimelech",
    )


def test_the_rendered_classifier_prompt_still_carries_her_retelling_judgment_and_scenes() -> None:
    rendered = _rendered()

    assert "## One more judgment: the passing retelling (`retelling`)" in rendered, (
        "her retelling-verdict section still has to reach the model rendered, even though "
        "stage 1 gives `retelling.approved` no reader yet — the classifier is asked for it, "
        "the app just isn't listening"
    )
    assert '"retelling"' in rendered
    assert "{{SCENES}}" not in rendered, (
        "the placeholder itself must not survive rendering — the model would read it as "
        "literal text instead of the passage's actual scenes"
    )
    for scene_id, title in [
        ("S1", "Famine and exile to Moab"),
        ("S2", "Death of Elimelech"),
        ("S3", "Marriages and time passing"),
        ("S4", "Deaths of the sons"),
    ]:
        assert f'"id": "{scene_id}"' in rendered
        assert title in rendered
