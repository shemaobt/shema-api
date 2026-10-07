from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.services import internalization_room as room
from app.services.internalization_room.llm import CACHE_BREAK
from tests.text_seam_harness import RUNNER_KEY, the_app
from tests.turn_harness import the_room_agent_is

SEAM = "/api/internalization-room/text-seam/back-translation"
PASSAGE = "P02"
LANGUAGE = "Brazilian Portuguese"
CLIPS = [
    {"key": "S1", "durationMs": 20000},
    {"key": "S2", "durationMs": 25000},
    {"key": "S3", "durationMs": 45000},
]
TELLING = [
    {
        "clipKey": "S1",
        "coversFrom": 0,
        "coversTo": 20,
        "text": "Noemi ouviu que o Senhor tinha dado pão ao seu povo e voltou com as noras.",
    },
    {
        "clipKey": "S2",
        "coversFrom": 0,
        "coversTo": 25,
        "text": "No caminho ela mandou as noras de volta, beijou as duas, e elas choraram alto.",
    },
    {
        "clipKey": "S3",
        "coversFrom": 0,
        "coversTo": 45,
        "text": "Orfa beijou a sogra e voltou, mas Rute se agarrou a Noemi à noite.",
    },
]
SAID = "No que vocês me traduziram, tem tudo o que a história conta — e nada a mais."


class Analyst:
    def __init__(self) -> None:
        self.readings: list[dict[str, Any]] = []
        self.asked: list[dict[str, Any]] = []

    async def __call__(self, **call: Any) -> str:
        self.asked.append(call)
        return json.dumps(self.readings.pop(0) if self.readings else {"findings": []})


class Speaker:
    def __init__(self) -> None:
        self.drafts: list[dict[str, Any]] = []
        self.validations: list[str] = []

    async def __call__(self, **call: Any) -> str:
        if "corrected_response" in call["system_prompt"]:
            self.validations.append(call["system_prompt"])
            return json.dumps({"verdict": "pass", "issues": []})
        self.drafts.append(call)
        return SAID


@pytest.fixture()
def analyst(monkeypatch: pytest.MonkeyPatch) -> Analyst:
    reader = Analyst()
    the_room_agent_is(monkeypatch, analyst=reader)
    return reader


@pytest.fixture()
def speaker(monkeypatch: pytest.MonkeyPatch) -> Speaker:
    voice = Speaker()
    the_room_agent_is(monkeypatch, turn=voice)
    return voice


@pytest.fixture()
async def client(
    db_session: AsyncSession,
    analyst: Analyst,
    speaker: Speaker,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        get_settings(), "internalization_room_runner_key", RUNNER_KEY, raising=False
    )

    async def _never_voiced(text: str, **_: Any) -> None:
        raise AssertionError(f"a costura pediu um clipe ao sintetizador: {text!r}")

    monkeypatch.setattr(room, "synthesize_facilitator_speech", _never_voiced)

    async with httpx.AsyncClient(
        transport=ASGITransport(app=the_app(db_session)),
        base_url="http://test",
        headers={"X-Access-Code": RUNNER_KEY},
    ) as c:
        yield c


async def _a_round(client: httpx.AsyncClient, frases: list[dict], session_id: str = "") -> dict:
    if not session_id:
        declared = await client.post(
            f"{SEAM}/session", json={"pericopeId": PASSAGE, "language": LANGUAGE, "clips": CLIPS}
        )
        assert declared.status_code == 200, declared.text
        session_id = str(declared.json()["sessionId"])
    played = await client.post(f"{SEAM}/round", json={"sessionId": session_id, "frases": frases})
    assert played.status_code == 200, played.text
    return dict(played.json())


async def test_the_analyst_is_asked_with_her_closing_request_not_ours(client, analyst) -> None:
    await _a_round(client, TELLING)

    assert [call["user_content"] for call in analyst.asked] == [
        "Analyze the telling-back now. Return only the JSON object."
    ], "o analista era chamado com o nosso «Compare a tradução com o mapa.»"


HER_KICKOFF = (
    "(The team heard their whole recording, told it back frase by frase, and tapped "
    "'terminei'. Speak the verdict now.)"
)


async def test_the_verdict_opens_on_her_kickoff_with_no_history_and_the_validator_reads_it(
    client, speaker
) -> None:
    first = await _a_round(client, TELLING)
    retold = {**TELLING[2], "supersedes": 2}

    await _a_round(client, [retold], session_id=first["sessionId"])

    later = speaker.drafts[-1]
    assert later["user_content"] == HER_KICKOFF, "o veredito abria com o nosso «Speak this turn.»"
    assert not later.get("conversation"), (
        "o veredito era redigido com a conversa inteira; o dela não tem histórico"
    )
    assert (
        "## WHAT THE TEAM JUST SAID (evidence — NEVER truth about the passage)\n\n"
        "The drafted response answers this. Referring to these words is not a claim about the "
        f"passage.\n\n{HER_KICKOFF}"
    ) in speaker.validations[-1], "o Validador não lia o pontapé dela como o que a equipe disse"


def _handed(speaker: Speaker) -> str:
    system = speaker.drafts[-1]["system_prompt"].replace(CACHE_BREAK, "")
    return system.split(f"## The findings for {PASSAGE}\n\n", 1)[1]


async def test_a_clean_round_hands_her_speaker_an_empty_list_and_says_only_her_words(
    client, speaker
) -> None:
    result = await _a_round(client, TELLING)

    assert _handed(speaker) == "[]", "a rodada limpa entregava a nossa frase «(nenhum achado …)»"
    assert result["spoken"] == SAID
    assert result["conferida"] is True
    sent = speaker.drafts[-1]["system_prompt"]
    for ours in ("wood disc", "green check", "two voices side by side", "OBT Refine"):
        assert ours not in sent, ours


async def test_a_missing_detail_reaches_her_speaker_with_the_frase_it_follows_and_no_part(
    client, analyst, speaker
) -> None:
    analyst.readings = [
        {"findings": [{"kind": "missing", "note": "Não ouvi a volta de Orfa.", "frase": 2}]}
    ]

    await _a_round(client, TELLING)

    assert _handed(speaker) == (
        "[\n"
        "  {\n"
        '    "kind": "missing",\n'
        '    "note": "Não ouvi a volta de Orfa.",\n'
        '    "frase": 2,\n'
        '    "repair": "part"\n'
        "  }\n"
        "]"
    ), "o falante recebia a nossa linha «- missing [frase 2 — …]: …», não o JSON dela"


async def test_an_addition_reaches_her_speaker_with_its_part_and_nothing_of_ours_follows(
    client, analyst, speaker
) -> None:
    analyst.readings = [
        {"findings": [{"kind": "addition", "note": "Ela voltou «à noite».", "frase": 3}]}
    ]

    result = await _a_round(client, TELLING)

    assert json.loads(_handed(speaker)) == [
        {
            "kind": "addition",
            "note": "Ela voltou «à noite».",
            "frase": 3,
            "part": "a parte 3 — O segundo apelo e a separação",
            "repair": "part",
        }
    ], "o falante recebia o endereço nosso, com «das frases N a M», não a parte dela"
    assert result["spoken"] == SAID, "a sala colava a nossa frase «I» depois do veredito"


async def test_a_retold_frase_is_judged_by_her_analyst_over_the_whole_telling(
    client, analyst
) -> None:
    analyst.readings = [
        {"findings": [{"kind": "addition", "note": "Ela voltou «à noite».", "frase": 3}]},
        {"findings": []},
    ]
    first = await _a_round(client, TELLING)
    retold = {
        **TELLING[2],
        "text": "Orfa beijou a sogra e voltou, mas Rute ficou.",
        "supersedes": 2,
    }

    result = await _a_round(client, [retold], session_id=first["sessionId"])

    assert [call["user_content"] for call in analyst.asked] == [
        "Analyze the telling-back now. Return only the JSON object."
    ] * 2, "uma frase traduzida de novo ia para a nossa verificação da correção"
    whole = analyst.asked[-1]["system_prompt"]
    assert all(frase["text"] in whole for frase in [*TELLING[:2], retold])
    assert result["conferida"] is True


A_NUANCE = {
    "kind": "nuance",
    "note": "O tempo ficou solto.",
    "frase": 3,
    "quote": "à noite",
    "story": "foi naquela mesma noite",
}


async def test_a_telling_with_only_a_nuance_hands_her_speaker_that_nuance_and_stays_conferida(
    client, analyst, speaker
) -> None:
    analyst.readings = [{"findings": [A_NUANCE]}]

    result = await _a_round(client, TELLING)

    assert json.loads(_handed(speaker)) == [
        {
            "kind": "nuance",
            "note": "O tempo ficou solto.",
            "frase": 3,
            "quote": "à noite",
            "story": "foi naquela mesma noite",
            "part": "a parte 3 — O segundo apelo e a separação",
            "repair": "part",
        }
    ], "a nuance era lida e jogada fora: o falante dizia a rodada limpa"
    assert result["conferida"] is True, "uma nuance nunca impede a aprovação"


async def test_a_nuance_beside_an_addition_waits_and_only_the_addition_reaches_her_speaker(
    client, analyst, speaker
) -> None:
    an_addition = {"kind": "addition", "note": "Ela voltou com as noras.", "frase": 1}
    analyst.readings = [{"findings": [A_NUANCE, an_addition]}]

    result = await _a_round(client, TELLING)

    assert [one["kind"] for one in json.loads(_handed(speaker))] == ["addition"], (
        "a nuance chegava ao falante ao lado de um achado que bloqueia"
    )
    assert result["conferida"] is False


async def test_a_nuance_quoting_words_its_frase_does_not_hold_is_dropped_alone(
    client, analyst, speaker
) -> None:
    analyst.readings = [{"findings": [{**A_NUANCE, "quote": "naquela noite"}]}]

    result = await _a_round(client, TELLING)

    assert _handed(speaker) == "[]", "a voz citava como da equipe palavras que a frase dela não tem"
    assert result["conferida"] is True
