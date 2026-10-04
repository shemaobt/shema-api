"""The correction check's prompt must not open the way the first rung refuses.

On 2026-09-16 the frontier rung answered ``stop_reason: refusal`` with no content to every
correction check, in under two seconds, for a prompt that had been answering for weeks on
its analyst sibling. Bisected by hand against the live API: the heading ``## Your role``
over the opening paragraph was what the classifier turned away — the same file with
``## Task`` in its place answered valid JSON every time. This pins the heading, so the
refusal cannot come back in a wording pass.
"""

from app.db.models.internalization_room import IRPromptKey
from app.services.internalization_room.prompts import get_prompt_text


def test_the_correction_check_does_not_open_with_the_heading_the_first_rung_refuses() -> None:
    prompt = get_prompt_text(IRPromptKey.BT_CORRECTION)
    assert not prompt.startswith("## Your role"), (
        "com esse cabeçalho o Fable 5.1 recusava a verificação da correção inteira, cinco vezes "
        "seguidas, e a sessão caía em 'precisa de uma pessoa' num turno em que a equipe acertou"
    )
    assert prompt.startswith("## Task")
