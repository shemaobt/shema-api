"""Stage 1 of ENG-753: kept retellings still wait on the Guide's verdict, not the
classifier's — this pins that the rendered prompt still asks for it.

`retelling.approved` has no reader yet (that is stage 2, its own ticket); this only pins
that the classifier is still asked for the judgment and still told which scenes exist.

Known gap, owned by stage 2 (ENG-986): the strict response schema handed to the model
(`classify_coverage._DECISIONS`, `required: ["decisions"]`, `additionalProperties: False`)
does not admit a `retelling` key, so today the prompt asks for a verdict the answer cannot
carry. That is the app's side to open, never the prompt's side to close.
"""

from __future__ import annotations

import pytest

from app.core.exceptions import ValidationError
from app.db.models.internalization_room import IRPromptKey
from app.services.internalization_room._default_prompts import default_prompt
from app.services.internalization_room.classify_coverage import _scenes_block
from app.services.internalization_room.render import render

P = "P01"
CLASSIFIER = default_prompt(IRPromptKey.COVERAGE_CLASSIFIER)["prompt"]


_SLOTS = {
    "SESSION_LANGUAGE": "English",
    "COVERAGE_ELEMENTS": "[]",
    "TEAM_UTTERANCE": "Naomi and her husband left Bethlehem for Moab because of the famine",
    "GUIDE_RESPONSE": "and then what happened to Elimelech",
}


def _rendered() -> str:
    return render(CLASSIFIER, SCENES=_scenes_block(P), **_SLOTS)


def test_the_rendered_classifier_prompt_still_carries_her_retelling_judgment_and_scenes() -> None:
    rendered = _rendered()

    assert "## One more judgment: the passing retelling (`retelling`)" in rendered, (
        "her retelling-verdict section still has to reach the model rendered, even though "
        "stage 1 gives `retelling.approved` no reader yet — the classifier is asked for it, "
        "the app just isn't listening"
    )
    assert '"retelling"' in rendered
    for scene_id, title in [
        ("S1", "Famine and exile to Moab"),
        ("S2", "Death of Elimelech"),
        ("S3", "Marriages and time passing"),
        ("S4", "Deaths of the sons"),
    ]:
        assert f'"id": "{scene_id}"' in rendered
        assert title in rendered


def test_her_scene_list_is_a_slot_the_classifier_cannot_be_rendered_without() -> None:
    # `render` refuses an unfilled placeholder rather than shipping it as literal text, so
    # the guard against a bare `{{SCENES}}` reaching the model is this error, not a grep.
    with pytest.raises(ValidationError, match="SCENES"):
        render(CLASSIFIER, **_SLOTS)
