import pytest


@pytest.mark.parametrize("model", ["SegmentView", "BackTranslationChunkResponse", "FindingView"])
def test_every_frase_the_room_serves_is_documented_as_the_number_the_voice_speaks(
    model: str,
) -> None:
    from app.main import app

    served = app.openapi()["components"]["schemas"][model]["properties"]["frase"]

    assert "voice" in served.get("description", "").lower(), (
        "a frase servida não dizia nas referências da API que é o número que a voz fala"
    )
