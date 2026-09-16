"""Her judge reads every golden session this runner plays, and its verdict is the gate.

Five transcripts in hand and nobody scoring them is the reading that produced the 3 September
demo failure. Her rubric and her pass rule are already written — `golden_judge_system_prompt.md`,
"the acceptance test that guards the app's behaviour across model and prompt changes" — and
they arrive here as bytes she wrote, under the pin, and are applied as she wrote them: the
judge's column beside the mechanical one, never one laundered into the other.
"""

from __future__ import annotations

from scripts.sync_doctrine import REPO_ROOT, VENDORED, digest

HER_JUDGE_PROMPT = "4a03febee00949c40207ada18b84600ac7897353fcc3eccd2d49feef85b8f026"
VENDORED_JUDGE_PROMPT = (
    "app/services/internalization_room/prompts/vendor/golden_judge_system_prompt.md"
)


def test_her_judge_prompt_is_vendored_byte_for_byte_under_the_pin() -> None:
    ours = VENDORED["prompts/golden_judge_system_prompt.md"]

    assert ours == VENDORED_JUDGE_PROMPT, (
        "o prompt do juiz mora ao lado dos outros dela, nunca entre os nossos"
    )
    assert digest((REPO_ROOT / ours).read_bytes()) == HER_JUDGE_PROMPT, (
        "os bytes vendorizados não são os do ramo dela no pin — o sha foi lido do checkout dela"
    )
