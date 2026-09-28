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


def test_the_range_headers_stay_out_of_the_list_on_purpose() -> None:
    """Accept-Ranges and Content-Range are not exposed, and nothing needs them to be.

    The only reader of the room's range route (``/voice``, 206) is the tablet's native
    ``http`` client, which CORS does not govern; no browser page reads ``/voice`` — the
    Project Health UI's voice calls are its own routes (checked 2026-09-28, ENG-1099). Pinned
    here rather than in prose because the readers live in other repos: the day a browser
    client needs a byte range, this is the assertion that says the list must change.
    """
    exposed = _exposed_headers()

    assert "Accept-Ranges" not in exposed
    assert "Content-Range" not in exposed
