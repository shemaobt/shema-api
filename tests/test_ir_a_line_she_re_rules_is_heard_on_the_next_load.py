from __future__ import annotations

from collections.abc import Callable, Iterator
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.services.internalization_room import fail_safe
from app.services.platform import tts
from tests.release_harness import KEY, PREFIX, a_claimed_device, team_headers
from tests.room_harness import room_client

THE_TABLET = {"X-Room-Key": KEY}

ACKS_AS_RULED = """
### F. Instant acknowledgements

- "Mm-hm."
- "Okay."
- "Mmm — let me think about that for a moment."
- "Right."

### F-pt. (Português brasileiro)

- "Hmm."
- "Certo."
- "Deixa eu pensar um instante."
- "Tá."
"""

HER_PROCESS_LINES_AT_18FA7C4 = "\n\n".join(
    f"### {family}.\n\n" + "\n".join(f'- "{line}"' for line in lines)
    for family, lines in {
        "P": (
            (
                "First let's listen to your whole recording, from beginning to end. For now, "
                "just listen."
            ),
            (
                "Now let's go back to the beginning. You will listen to your recording and, at "
                "each sentence, pause to translate for me only what was said there. Tap the "
                "circle to pause, translate, and tap again so the recording goes on. Don't add "
                "anything and don't explain; it doesn't need to sound nice. Say in English "
                "exactly what that sentence says. Pause wherever it helps you remember what was"
                " said so you can translate it. When the whole recording has been translated, "
                "tap 'done'."
            ),
            "There is still a part of the recording to listen to before I check.",
            (
                "Approved as the team's final draft. The next step is the external check: tap "
                "the 'external check' button below and call in the listeners."
            ),
        ),
        "P-pt": (
            (
                "Primeiro vamos ouvir a gravação de vocês inteira, do começo ao fim. Por "
                "enquanto é só ouvir."
            ),
            (
                "Agora vamos voltar ao começo. Vocês vão ouvir a gravação de vocês e, a cada "
                "frase, pausar para me traduzir só o que foi dito ali. Toquem no círculo para "
                "pausar, traduzam, e toquem de novo para a gravação seguir. Não acrescentem "
                "nada e não expliquem; não precisa ficar bonito. Digam em português exatamente "
                "o que aquela frase diz. Façam as pausas onde for melhor para vocês lembrarem "
                "do que foi dito e traduzirem. Quando a gravação inteira estiver traduzida, "
                "toquem em 'terminei'."
            ),
            "Ainda falta ouvir um trecho da gravação antes de eu conferir.",
            (
                "Aprovado como rascunho final da equipe. O próximo passo é a checagem externa: "
                "toquem no botão 'checagem externa', aqui embaixo, e chamem os ouvintes."
            ),
        ),
        "X": (
            (
                "Now it's the turn of those who didn't help translate. What you say here is "
                "recorded, only for the team to hear afterwards. You will hear the whole "
                "passage. Then I'll ask what you understood. There is no right answer: what you"
                " understood is what matters."
            ),
            (
                "Now tell me, in your own way, what you heard. It doesn't need to be perfect, "
                "tell what you remember. Tap the circle to speak and tap again when you finish."
            ),
            (
                "Did anything stay unclear? Would you like to comment on anything about the "
                "whole passage? If so, tap the circle and speak, as many times as you want. If "
                "not, tap 'continue'."
            ),
            (
                "Now, listen to the sentences one by one. When you hear a sentence, if you "
                "think it is good, tap the 'it's good' button. But if you think the sentence "
                "needs to change in some way, or if you think it is not clear, tap the circle "
                "again and make your comment."
            ),
            "Thank you for your help. What you said is kept for the team to hear.",
        ),
        "X-pt": (
            (
                "Agora é a vez de quem não ajudou a traduzir. O que vocês disserem aqui fica "
                "gravado, só para a equipe ouvir depois. Vocês vão ouvir a passagem inteira. "
                "Depois eu pergunto o que vocês entenderam. Não tem resposta certa: o que vocês"
                " entenderam é o que importa."
            ),
            (
                "Agora me contem, do jeito de vocês, o que vocês ouviram. Não precisa ser "
                "perfeito, conte o que você se lembrar. Toquem no círculo para falar e toquem "
                "de novo quando terminarem."
            ),
            (
                "Alguma coisa não ficou clara? Querem comentar alguma coisa sobre a passagem "
                "inteira? Se sim, toquem no círculo e falem, quantas vezes quiserem. Se não, "
                "toquem em 'continuar'."
            ),
            (
                "Agora, escute as frases uma por uma. Quando ouvir uma frase, se achar que ela "
                "está boa, clique no botão 'está boa'. Mas se achar que a frase precisa mudar "
                "em alguma coisa, ou se achar que ela não está clara, clique novamente no "
                "círculo e faça o seu comentário."
            ),
            "Agradecemos sua ajuda. O que vocês disseram fica guardado para a equipe ouvir.",
        ),
    }.items()
)


class Bucket:
    def __init__(self) -> None:
        self.kept: dict[str, bytes] = {}

    async def get(self, key: str) -> bytes | None:
        return self.kept.get(key)

    async def exists(self, key: str) -> bool:
        return key in self.kept

    async def put(self, key: str, data: bytes, content_type: str) -> bytes:
        return self.kept.setdefault(key, data)


class ElevenLabs:
    def __init__(self) -> None:
        self.voiced: list[str] = []

    async def post(self, url: str, *, json: dict[str, Any], **_: Any) -> SimpleNamespace:
        self.voiced.append(json["text"])
        return SimpleNamespace(status_code=200, content=f"voz:{json['text']}".encode(), text="")


@pytest.fixture
def elevenlabs(monkeypatch: pytest.MonkeyPatch) -> ElevenLabs:
    from app.api.internalization_room import voice as voice_api

    voice, bucket = ElevenLabs(), Bucket()
    monkeypatch.setattr(get_settings(), "elevenlabs_api_key", "fake-elevenlabs", raising=False)
    monkeypatch.setattr(tts, "_make_client", lambda: voice)
    monkeypatch.setattr(tts, "_default_store", lambda _: bucket)
    monkeypatch.setattr(voice_api, "GcsPlatformStore", lambda _: bucket)
    return voice


@pytest.fixture
def deploy(monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[[str], None]]:
    def deployed(her_file: str) -> None:
        monkeypatch.setattr(fail_safe, "fail_safe_utterances", lambda: her_file)
        fail_safe._sections.cache_clear()
        tts.forget_what_is_kept()

    yield deployed
    fail_safe._sections.cache_clear()


async def heard(client: httpx.AsyncClient, line: str, language: str) -> tuple[str, str]:
    asked = await client.get(
        f"{PREFIX}/fixed-lines/{line}", params={"language": language}, headers=THE_TABLET
    )
    assert asked.status_code == 200, asked.text
    address = asked.json()["audio_url"]
    clip = await client.get(address, headers=THE_TABLET)
    assert clip.status_code == 200, clip.text
    return address, clip.content.decode()


async def test_a_re_ruled_acknowledgement_is_heard_in_its_new_words_on_the_next_load(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    elevenlabs: ElevenLabs,
    deploy: Callable[[str], None],
) -> None:
    deploy(ACKS_AS_RULED)
    async with room_client(db_session, monkeypatch) as client:
        _, before = await heard(client, "F2", "pt")
        deploy(ACKS_AS_RULED.replace("Deixa eu pensar um instante.", "Deixa eu pensar."))
        _, after = await heard(client, "F2", "pt")

    assert before == "voz:Deixa eu pensar um instante."
    assert after == "voz:Deixa eu pensar.", (
        "a linha ia gravada dentro do app e só mudava com uma versão nova na loja"
    )


async def test_the_old_sound_is_never_answered_again_once_the_line_is_re_ruled(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    elevenlabs: ElevenLabs,
    deploy: Callable[[str], None],
) -> None:
    deploy(ACKS_AS_RULED)
    async with room_client(db_session, monkeypatch) as client:
        old, _ = await heard(client, "F2", "pt")
        deploy(ACKS_AS_RULED.replace("Deixa eu pensar um instante.", "Deixa eu pensar."))
        first = await heard(client, "F2", "pt")
        second = await heard(client, "F2", "pt")

    assert first == second == (first[0], "voz:Deixa eu pensar."), (
        "o segundo pedido depois da mudança voltava a tocar a fala antiga"
    )
    assert old != first[0]


async def test_a_line_whose_text_did_not_change_is_not_voiced_again(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    elevenlabs: ElevenLabs,
    deploy: Callable[[str], None],
) -> None:
    deploy(ACKS_AS_RULED)
    async with room_client(db_session, monkeypatch) as client:
        before = await heard(client, "F1", "pt")
        deploy(ACKS_AS_RULED.replace("Deixa eu pensar um instante.", "Deixa eu pensar."))
        after = await heard(client, "F1", "pt")

    assert after == before == (before[0], "voz:Certo.")
    assert elevenlabs.voiced == ["Certo."], (
        "uma fala que ninguém mudou era sintetizada de novo a cada deploy"
    )


async def test_an_english_line_re_ruled_is_heard_new_in_english_and_portuguese_keeps_its_own(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    elevenlabs: ElevenLabs,
    deploy: Callable[[str], None],
) -> None:
    deploy(ACKS_AS_RULED)
    async with room_client(db_session, monkeypatch) as client:
        portuguese = await heard(client, "F2", "pt")
        deploy(
            ACKS_AS_RULED.replace("Mmm — let me think about that for a moment.", "Let me think.")
        )
        english = await heard(client, "F2", "en")
        still = await heard(client, "F2", "pt")

    assert english[1] == "voz:Let me think."
    assert still == portuguese == (portuguese[0], "voz:Deixa eu pensar um instante."), (
        "a mudança numa língua mexia na fala da outra"
    )


@pytest.mark.parametrize(
    ("line", "language", "her_words"),
    [
        (
            "P3",
            "pt",
            "Aprovado como rascunho final da equipe. O próximo passo é a checagem externa: "
            "toquem no botão 'checagem externa', aqui embaixo, e chamem os ouvintes.",
        ),
        (
            "P3",
            "en",
            "Approved as the team's final draft. The next step is the external check: tap the "
            "'external check' button below and call in the listeners.",
        ),
        (
            "X2",
            "pt",
            "Alguma coisa não ficou clara? Querem comentar alguma coisa sobre a passagem inteira? "
            "Se sim, toquem no círculo e falem, quantas vezes quiserem. Se não, toquem em "
            "'continuar'.",
        ),
        (
            "X2",
            "en",
            "Did anything stay unclear? Would you like to comment on anything about the whole "
            "passage? If so, tap the circle and speak, as many times as you want. If not, tap "
            "'continue'.",
        ),
    ],
    ids=["P3-pt", "P3-en", "X2-pt", "X2-en"],
)
async def test_the_two_stale_lines_are_heard_in_her_current_wording(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    elevenlabs: ElevenLabs,
    deploy: Callable[[str], None],
    line: str,
    language: str,
    her_words: str,
) -> None:
    deploy(HER_PROCESS_LINES_AT_18FA7C4)
    async with room_client(db_session, monkeypatch) as client:
        _, spoken = await heard(client, line, language)

    assert spoken == f"voz:{her_words}", (
        "a aprovação falava do OBT Refine e a checagem pedia 'nada a acrescentar', gravadas no app"
    )


@pytest.mark.parametrize("line", ["B0", "C1", "H0", "I0", "N0", "Z0", "F4", "F", "Fx", "f0"])
async def test_a_line_that_is_not_in_her_file_is_never_voiced(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    elevenlabs: ElevenLabs,
    line: str,
) -> None:
    async with room_client(db_session, monkeypatch) as client:
        asked = await client.get(
            f"{PREFIX}/fixed-lines/{line}", params={"language": "pt"}, headers=THE_TABLET
        )

    assert asked.status_code == 404, asked.text
    assert elevenlabs.voiced == [], (
        "a rota falava a reserva, o suplemento nosso ou qualquer nome que o tablet mandasse"
    )


async def test_a_line_whose_voice_cannot_be_made_answers_no_sound_at_all(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    elevenlabs: ElevenLabs,
) -> None:
    async def down(url: str, **_: Any) -> SimpleNamespace:
        return SimpleNamespace(status_code=503, content=b"", text="down")

    monkeypatch.setattr(elevenlabs, "post", down)
    async with room_client(db_session, monkeypatch) as client:
        asked = await client.get(
            f"{PREFIX}/fixed-lines/F2", params={"language": "pt"}, headers=THE_TABLET
        )

    assert asked.status_code == 502, asked.text
    assert "audio_url" not in asked.json(), "sem voz, a sala devolvia um endereço mesmo assim"


async def test_a_tablet_with_a_credential_hears_its_line_voiced_with_the_read_let_go(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.api.internalization_room import fixed_lines as route

    _, credential = await a_claimed_device(db_session)
    held: list[bool] = []

    async def voices(text: str, **_: object) -> tuple[SimpleNamespace, bool]:
        held.append(db_session.in_transaction())
        return SimpleNamespace(key="tts/linha.mp3"), False

    monkeypatch.setattr(route.room, "synthesize_facilitator_speech", voices)
    async with room_client(db_session, monkeypatch) as client:
        asked = await client.get(
            f"{PREFIX}/fixed-lines/F2", params={"language": "pt"}, headers=team_headers(credential)
        )

    assert asked.status_code == 200, asked.text
    assert held == [False], (
        "a leitura da credencial abria a transação e a conexão ficava presa durante a síntese"
    )


@pytest.mark.parametrize(
    ("spoken", "notices"),
    [
        ("pt", {"gravacao_presa", "microfone"}),
        ("en", {"sem_conexao", "gravacao_presa", "microfone"}),
    ],
)
def test_the_app_bundle_is_rendered_with_its_notices_and_none_of_her_lines(
    spoken: str, notices: set[str]
) -> None:
    import scripts.render_fixed_voice_lines as render

    assert set(render.catalogue(spoken)) == notices, (
        "as falas dela iam gravadas no app, e uma gravação velha tocava depois de ela mudar a letra"
    )
