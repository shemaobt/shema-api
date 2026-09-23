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
    async def post(self, *_: Any, **__: Any) -> SimpleNamespace:
        return SimpleNamespace(status_code=200, content=b"a rendering nobody kept", text="")


class _RefusingBucket:
    async def get(self, key: str) -> bytes | None:
        return None

    async def exists(self, key: str) -> bool:
        return False

    async def put_once(self, key: str, data: bytes, content_type: str) -> bytes:
        raise OSError("the bucket refused the write")


async def test_a_line_the_bucket_refused_is_not_served_from_memory_afterwards() -> None:
    bucket = _RefusingBucket()

    voiced = await tts.synthesize_speech_key(
        LINE, language="pt-BR", settings=_settings(), client=_Elevenlabs(), store=bucket
    )

    assert await tts.fetch_clip(voiced.key, store=bucket) is None, (
        "a memória guardava uma renderização que o bucket recusou, e esta instância a "
        "servia enquanto qualquer outra faria e serviria outra"
    )
