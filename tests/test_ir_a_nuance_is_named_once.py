from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.services import internalization_room as room
from app.services.internalization_room import verdict_round
from app.services.internalization_room.llm import CACHE_BREAK
from app.services.internalization_room.sessions import get_session, start_the_translation_over
from tests.text_seam_harness import RUNNER_KEY, the_app
from tests.turn_harness import the_room_agent_is

SEAM = "/api/internalization-room/text-seam/back-translation"
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
CLEAN = "No que vocês me traduziram, tem tudo o que a história conta — e nada a mais."
ON_FRASE_3 = {
    "kind": "nuance",
    "note": "O tempo ficou solto.",
    "frase": 3,
    "quote": "à noite",
    "story": "foi naquela mesma noite",
}
NAMES_FRASE_3 = (
    "Só um detalhe, na frase 3: vocês traduziram «à noite»; a história conta que foi naquela "
    "mesma noite."
)


class Analyst:
    def __init__(self) -> None:
        self.readings: list[dict[str, Any]] = []
        self.read = 0

    async def __call__(self, **_: Any) -> str:
        self.read += 1
        return json.dumps(self.readings.pop(0) if self.readings else {"findings": []})


class Speaker:
    def __init__(self) -> None:
        self.line = CLEAN
        self.drafts: list[str] = []
        self.verdicts: list[str] = []

    async def __call__(self, *, system_prompt: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            if self.verdicts:
                return self.verdicts.pop(0)
            return json.dumps({"verdict": "pass", "issues": []})
        self.drafts.append(system_prompt.replace(CACHE_BREAK, ""))
        return self.line


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
    db_session: AsyncSession, analyst: Analyst, speaker: Speaker, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        get_settings(), "internalization_room_runner_key", RUNNER_KEY, raising=False
    )
    async with httpx.AsyncClient(
        transport=ASGITransport(app=the_app(db_session)),
        base_url="http://test",
        headers={"X-Access-Code": RUNNER_KEY},
    ) as c:
        yield c


async def _a_round(client: httpx.AsyncClient, frases: list[dict], session_id: str = "") -> dict:
    if not session_id:
        declared = await client.post(
            f"{SEAM}/session",
            json={"pericopeId": "P02", "language": "Brazilian Portuguese", "clips": CLIPS},
        )
        assert declared.status_code == 200, declared.text
        session_id = str(declared.json()["sessionId"])
    played = await client.post(f"{SEAM}/round", json={"sessionId": session_id, "frases": frases})
    assert played.status_code == 200, played.text
    return dict(played.json())


async def _the_kept_rounds(db_session: AsyncSession, session_id: str) -> list:
    return room.back_translation_of(await room.get_session(db_session, session_id)).checks


async def test_a_round_that_names_a_nuance_keeps_its_frase_words_story_and_that_it_was_said(
    client, analyst, speaker, db_session
) -> None:
    analyst.readings = [{"findings": [ON_FRASE_3]}]
    speaker.line = NAMES_FRASE_3

    result = await _a_round(client, TELLING)

    kept = await _the_kept_rounds(db_session, result["sessionId"])
    assert [
        [(one.chunk, one.quote, one.story, one.voiced) for one in check.nuances] for check in kept
    ] == [[(3, "à noite", "foi naquela mesma noite", "now")]], (
        "a nuance da rodada só existia na memória do pedido e sumia com a resposta"
    )


@pytest.mark.parametrize(
    "line",
    [
        "Só um detalhe: vocês traduziram «à noite»; a história conta outra coisa.",
        "Só um detalhe, na frase 30: vocês traduziram «à noite».",
    ],
    ids=["no frase", "another number"],
)
async def test_a_validated_verdict_that_never_says_the_frase_leaves_the_nuance_unsaid(
    client, analyst, speaker, db_session, line
) -> None:
    analyst.readings = [{"findings": [ON_FRASE_3]}]
    speaker.line = line

    result = await _a_round(client, TELLING)

    kept = await _the_kept_rounds(db_session, result["sessionId"])
    assert [one.voiced for one in kept[0].nuances] == [None], (
        "a nuance contava como dita sem que a voz tivesse dito o número da frase"
    )


async def test_a_nuance_verdict_fallen_to_the_fail_safe_is_spoken_clean_and_the_nuance_stays_unsaid(
    client, analyst, speaker, db_session
) -> None:
    analyst.readings = [{"findings": [ON_FRASE_3]}]
    speaker.line = NAMES_FRASE_3
    speaker.verdicts = ["isto não é um veredito"]

    result = await _a_round(client, TELLING)

    assert len(speaker.drafts) == 2
    assert result["conferida"] is True
    kept = await _the_kept_rounds(db_session, result["sessionId"])
    assert [one.voiced for one in kept[0].nuances] == [None], (
        "a nuance cujo veredito caiu na linha A contava como dita pela rodada limpa"
    )


async def test_every_round_the_seam_plays_counts_as_heard_to_its_end(
    client, analyst, speaker, db_session
) -> None:
    analyst.readings = [{"findings": [ON_FRASE_3]}]
    speaker.line = NAMES_FRASE_3

    result = await _a_round(client, TELLING)

    kept = await _the_kept_rounds(db_session, result["sessionId"])
    assert kept[0].heard_at is not None, (
        "o roteiro dourado nunca ouvia o veredito e a mesma nuance voltava a cada rodada"
    )
    assert kept[0].heard_at >= kept[0].at


def _handed(speaker: Speaker, run: int = -1) -> list[dict]:
    return list(
        json.loads(speaker.drafts[run].split("## The findings for the whole passage\n\n")[1])
    )


FRASE_1_AGAIN = {
    **TELLING[0],
    "text": "Noemi soube que havia pão e voltou com as noras.",
    "supersedes": 0,
}


async def test_a_nuance_heard_to_its_end_is_never_handed_again_and_the_round_says_it_was_before(
    client, analyst, speaker, db_session
) -> None:
    analyst.readings = [{"findings": [ON_FRASE_3]}, {"findings": [ON_FRASE_3]}]
    speaker.line = NAMES_FRASE_3
    first = await _a_round(client, TELLING)

    await _a_round(client, [FRASE_1_AGAIN], session_id=first["sessionId"])

    assert _handed(speaker) == [], "a mesma nuance, já ouvida até o fim, era dita de novo"
    kept = await _the_kept_rounds(db_session, first["sessionId"])
    assert [[one.voiced for one in check.nuances] for check in kept] == [["now"], ["before"]]


async def test_a_second_different_detail_on_a_frase_whose_first_was_said_is_named_in_its_turn(
    client, analyst, speaker, db_session
) -> None:
    another_on_frase_3 = {
        **ON_FRASE_3,
        "note": "Quem segura quem mudou.",
        "quote": "Rute se agarrou",
        "story": "Rute ficou com ela",
    }
    analyst.readings = [{"findings": [ON_FRASE_3]}, {"findings": [ON_FRASE_3, another_on_frase_3]}]
    speaker.line = NAMES_FRASE_3
    first = await _a_round(client, TELLING)

    await _a_round(client, [FRASE_1_AGAIN], session_id=first["sessionId"])

    assert [one["quote"] for one in _handed(speaker)] == ["Rute se agarrou"], (
        "uma nuance era a sua frase: um segundo detalhe na mesma frase nunca era dito"
    )


@pytest.mark.parametrize("copy", ["a Noemi à noite", "noite"], ids=["longer", "shorter"])
async def test_a_longer_or_shorter_copy_of_the_said_words_on_the_same_frase_is_the_same_detail(
    client, analyst, speaker, copy
) -> None:
    analyst.readings = [{"findings": [ON_FRASE_3]}, {"findings": [{**ON_FRASE_3, "quote": copy}]}]
    speaker.line = NAMES_FRASE_3
    first = await _a_round(client, TELLING)

    await _a_round(client, [FRASE_1_AGAIN], session_id=first["sessionId"])

    assert _handed(speaker) == [], (
        "o Analista copiava um trecho maior ou menor e a mesma nuance era dita de novo"
    )


async def test_the_same_words_already_said_placed_on_another_current_frase_count_as_said(
    client, analyst, speaker
) -> None:
    frase_1_at_night = {
        **TELLING[0],
        "text": "Noemi soube que havia pão e voltou com as noras à noite.",
        "supersedes": 0,
    }
    analyst.readings = [{"findings": [ON_FRASE_3]}, {"findings": [{**ON_FRASE_3, "frase": 1}]}]
    speaker.line = NAMES_FRASE_3
    first = await _a_round(client, TELLING)

    await _a_round(client, [frase_1_at_night], session_id=first["sessionId"])

    assert _handed(speaker) == [], (
        "o Analista punha o mesmo detalhe uma frase ao lado e a voz o dizia de novo"
    )


async def test_a_frase_translated_again_on_the_same_audio_keeps_its_nuance_said(
    client, analyst, speaker, db_session
) -> None:
    analyst.readings = [
        {"findings": [ON_FRASE_3]},
        {"findings": [{**ON_FRASE_3, "quote": "a Noemi à noite"}]},
    ]
    speaker.line = NAMES_FRASE_3
    first = await _a_round(client, TELLING)

    await _a_round(client, [{**TELLING[2], "supersedes": 2}], session_id=first["sessionId"])

    assert _handed(speaker) == [], (
        "traduzir a frase de novo sobre o mesmo áudio fazia a voz dizer a nuance outra vez"
    )


def _reported(result: dict) -> list[tuple[str, int | None, str]]:
    return [(one["kind"], one["frase"], one["note"]) for one in result["findings"]]


async def test_the_round_reports_an_unsaid_nuance_beside_a_blocking_finding(
    client, analyst, speaker
) -> None:
    an_addition = {"kind": "addition", "note": "Ela voltou com as noras.", "frase": 1}
    analyst.readings = [{"findings": [an_addition, ON_FRASE_3]}]

    result = await _a_round(client, TELLING)

    assert _reported(result) == [
        ("addition", 1, "Ela voltou com as noras."),
        ("nuance", 3, "«à noite» — foi naquela mesma noite"),
    ], "o roteiro dourado nunca via a nuance que esperava, calada ao lado do acréscimo"


async def test_the_round_reports_the_nuance_it_named_and_the_one_said_before(
    client, analyst, speaker
) -> None:
    analyst.readings = [{"findings": [ON_FRASE_3]}, {"findings": [ON_FRASE_3]}]
    speaker.line = NAMES_FRASE_3

    first = await _a_round(client, TELLING)
    second = await _a_round(client, [FRASE_1_AGAIN], session_id=first["sessionId"])

    assert _reported(first) == [("nuance", 3, "«à noite» — foi naquela mesma noite")]
    [kept] = second["findings"]
    assert (kept["kind"], kept["frase"], kept["voiced"]) == ("nuance", 3, "before"), (
        "a nuance dita numa rodada anterior sumia da lista da rodada seguinte"
    )


async def test_a_round_with_nothing_new_after_a_heard_nuance_is_a_new_round_on_the_same_reading(
    client, analyst, speaker, db_session
) -> None:
    analyst.readings = [{"findings": [ON_FRASE_3]}]
    speaker.line = NAMES_FRASE_3
    first = await _a_round(client, TELLING)
    speaker.line = CLEAN

    again = await _a_round(client, [], session_id=first["sessionId"])

    assert analyst.read == 1, "uma rodada sem nada novo pedia outra leitura ao Analista"
    assert (again["spoken"], again["conferida"]) == (CLEAN, True), (
        "o roteiro dela apertava terminei de novo e a costura recusava a rodada"
    )
    assert [(one["kind"], one["voiced"]) for one in again["findings"]] == [("nuance", "before")]
    kept = await _the_kept_rounds(db_session, first["sessionId"])
    assert [[one.voiced for one in check.nuances] for check in kept] == [["now"], ["before"]]


async def test_a_round_with_nothing_new_after_a_clean_round_is_served_the_verdict_already_reached(
    client, analyst, speaker, db_session
) -> None:
    first = await _a_round(client, TELLING)
    speaker.line = "outra coisa"

    again = await _a_round(client, [], session_id=first["sessionId"])

    assert (again["spoken"], again["conferida"]) == (CLEAN, True), (
        "a costura falava de novo onde terminei serve o veredito já dado"
    )
    assert len(speaker.drafts) == 1
    assert len(await _the_kept_rounds(db_session, first["sessionId"])) == 1


async def _a_round_a_restart_lands_in(
    client: httpx.AsyncClient,
    rival_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> dict:
    declared = await client.post(
        f"{SEAM}/session",
        json={"pericopeId": "P02", "language": "Brazilian Portuguese", "clips": CLIPS},
    )
    session_id = str(declared.json()["sessionId"])
    written = verdict_round.append_exchange

    async def written_after_a_restart(*args: Any, **kwargs: Any) -> Any:
        async with rival_factory() as restarting_db:
            await start_the_translation_over(
                restarting_db, await get_session(restarting_db, session_id)
            )
        return await written(*args, **kwargs)

    monkeypatch.setattr(verdict_round, "append_exchange", written_after_a_restart)
    return await _a_round(client, TELLING, session_id=session_id)


async def test_a_round_a_restart_lands_in_answers_without_the_nuance_the_restart_cleared(
    client,
    analyst,
    speaker,
    rival_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analyst.readings = [{"findings": [ON_FRASE_3]}]
    speaker.line = NAMES_FRASE_3

    result = await _a_round_a_restart_lands_in(client, rival_factory, monkeypatch)

    assert [one["kind"] for one in result["findings"]] == [], (
        "a rodada em que o recomeço caiu devolvia a nuance que o recomeço já tinha apagado"
    )


async def test_a_round_a_restart_lands_in_answers_without_the_finding_the_restart_cleared(
    client,
    analyst,
    speaker,
    rival_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    an_addition = {"kind": "addition", "note": "Ela voltou com as noras.", "frase": 1}
    analyst.readings = [{"findings": [an_addition]}]

    result = await _a_round_a_restart_lands_in(client, rival_factory, monkeypatch)

    assert (result["findings"], result["findingsRemaining"]) == ([], 0), (
        "a rodada em que o recomeço caiu devolvia o achado que o recomeço já tinha apagado"
    )


async def test_a_press_on_a_verdict_stored_before_rounds_were_kept_is_read_again_not_served(
    client,
    analyst,
    speaker,
    rival_factory: async_sessionmaker[AsyncSession],
) -> None:
    first = await _a_round(client, TELLING)
    async with rival_factory() as legacy_db:
        legacy = await get_session(legacy_db, first["sessionId"])
        legacy.back_translation = {**legacy.back_translation, "checks": []}
        await legacy_db.commit()
    speaker.line = "outra coisa"

    again = await _a_round(client, [], session_id=first["sessionId"])

    assert (len(speaker.drafts), again["spoken"]) == (2, "outra coisa"), (
        "o veredito guardado sem rodada nenhuma derrubava a costura em vez de ser lido de novo"
    )
