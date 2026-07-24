"""Session persistence: create, autosave under a version guard, lifecycle, resume, list.

The state document is produced and validated by the SPA (it re-reads it with a
strict schema), so the API is only its custodian: what comes in as bytes goes out
as the same bytes. These tests send deliberately ugly JSON — keys out of order,
odd whitespace, a long float — because a server that re-serializes the document
would silently normalize all three and still look correct to a shallow assertion.
"""

from __future__ import annotations

import pytest

from tests.baker import make_language, make_project, make_project_user_access, make_user
from tests.test_sound_necklace.conftest import (
    audio_of,
    auth_header,
    give_project_an_audio,
    grant_role,
)

SN = "/api/sound-necklace"


def state_bytes(*, mode: str = "escuta", confirmed: bool = False) -> str:
    """A state envelope whose exact bytes matter. Not built with json.dumps on purpose."""
    return (
        '{"schema_version": 1,  "mode":"' + mode + '",\n'
        '  "beadSec": 0.30000000000000004, "whole": {"confirmed": '
        + ("true" if confirmed else "false")
        + ', "id":"S1"},\n  "zeta": 1, "alpha": 2}'
    )


JSON_HEADERS = {"content-type": "application/json"}


async def new_session(client, headers, project_id: str, *, name: str = "O Conto do Boto") -> str:
    res = await client.post(
        f"{SN}/sessions",
        headers=headers,
        json={
            "audio_id": audio_of(project_id),
            "project_id": project_id,
            "story_name": name,
            "story_slug": "conto-do-boto",
            "granularity_level": "medium",
            "bead_sec": 0.5,
            "manifest_id": "fnv1a32:d31a8419",
            "pipeline_consent": True,
        },
    )
    assert res.status_code == 201, res.text
    return str(res.json()["id"])


@pytest.fixture()
async def facilitator(db_session, sound_necklace_app):
    """A sound-necklace facilitator with access to one project."""
    user = await make_user(db_session, email="facilitator@example.com")
    await grant_role(db_session, sound_necklace_app.id, user.id, "facilitator")
    language = await make_language(db_session, name="Nheengatu", code="yrl")
    project = await make_project(db_session, language.id, name="Projeto A")
    await give_project_an_audio(db_session, project.id)
    await make_project_user_access(db_session, project.id, user.id)
    headers = await auth_header(db_session, user)
    return user, project, headers


# ── Creation ─────────────────────────────────────────────────────────────────


async def test_create_opens_the_session_at_the_first_station(client, facilitator):
    _user, project, headers = facilitator

    res = await client.post(
        f"{SN}/sessions",
        headers=headers,
        json={
            "audio_id": audio_of(project.id),
            "project_id": project.id,
            "story_name": "O Conto do Boto",
            "story_slug": "conto-do-boto",
            "granularity_level": "medium",
            "bead_sec": 0.5,
            "manifest_id": "fnv1a32:d31a8419",
            "pipeline_consent": True,
        },
    )

    assert res.status_code == 201, res.text
    body = res.json()
    assert body["status"] == "in_progress"
    assert body["progress"]["current_step"] == "listen"
    assert body["story_slug"] == "conto-do-boto"
    assert body["project_id"] == project.id


async def test_create_in_a_project_the_user_cannot_reach_is_forbidden(
    client, db_session, facilitator, sound_necklace_app
):
    _user, _project, headers = facilitator
    language = await make_language(db_session, name="Outra", code="oth")
    foreign = await make_project(db_session, language.id, name="Projeto B")
    await give_project_an_audio(db_session, foreign.id)

    res = await client.post(
        f"{SN}/sessions",
        headers=headers,
        json={
            "audio_id": audio_of(foreign.id),
            "project_id": foreign.id,
            "story_name": "Alheia",
            "story_slug": "alheia",
            "granularity_level": "medium",
            "bead_sec": 0.5,
            "manifest_id": "fnv1a32:d31a8419",
            "pipeline_consent": True,
        },
    )

    assert res.status_code == 403


async def test_create_with_a_nonexistent_project_is_not_found_for_an_admin(client, db_session):
    """A platform admin bypasses the access check, so a bogus project_id would otherwise
    reach the FK as a 500. It must be a clean 404 instead."""
    admin = await make_user(db_session, email="admin@example.com", is_platform_admin=True)
    headers = await auth_header(db_session, admin)

    res = await client.post(
        f"{SN}/sessions",
        headers=headers,
        json={
            "audio_id": audio_of("proj_missing"),
            "project_id": "proj_missing",
            "story_name": "Fantasma",
            "story_slug": "fantasma",
            "granularity_level": "medium",
            "bead_sec": 0.5,
            "manifest_id": "fnv1a32:d31a8419",
            "pipeline_consent": True,
        },
    )

    assert res.status_code == 404, res.text


# ── Autosave + resume: the bytes are the contract ────────────────────────────


async def test_state_is_absent_until_the_first_autosave(client, facilitator):
    _user, project, headers = facilitator
    session_id = await new_session(client, headers, project.id)

    res = await client.get(f"{SN}/sessions/{session_id}/state", headers=headers)

    assert res.status_code == 404


async def test_resume_returns_the_saved_document_byte_for_byte(client, facilitator):
    _user, project, headers = facilitator
    session_id = await new_session(client, headers, project.id)
    raw = state_bytes(mode="triagem")

    saved = await client.put(
        f"{SN}/sessions/{session_id}/state",
        headers={**headers, **JSON_HEADERS},
        content=raw,
    )
    assert saved.status_code == 200, saved.text

    resumed = await client.get(f"{SN}/sessions/{session_id}/state", headers=headers)

    assert resumed.status_code == 200
    assert resumed.content == raw.encode(), "the stored document must come back as the same bytes"


async def test_progress_follows_the_saved_state(client, facilitator):
    _user, project, headers = facilitator
    session_id = await new_session(client, headers, project.id)

    await client.put(
        f"{SN}/sessions/{session_id}/state",
        headers={**headers, **JSON_HEADERS},
        content=state_bytes(mode="mapeamento"),
    )

    res = await client.get(f"{SN}/sessions/{session_id}", headers=headers)
    assert res.json()["progress"]["current_step"] == "conversation"


async def test_progress_reaches_the_cutting_station_once_the_whole_is_confirmed(
    client, facilitator
):
    _user, project, headers = facilitator
    session_id = await new_session(client, headers, project.id)

    await client.put(
        f"{SN}/sessions/{session_id}/state",
        headers={**headers, **JSON_HEADERS},
        content=state_bytes(mode="escuta", confirmed=True),
    )

    res = await client.get(f"{SN}/sessions/{session_id}", headers=headers)
    assert res.json()["progress"]["current_step"] == "cut"


# ── The version guard ────────────────────────────────────────────────────────


async def test_autosave_without_a_version_overwrites(client, facilitator):
    """The SPA's autosaver sends no version. An unconditional write must keep working."""
    _user, project, headers = facilitator
    session_id = await new_session(client, headers, project.id)
    last = state_bytes(mode="mapeamento")

    for raw in (state_bytes(mode="escuta"), state_bytes(mode="triagem"), last):
        res = await client.put(
            f"{SN}/sessions/{session_id}/state",
            headers={**headers, **JSON_HEADERS},
            content=raw,
        )
        assert res.status_code == 200, res.text

    resumed = await client.get(f"{SN}/sessions/{session_id}/state", headers=headers)
    assert resumed.text == last


async def test_a_stale_if_match_that_is_not_a_version_is_refused_not_crashed(client, facilitator):
    _user, project, headers = facilitator
    session_id = await new_session(client, headers, project.id)

    res = await client.put(
        f"{SN}/sessions/{session_id}/state",
        headers={**headers, **JSON_HEADERS, "If-Match": "not-a-version"},
        content=state_bytes(),
    )

    assert res.status_code == 400


async def test_an_if_match_beyond_the_version_column_is_refused_not_crashed(client, facilitator):
    """The version column is a 32-bit int; a bigger number is not a version we ever issued."""
    _user, project, headers = facilitator
    session_id = await new_session(client, headers, project.id)

    res = await client.put(
        f"{SN}/sessions/{session_id}/state",
        headers={**headers, **JSON_HEADERS, "If-Match": '"99999999999999999999"'},
        content=state_bytes(),
    )

    assert res.status_code == 400


async def test_a_body_that_is_not_utf8_is_refused_not_crashed(client, facilitator):
    """`json.loads` accepts UTF-16, so a body can validate and still not be UTF-8 text."""
    _user, project, headers = facilitator
    session_id = await new_session(client, headers, project.id)

    res = await client.put(
        f"{SN}/sessions/{session_id}/state",
        headers={**headers, **JSON_HEADERS},
        content=state_bytes().encode("utf-16"),
    )

    assert res.status_code == 400


async def test_a_body_with_a_utf8_bom_still_saves(client, facilitator):
    """A BOM decodes cleanly, so it must not blow up on the way to the progress step."""
    _user, project, headers = facilitator
    session_id = await new_session(client, headers, project.id)
    raw = state_bytes(mode="triagem").encode("utf-8-sig")

    saved = await client.put(
        f"{SN}/sessions/{session_id}/state",
        headers={**headers, **JSON_HEADERS},
        content=raw,
    )

    assert saved.status_code == 200, saved.text
    summary = await client.get(f"{SN}/sessions/{session_id}", headers=headers)
    assert summary.json()["progress"]["current_step"] == "triage"


async def test_a_story_name_longer_than_the_column_is_refused_not_truncated(client, facilitator):
    """Postgres would reject the oversized insert; SQLite would silently take it."""
    _user, project, headers = facilitator

    res = await client.post(
        f"{SN}/sessions",
        headers=headers,
        json={
            "audio_id": audio_of(project.id),
            "project_id": project.id,
            "story_name": "b" * 300,
            "story_slug": "conto-do-boto",
            "granularity_level": "medium",
            "bead_sec": 0.5,
            "manifest_id": "fnv1a32:d31a8419",
            "pipeline_consent": True,
        },
    )

    assert res.status_code == 422


async def test_the_second_writer_of_a_version_is_refused_and_told_the_current_one(
    client, facilitator
):
    """Two machines resume the same session and both write from version 1.

    The first wins; the loser must be refused with the version it needs to reload,
    rather than silently clobbering work it never saw.
    """
    _user, project, headers = facilitator
    session_id = await new_session(client, headers, project.id)

    first_save = await client.put(
        f"{SN}/sessions/{session_id}/state",
        headers={**headers, **JSON_HEADERS},
        content=state_bytes(mode="escuta"),
    )
    version = first_save.headers["etag"]

    winner = await client.put(
        f"{SN}/sessions/{session_id}/state",
        headers={**headers, **JSON_HEADERS, "If-Match": version},
        content=state_bytes(mode="triagem"),
    )
    loser = await client.put(
        f"{SN}/sessions/{session_id}/state",
        headers={**headers, **JSON_HEADERS, "If-Match": version},
        content=state_bytes(mode="mapeamento"),
    )

    assert winner.status_code == 200
    assert loser.status_code == 409
    assert loser.json()["current_version"] == 2

    kept = await client.get(f"{SN}/sessions/{session_id}/state", headers=headers)
    assert kept.text == state_bytes(mode="triagem"), "the refused write must not have landed"


# ── Lifecycle ────────────────────────────────────────────────────────────────


async def test_complete_then_reopen_preserves_the_document(client, facilitator):
    _user, project, headers = facilitator
    session_id = await new_session(client, headers, project.id)
    raw = state_bytes(mode="mapeamento")
    await client.put(
        f"{SN}/sessions/{session_id}/state",
        headers={**headers, **JSON_HEADERS},
        content=raw,
    )

    done = await client.post(f"{SN}/sessions/{session_id}/complete", headers=headers)
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "completed"
    assert done.json()["progress"]["current_step"] == "save"

    reopened = await client.post(f"{SN}/sessions/{session_id}/reopen", headers=headers)
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["status"] == "in_progress"
    assert reopened.json()["progress"]["current_step"] == "conversation", (
        "reopening must restore the station the state was left at, not the completion one"
    )

    resumed = await client.get(f"{SN}/sessions/{session_id}/state", headers=headers)
    assert resumed.content == raw.encode(), "a completed-then-reopened session must resume intact"


# ── Listing ──────────────────────────────────────────────────────────────────


async def test_the_list_only_shows_sessions_of_projects_the_user_can_reach(
    client, db_session, facilitator, sound_necklace_app
):
    _user, project, headers = facilitator
    await new_session(client, headers, project.id, name="Minha")

    stranger = await make_user(db_session, email="stranger@example.com")
    await grant_role(db_session, sound_necklace_app.id, stranger.id, "facilitator")
    other_language = await make_language(db_session, name="Outra", code="oth")
    other_project = await make_project(db_session, other_language.id, name="Projeto B")
    await give_project_an_audio(db_session, other_project.id)
    await make_project_user_access(db_session, other_project.id, stranger.id)
    stranger_headers = await auth_header(db_session, stranger)
    await new_session(client, stranger_headers, other_project.id, name="Alheia")

    mine = await client.get(f"{SN}/sessions", headers=headers)
    theirs = await client.get(f"{SN}/sessions", headers=stranger_headers)

    assert [s["story_name"] for s in mine.json()["sessions"]] == ["Minha"]
    assert [s["story_name"] for s in theirs.json()["sessions"]] == ["Alheia"]


async def test_reading_a_session_of_another_project_is_forbidden(
    client, db_session, facilitator, sound_necklace_app
):
    _user, _project, headers = facilitator
    stranger = await make_user(db_session, email="stranger@example.com")
    await grant_role(db_session, sound_necklace_app.id, stranger.id, "facilitator")
    other_language = await make_language(db_session, name="Outra", code="oth")
    other_project = await make_project(db_session, other_language.id, name="Projeto B")
    await give_project_an_audio(db_session, other_project.id)
    await make_project_user_access(db_session, other_project.id, stranger.id)
    stranger_headers = await auth_header(db_session, stranger)
    foreign_id = await new_session(client, stranger_headers, other_project.id, name="Alheia")

    res = await client.get(f"{SN}/sessions/{foreign_id}", headers=headers)

    assert res.status_code == 403


async def test_an_unknown_session_is_not_found(client, facilitator):
    _user, _project, headers = facilitator

    res = await client.get(f"{SN}/sessions/does-not-exist", headers=headers)

    assert res.status_code == 404


async def test_the_list_is_paginated(client, facilitator):
    """The dashboard loads this on open, so the page size must be bounded."""
    _user, project, headers = facilitator
    for i in range(3):
        await new_session(client, headers, project.id, name=f"S{i}")

    page1 = await client.get(f"{SN}/sessions?limit=2", headers=headers)
    page2 = await client.get(f"{SN}/sessions?limit=2&offset=2", headers=headers)

    ids1 = [s["id"] for s in page1.json()["sessions"]]
    ids2 = [s["id"] for s in page2.json()["sessions"]]
    assert len(ids1) == 2
    assert len(ids2) == 1
    assert len(set(ids1 + ids2)) == 3, "pages must not overlap and must cover every session"


async def test_a_session_cannot_name_an_audio_the_project_does_not_have(client, facilitator):
    """The link from audio to artifacts is checked, not trusted (ENG-362).

    ``audio_ref`` is the only thing tying a bucket audio to the artifacts cut from it. A
    session naming an audio nobody has would export files that could never be traced
    back: the row survives, and the one field saying where it came from is wrong.
    """
    _user, project, headers = facilitator

    res = await client.post(
        f"{SN}/sessions",
        headers=headers,
        json={
            "audio_id": "aud_que_nao_existe",
            "project_id": project.id,
            "story_name": "Fantasma",
            "story_slug": "fantasma",
            "granularity_level": "medium",
            "bead_sec": 0.5,
            "manifest_id": "fnv1a32:d31a8419",
            "pipeline_consent": True,
        },
    )

    assert res.status_code == 404, res.text
    assert (await db_sessions(client, headers)) == []


async def test_a_session_cannot_borrow_an_audio_from_another_project(
    client, db_session, facilitator
):
    """An audio belongs to one project. Cutting somebody else's is a miss, not a loan."""
    _user, project, headers = facilitator
    language = await make_language(db_session, name="Outra", code="oth")
    foreign = await make_project(db_session, language.id, name="Projeto B")
    foreign_audio = await give_project_an_audio(db_session, foreign.id)

    res = await client.post(
        f"{SN}/sessions",
        headers=headers,
        json={
            "audio_id": foreign_audio,
            "project_id": project.id,
            "story_name": "Emprestada",
            "story_slug": "emprestada",
            "granularity_level": "medium",
            "bead_sec": 0.5,
            "manifest_id": "fnv1a32:d31a8419",
            "pipeline_consent": True,
        },
    )

    assert res.status_code == 404, res.text


async def db_sessions(client, headers) -> list[dict]:
    """The caller's sessions, as the listing reports them."""
    res = await client.get(f"{SN}/sessions", headers=headers)
    assert res.status_code == 200, res.text
    return list(res.json()["sessions"])
