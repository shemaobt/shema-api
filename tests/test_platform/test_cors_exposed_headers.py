from fastapi.middleware.cors import CORSMiddleware

from app.main import create_app


def _exposed_headers() -> list[str]:
    app = create_app()
    for middleware in app.user_middleware:
        if middleware.cls is CORSMiddleware:
            return middleware.kwargs["expose_headers"]
    raise AssertionError("CORSMiddleware is not mounted")


def test_the_browser_can_read_the_etag_and_x_tts_cached() -> None:
    # Neither is CORS-safelisted: without expose_headers the SPA cannot read them, and cache
    # warming — which X-Tts-Cached exists to make observable — goes blind.
    #
    # Both entries are asserted here because two PRs added to this one shared list for two
    # unrelated reasons (#107 for the sound-necklace autosave guard, #108 for TTS) and it
    # conflicted: resolving that merge by keeping one side silently breaks the other app.
    exposed = _exposed_headers()

    assert "ETag" in exposed
    assert "X-Tts-Cached" in exposed
