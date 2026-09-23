import asyncio
from types import SimpleNamespace
from typing import Any

from app.core.config import Settings
from app.services.platform import tts

LINE = "Onde essa história acontece?"


def _settings() -> Settings:
    return Settings(
        database_url="sqlite+aiosqlite:///./test.db",
        elevenlabs_api_key="fake-elevenlabs",
        gcs_platform_bucket="tripod-platform-test",
    )


class _Elevenlabs:
    def __init__(self, *renderings: bytes) -> None:
        self.renderings = list(renderings)

    async def post(self, *args: Any, **kwargs: Any) -> SimpleNamespace:
        audio = self.renderings.pop(0)
        await asyncio.sleep(0)
        return SimpleNamespace(status_code=200, content=audio, text="")


class _WriteOnceBucket:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def get(self, key: str) -> bytes | None:
        return self.objects.get(key)

    async def exists(self, key: str) -> bool:
        return key in self.objects

    async def put_once(self, key: str, data: bytes, content_type: str) -> bytes:
        return self.objects.setdefault(key, data)


async def test_two_syntheses_of_one_line_at_once_serve_the_bytes_the_bucket_kept() -> None:
    bucket = _WriteOnceBucket()
    elevenlabs = _Elevenlabs(b"first rendering", b"second rendering")

    first, second = await asyncio.gather(
        *(
            tts.synthesize_speech_key(
                LINE, language="pt-BR", settings=_settings(), client=elevenlabs, store=bucket
            )
            for _ in range(2)
        )
    )

    assert first.key == second.key
    assert bucket.objects[first.key] == b"first rendering"
    assert await tts.fetch_clip(first.key, store=bucket) == b"first rendering", (
        "quem perdia a corrida guardava na memória a própria renderização e a servia, "
        "enquanto o bucket servia a outra: duas vozes para a mesma fala"
    )


async def test_a_platform_synthesis_that_lost_the_race_answers_with_the_kept_bytes() -> None:
    bucket = _WriteOnceBucket()
    elevenlabs = _Elevenlabs(b"first rendering", b"second rendering")

    first, second = await asyncio.gather(
        *(
            tts.synthesize_speech(
                LINE, language="pt-BR", settings=_settings(), client=elevenlabs, store=bucket
            )
            for _ in range(2)
        )
    )

    assert first.audio == second.audio == b"first rendering", (
        "a síntese que perdia o put devolvia a própria renderização"
    )
