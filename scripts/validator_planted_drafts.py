"""Her planted drafts B6 to B13 against the Validator the room sends, judged by her bar.

uv run python scripts/validator_planted_drafts.py
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass

from app.core.config import get_settings
from app.db.models.internalization_room import IRPromptKey
from app.services.internalization_room.llm import call_agent
from app.services.internalization_room.prompt_blocks import validator_map_block
from app.services.internalization_room.prompts import get_prompt_text
from app.services.internalization_room.turn_instructions import VALIDATOR_USER_MESSAGE
from app.services.internalization_room.validated_turn import her_validator
from app.services.internalization_room.validator_reply import _parse_verdict

LANGUAGE = "Brazilian Portuguese"


@dataclass(frozen=True)
class Planted:
    id: str
    draft: str
    must_pass: bool
    why: str
    team: str = ""
    uncounted: str = ""


PLANTED = (
    Planted(
        id="B6 withheld pairing inside a question",
        draft=(
            "Os dois filhos casaram com mulheres de Moabe, Orfa e Rute. E quando Rute se casou "
            "com Malom, o que mudou para Noemi?"
        ),
        must_pass=False,
        why="the question presupposes who married whom — the text withholds this until 4:10",
    ),
    Planted(
        id="B7 divine cause inside a question",
        draft="Veio uma fome na terra, e a família saiu de Belém. Por que Deus mandou a fome?",
        must_pass=False,
        why="the question presupposes God sent the famine — the map keeps the cause absent",
    ),
    Planted(
        id="B8 the team's addition adopted and built on",
        draft="Isso, vocês lembraram bem. E quando Malom morreu, como ficou a Rute, a mulher dele?",
        must_pass=False,
        why=(
            "affirms the team's pairing as a fact of the passage and builds the next question on it"
        ),
        team="A Rute casou com o Malom, né?",
    ),
    Planted(
        id="B9 the team's words given back as theirs",
        draft=(
            "Vocês disseram que a Rute casou com o Malom. Isso a história não conta. Ela só diz "
            "que Malom e Quiliom tomaram mulheres de Moabe, e que os nomes eram Orfa e Rute. De "
            "onde veio essa ideia pra vocês?"
        ),
        must_pass=True,
        why=(
            "quotes the team to name the addition and asks where it came from — must pass untouched"
        ),
        team="A Rute casou com o Malom, né?",
    ),
    Planted(
        id="B10 open question standing on the map",
        draft=(
            "No fim, a mulher ficou sem os dois filhos dela e sem o marido dela. O que vocês "
            "acham que Noemi está sentindo?"
        ),
        must_pass=True,
        why=(
            "asks what a character feels where the story does not say — legitimate (ruling "
            "2026-09-21), must pass untouched"
        ),
    ),
    Planted(
        id="B11 invitation to talk and tell back",
        draft=(
            "Conversem entre vocês. O que vocês sentiram ouvindo essa história, uma perda depois "
            "da outra? Depois me contem com as palavras de vocês o que acontece nessa parte."
        ),
        must_pass=True,
        why="questions and invitations that carry nothing unsupported — must pass untouched",
    ),
    Planted(
        id="B12 the team's EARLIER words given back (not in the latest utterance)",
        draft=(
            "Vocês disseram antes que a Rute casou com o Malom. Isso a história não conta. Ela "
            "só diz que os dois filhos tomaram mulheres de Moabe, e que os nomes eram Orfa e "
            "Rute. Vamos seguir?"
        ),
        must_pass=True,
        why=(
            "attributes the pairing to what the team said before and denies it — a legitimate "
            "quote-back"
        ),
        team="Tá bom. Pode continuar.",
        uncounted=(
            "observation — the Validator sees only the latest utterance; a fix would be its "
            "input (history), not prompt wording"
        ),
    ),
    Planted(
        id="B13 feeling stated as the story's own inside a question",
        draft=(
            "No fim, a mulher ficou sem os dois filhos dela e sem o marido dela. A história "
            "conta que Noemi ficou desesperada quando os filhos morreram — como vocês contariam "
            "esse desespero?"
        ),
        must_pass=False,
        why=(
            "the question says the story tells Naomi's despair — the map marks that grief as "
            "unsaid (S4 absence, R7)"
        ),
    ),
)


async def run() -> int:
    settings = get_settings()
    meaning_map = validator_map_block("P01", "Ruth")
    failed = 0
    for planted in PLANTED:
        raw = await call_agent(
            role="validator",
            system_prompt=her_validator(
                validator_prompt=get_prompt_text(IRPromptKey.VALIDATOR),
                meaning_map=meaning_map,
                team_side=planted.team,
                draft=planted.draft,
                session_language=LANGUAGE,
            ),
            user_content=VALIDATOR_USER_MESSAGE,
            max_output_tokens=4096,
            settings=settings,
        )
        verdict, refusal = _parse_verdict(raw)
        passed = refusal is None and verdict["verdict"] == "pass"
        held = refusal is None and passed == planted.must_pass
        expected = "pass" if planted.must_pass else "not pass"
        said = f"verdict={verdict.get('verdict', refusal)}"
        if planted.uncounted:
            mark = "○" if held else "△"
            print(f"  {mark} {planted.id} — {said} [NOT COUNTED: {planted.uncounted}; {expected}]")
        else:
            failed += not held
            print(f"  {'✓' if held else '✗'} {planted.id} — {planted.why} — {said}")
        for issue in verdict.get("issues") or []:
            print(f"        flagged: {issue}")
        if verdict.get("corrected_response"):
            print(f"        corrected: {verdict['corrected_response']}")
    print(f"{len(PLANTED)} drafts, {failed} off her bar")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
