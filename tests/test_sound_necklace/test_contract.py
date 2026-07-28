"""The emitted OpenAPI schema is what the SPA generates its TypeScript from, so it
has to tell the truth about which resources are real and which are still stubs.
"""

from __future__ import annotations

PREFIX = "/api/sound-necklace"
METHODS = {"get", "post", "put", "delete", "patch"}

# Implemented (ENG-260 sessions, ENG-261 audios, ENG-263 artifacts, ENG-264 resources,
# ENG-262 lock, ENG-265 consent, ENG-266 audit). Nothing answers 501 any more; the set is
# kept because the check runs both ways and a future stub must still be caught.
IMPLEMENTED_OPERATIONS = {
    ("/sessions/{session_id}/lock", "put"),
    ("/sessions/{session_id}/lock", "get"),
    ("/sessions/{session_id}/lock", "delete"),
    ("/sessions", "post"),
    ("/sessions", "get"),
    ("/sessions/{session_id}", "get"),
    ("/sessions/{session_id}/state", "get"),
    ("/sessions/{session_id}/state", "put"),
    ("/sessions/{session_id}/complete", "post"),
    ("/sessions/{session_id}/reopen", "post"),
    ("/projects/{project_id}/audios", "get"),
    ("/audios/{audio_id}/url", "get"),
    ("/sessions/{session_id}/artifacts", "post"),
    ("/sessions/{session_id}/artifacts/{kind}", "get"),
    ("/sessions/{session_id}/resources", "put"),
    ("/sessions/{session_id}/resources", "get"),
    ("/sessions/{session_id}/resources", "delete"),
    ("/sessions/{session_id}/resources/url", "get"),
    ("/sessions/{session_id}/consent", "post"),
    ("/sessions/{session_id}/consent", "get"),
    ("/projects/{project_id}/audit", "get"),
    ("/sessions/{session_id}/transcriptions", "post"),
    ("/sessions/{session_id}/transcriptions", "get"),
    ("/projects/{project_id}/settings", "get"),
    ("/projects/{project_id}/settings", "put"),
}


def _operations() -> list[tuple[str, str, dict]]:
    from app.main import app

    schema = app.openapi()
    return [
        (path.removeprefix(PREFIX), method, operation)
        for path, item in schema["paths"].items()
        if path.startswith(PREFIX)
        for method, operation in item.items()
        if method in METHODS
    ]


def test_the_implemented_routes_are_in_the_schema():
    operations = {(path, method) for path, method, _ in _operations()}
    assert operations >= IMPLEMENTED_OPERATIONS, f"missing: {IMPLEMENTED_OPERATIONS - operations}"


def test_only_the_unimplemented_routes_advertise_501():
    """A 501 on a route that now answers for real is a lie the SPA would generate from."""
    operations = _operations()
    assert operations, "no sound-necklace operations in the schema"

    lying = [
        f"{method.upper()} {path}"
        for path, method, operation in operations
        if (path, method) in IMPLEMENTED_OPERATIONS and "501" in operation["responses"]
    ]
    hiding = [
        f"{method.upper()} {path}"
        for path, method, operation in operations
        if (path, method) not in IMPLEMENTED_OPERATIONS and "501" not in operation["responses"]
    ]

    assert not lying, f"implemented operations still advertising 501: {lying}"
    assert not hiding, f"stub operations hiding their status: {hiding}"


def test_the_autosave_advertises_its_conflict():
    """The version guard is part of the contract: a loser must know 409 can happen."""
    operations = {(path, method): op for path, method, op in _operations()}
    autosave = operations[("/sessions/{session_id}/state", "put")]
    assert "409" in autosave["responses"]


def test_the_lock_status_carries_exactly_the_three_keys_the_spa_parses():
    """The SPA reads this under z.strictObject: a fourth key throws on the client.

    The throw is swallowed by the app shell's catch, which also skips wiring autosave —
    so an extra field here costs the user their session silently. The fencing counter is
    deliberately server-side only for this reason; if it ever needs to be on the wire,
    the SPA's contract has to change first.
    """
    from app.main import app

    schemas = app.openapi()["components"]["schemas"]
    assert set(schemas["LockStatusResponse"]["properties"]) == {"held", "holder", "expires_at"}
    # LockHolder is nested inside it and parsed just as strictly.
    assert set(schemas["LockHolder"]["properties"]) == {"user_id", "display_name"}


def test_every_fenced_write_advertises_the_lock_conflict_it_can_raise():
    """A tab that lost the lease learns it from the schema, not from production."""
    operations = {(path, method): op for path, method, op in _operations()}
    fenced = [
        ("/sessions/{session_id}/state", "put"),
        ("/sessions/{session_id}/complete", "post"),
        ("/sessions/{session_id}/reopen", "post"),
        ("/sessions/{session_id}/artifacts", "post"),
    ]
    silent = [f"{m.upper()} {p}" for p, m in fenced if "409" not in operations[(p, m)]["responses"]]
    assert not silent, f"fenced writes not advertising their 409: {silent}"


def test_the_lock_conflict_body_is_a_schema_the_spa_can_generate_from():
    """A description is prose; the SPA generates types from schemas.

    `holder_name` and `expires_at` are what the "sessão em uso por…" screen renders, and
    `code` is what decides between review mode and a reload — none of it reaches the
    client's types unless the 409 names a model.
    """
    from app.main import app

    schemas = app.openapi()["components"]["schemas"]
    locked = schemas["SessionLockedResponse"]
    assert set(locked["properties"]) == {"detail", "code", "holder_name", "expires_at"}
    assert locked["properties"]["code"]["const"] == "SESSION_LOCKED"
    changed = schemas["SessionLockChangedResponse"]
    assert set(changed["properties"]) == {"detail", "code"}
    assert changed["properties"]["code"]["const"] == "SESSION_LOCK_CHANGED"


def test_the_lifecycle_409s_reference_both_codes_they_can_answer_with():
    """Complete and reopen refuse for two reasons and the client must tell them apart."""
    operations = {(path, method): op for path, method, op in _operations()}
    for path, method in [
        ("/sessions/{session_id}/complete", "post"),
        ("/sessions/{session_id}/reopen", "post"),
    ]:
        body = operations[(path, method)]["responses"]["409"]["content"]["application/json"]
        referenced = {ref["$ref"].rsplit("/", 1)[-1] for ref in body["schema"]["anyOf"]}
        assert referenced == {"SessionLockedResponse", "SessionLockChangedResponse"}, (
            f"{method.upper()} {path} advertises {referenced}"
        )


def test_artifact_download_declares_a_redirect_not_an_empty_body():
    """Bytes are served by storage, never proxied — the schema must say redirect."""
    operations = {(path, method): operation for path, method, operation in _operations()}
    download = operations[("/sessions/{session_id}/artifacts/{kind}", "get")]
    assert "307" in download["responses"]
    assert "200" not in download["responses"]


def test_artifact_upload_takes_raw_multipart_bytes():
    """A JSON body would put the payload through a parser — §10.5 forbids that."""
    operations = {(path, method): operation for path, method, operation in _operations()}
    upload = operations[("/sessions/{session_id}/artifacts", "post")]
    assert list(upload["requestBody"]["content"]) == ["multipart/form-data"]


def test_the_transcription_progress_is_a_schema_the_spa_can_poll_from():
    """The report renders partial state, so partial state has to be in the types.

    Per-answer `status` and `error` are what let one dead answer show as one red row
    instead of a failed job — and `translation_en` is the field the report reads whatever
    the interview language was.
    """
    from app.main import app

    schemas = app.openapi()["components"]["schemas"]
    progress = schemas["TranscriptionProgressResponse"]
    assert set(progress["properties"]) == {"total", "ready", "failed", "pending", "answers"}
    draft = schemas["AnswerTranscript"]
    assert set(draft["properties"]) == {
        "path",
        "status",
        "transcript_source",
        "translation_en",
        "error",
    }
    assert set(schemas["TranscriptStatus"]["enum"]) == {"pending", "ready", "failed"}


def test_starting_a_transcription_answers_202_not_200():
    """The drafts are not ready when the call returns: a 200 would invite the SPA to read
    them straight off the response instead of polling."""
    operations = {(path, method): operation for path, method, operation in _operations()}
    start = operations[("/sessions/{session_id}/transcriptions", "post")]
    assert "202" in start["responses"]
    assert "200" not in start["responses"]
