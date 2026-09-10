# ruff: noqa: RUF001 — the expectations are canon quoted verbatim; the en dash in a
# verse range is the character the map itself carries.
import json
import sys
from typing import Any

import pytest

from app.core.config import Settings
from app.db.models.internalization_room import IRPromptKey
from app.services.internalization_room._default_prompts import default_prompt
from app.services.internalization_room.canon.book_material import build_book_material
from app.services.internalization_room.run_turn import (
    run_panorama_turn,
    run_turn,
    run_verdict_turn,
)

GUIDE = default_prompt(IRPromptKey.GUIDE)["prompt"]
VALIDATOR = default_prompt(IRPromptKey.VALIDATOR)["prompt"]
VERDICT_SPEAKER = default_prompt(IRPromptKey.BT_VERDICT_SPEAKER)["prompt"]
PANORAMA = default_prompt(IRPromptKey.BOOK_PANORAMA)["prompt"]

#: The two prohibitions the ticket names, quoted from
#: `canon/vendor/compilation-log/P01-Ruth-1-1-5-COMPILATION-LOG.md`, never read back through
#: `preservation_rules` — an expectation the parser computes cannot disagree with the parser.
R6 = (
    "YHWH is not named as agent of any event in P01. The withholding is structural and "
    "intentional; it contrasts with the first divine action at 1:6 in P02. Reconstructor "
    "must not assign divine causation."
)
R10 = (
    "The source text does not pair the wives with their husbands at 1:4. Pairing is "
    "disclosed at 4:10. The MEANING_COORDINATES preserves the withholding via wife_taken: "
    "B? in P9 marriage_components. Reconstructor must not infer or state the pairing here."
)

#: Her heading and framing sentence, quoted from `src/turn/mapText.ts:102-104` in
#: `Tripod-Internalization`, so the expectation cannot be rebuilt the way the block is.
PROHIBITIONS = (
    "## PRESERVATION RULES — do_not_decide (HARD CONSTRAINTS)\n"
    "These are explicit prohibitions from the Compilation Log. The response must honor "
    "every one; a draft that violates any of these is ungrounded even if it sounds plausible."
)


ABSENCES = "## SIGNIFICANT ABSENCES (per scene — silences that must be preserved, never filled)"

#: The four silences of P01, quoted from the **Significant Absence** blocks of
#: `canon/vendor/meaning-map/P01-Ruth-1-1-5.md`, scene by scene.
P01_ABSENCES = (
    "- S1 (v.1–2): The narrator never says YHWH sent the famine or drove the family out. "
    "The book opens with no word of God doing anything.",
    "- S2 (v.3): The narrator points to no one as the cause of the death. No grief is "
    "described. No funeral or mourning is mentioned.",
    "- S3 (v.4): No children are born to either marriage in the ten years they live there. "
    "The narrator tells us how long it was, but says nothing of any child.",
    "- S4 (v.5): The narrator tells of no grief, no funeral, no one left to carry on the "
    "line, and no act of God. The losses are reported, and the line simply stops there.",
)


#: The two headings the Validator's own prompt puts around the map slot
#: (`prompts/validator_system_prompt.md:127,131`).
MAP_SLOT = "## The Meaning Map (the only standard of truth)"
NEXT_SLOT = "## Recent conversation"


#: Her operational sentence for the panorama's preservation header, quoted from
#: `app/lib/liveTurn.ts:191-192` in `Tripod-Internalization`.
HONOUR = (
    "The team has not yet lived any passage: every one of these still lies ahead of them. "
    "The panorama must honor each — never state, pair, name, or attribute what a passage "
    "withholds until its moment."
)


#: The story-so-far usage note as the ticket quotes it from `app/lib/liveTurn.ts:108-110`.
GROUNDED = (
    "Grounded material: it may be used to answer the team's questions about the story so "
    "far and to situate the current passage in the book. Nothing beyond these passages and "
    "the current map exists."
)


def _settings() -> Settings:
    return Settings(database_url="sqlite+aiosqlite:///./test.db", google_api_key="fake")


class FakeAgent:
    def __init__(self, draft: str = "Vamos ouvir a passagem."):
        self.draft = draft
        self.systems: list[str] = []

    async def __call__(self, *, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        self.systems.append(system_prompt)
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return self.draft


@pytest.fixture
def patch_agent(monkeypatch: pytest.MonkeyPatch):
    module = sys.modules["app.services.internalization_room.run_turn"]

    def _install(agent: FakeAgent) -> FakeAgent:
        monkeypatch.setattr(module, "call_agent", agent)
        return agent

    return _install


async def _systems(
    agent: FakeAgent,
    pericope_num: str = "P01",
    session_language: str = "Portuguese",
    language_code: str = "pt",
) -> tuple[str, str]:
    await run_turn(
        transcript="",
        coverage_state={},
        messages=[],
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        pericope_num=pericope_num,
        book="Ruth",
        session_language=session_language,
        language_code=language_code,
        opening=True,
        settings=_settings(),
    )
    return agent.systems[0], agent.systems[1]


async def test_the_withholdings_reach_the_validator_as_constraints_not_only_as_beads(
    patch_agent,
) -> None:
    guide_system, validator_system = await _systems(patch_agent(FakeAgent()))

    assert R6 in validator_system, (
        "a proibição de agência divina virava conta de cobertura e parava ali; o Validador "
        "julgava a passagem com o mesmo mapa do Guia, que não a carrega"
    )
    assert R10 in validator_system, (
        "sem a regra do pareamento, um rascunho dizendo que Rute casou com Malom não "
        "contradizia nada do que o Validador tinha em mãos"
    )
    assert PROHIBITIONS in validator_system, (
        "as regras sem o cabeçalho dela são mais uma seção de prosa; é a frase de "
        "enquadramento que diz que um rascunho plausível ainda assim é infundado"
    )
    assert PROHIBITIONS not in guide_system, (
        "o mapa do Guia é a fonte da narração, não a lista de proibições — o desenho dela "
        "separa os dois papéis exatamente aqui"
    )
    assert "- [preserved:R6] " in guide_system, (
        "o Guia já via R6, mas como conta a trabalhar na lista REMAINING, que some quando a "
        "equipe engaja a conta; era essa a única passagem da regra pelo prompt"
    )


async def test_every_scene_of_the_passage_names_its_silence_under_the_absences_heading(
    patch_agent,
) -> None:
    guide_system, validator_system = await _systems(patch_agent(FakeAgent()))

    assert ABSENCES in validator_system, (
        "as ausências já estavam no corpo do mapa, em prosa, espalhadas por quatro cenas; "
        "sem o cabeçalho dela nada dizia que eram silêncios a preservar"
    )
    for line in P01_ABSENCES:
        assert line in validator_system, (
            f"a cena {line[:6]} perdia o seu silêncio no caminho até o juiz"
        )
    assert ABSENCES not in guide_system, (
        "o Guia lê as ausências como prosa do mapa; a lista rotulada é do juiz"
    )


def _standard_of_truth(validator_system: str) -> str:
    """What sits in the Validator's map slot, cut out of a system the language does change."""
    opens = validator_system.index(MAP_SLOT) + len(MAP_SLOT)
    return validator_system[opens : validator_system.index(NEXT_SLOT, opens)]


async def test_the_two_new_blocks_read_the_same_in_a_portuguese_and_an_english_session(
    patch_agent,
) -> None:
    _, spoken_in_portuguese = await _systems(patch_agent(FakeAgent()))
    _, spoken_in_english = await _systems(
        patch_agent(FakeAgent()), session_language="English", language_code="en"
    )

    carried = _standard_of_truth(spoken_in_portuguese)

    assert PROHIBITIONS in carried and ABSENCES in carried, (
        "a fatia tem de ser o mapa mesmo; duas fatias vazias seriam iguais para sempre e o "
        "teste passaria sem olhar para nada"
    )
    assert carried == _standard_of_truth(spoken_in_english), (
        "o mapa é metadado em inglês dentro do prompt, e uma variante por língua faria a "
        "mesma passagem ser julgada contra dois textos diferentes"
    )


async def _verdict_systems(agent: FakeAgent) -> tuple[str, str]:
    await run_verdict_turn(
        findings_text="No que você me contou, Orfa não apareceu.",
        closing="Vamos ouvir de novo, em {session_language}.",
        scope="P01",
        pericope_num="P01",
        messages=[],
        speaker_prompt=VERDICT_SPEAKER,
        validator_prompt=VALIDATOR,
        book="Ruth",
        settings=_settings(),
    )
    return agent.systems[0], agent.systems[1]


async def test_the_verdict_is_judged_against_the_withholdings_its_speaker_never_reads(
    patch_agent,
) -> None:
    speaker_system, validator_system = await _verdict_systems(patch_agent(FakeAgent()))

    assert R6 in validator_system and R10 in validator_system, (
        "o veredito falava sobre a passagem julgado contra o mapa do Guia; uma emenda que "
        "reintroduzisse a agência divina ou o pareamento passava pelo mesmo buraco"
    )
    assert PROHIBITIONS in validator_system and ABSENCES in validator_system, (
        "o corte do veredito tem de ser o mesmo da passagem, senão o aperto vale num turno "
        "e não no outro"
    )
    assert R6 not in speaker_system and R10 not in speaker_system, (
        "o Speaker do veredito narra a partir da prosa, e aqui não há lista REMAINING para "
        "lhe mostrar a regra como conta a trabalhar"
    )


async def test_the_panorama_is_told_what_honouring_a_withholding_means(patch_agent) -> None:
    agent = patch_agent(FakeAgent("Vamos conhecer o livro."))

    await run_panorama_turn(
        transcript="o que é esse livro?",
        messages=[],
        panorama_prompt=PANORAMA,
        validator_prompt=VALIDATOR,
        book="Ruth",
        book_material=build_book_material("Ruth"),
        session_language="Portuguese",
        language_code="pt",
        settings=_settings(),
    )
    speaker_system, validator_system = agent.systems[0], agent.systems[1]

    assert HONOUR in speaker_system, (
        "o cabeçalho listava as retenções do livro sem dizer o que honrá-las quer dizer, e "
        "o panorama fala de catorze passagens que a equipe ainda não viveu"
    )
    assert HONOUR in validator_system, (
        "os dois papéis leem o mesmo material do livro; a frase que governa o uso da lista "
        "não pode chegar só a um deles"
    )


async def test_the_story_so_far_says_what_it_may_be_used_for_to_both_roles(patch_agent) -> None:
    guide_system, validator_system = await _systems(patch_agent(FakeAgent()), pericope_num="P02")

    assert GROUNDED in guide_system, (
        "os digests das passagens anteriores chegavam sob um título nu; nada dizia ao Guia "
        "que podia responder com eles, nem que fora deles não existe mais nada"
    )
    assert GROUNDED in validator_system, (
        "é a mesma nota que diz ao juiz que uma afirmação fundada numa passagem anterior "
        "está fundada — sem ela, o bloco é evidência sem estatuto"
    )
