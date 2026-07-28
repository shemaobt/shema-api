"""End-to-end proof that per-language access control is enforced at the HTTP layer.

Service-level tests prove ``assert_language_access`` works in isolation; these
prove the routers actually invoke it through the real dependency chain, and guard
against a future route forgetting the check.
"""

from __future__ import annotations

import pytest

from tests.baker import make_language, make_user
from tests.test_annotation_studio.conftest import (
    add_member,
    add_tier_a_recording,
    auth_header,
    grant_role,
    make_speaker,
    make_word,
)

AS = "/api/annotation-studio"


@pytest.fixture()
async def scenario(db_session, as_app):
    """Two languages, two facilitators (each member of one), an admin, seeded A data."""
    lang_a = await make_language(db_session, name="Alpha", code="ala")
    lang_b = await make_language(db_session, name="Beta", code="bet")

    f_a = await make_user(db_session, email="fa@example.com")
    f_b = await make_user(db_session, email="fb@example.com")
    admin = await make_user(db_session, email="adm@example.com")

    # Both facilitators have app access; they differ only in language membership.
    for u in (f_a, f_b):
        await grant_role(db_session, as_app.id, u.id, "facilitator")
    await grant_role(db_session, as_app.id, admin.id, "admin")
    await add_member(db_session, lang_a.id, f_a.id)
    await add_member(db_session, lang_b.id, f_b.id)

    word = await make_word(db_session, lang_a.id, "w001")
    speaker = await make_speaker(db_session, lang_a.id, "speaker1")
    rec_key = "ala/tier_a/raw/rec1"
    await add_tier_a_recording(db_session, word.id, speaker.id, 0, stored=True, key=rec_key)
    # Give B data too, so it's "active" and the admin-vs-facilitator dashboard
    # scoping is observable (an empty language never shows for anyone).
    await make_speaker(db_session, lang_b.id, "speaker1")

    return {
        "lang_a": lang_a,
        "lang_b": lang_b,
        "f_a": f_a,
        "f_b": f_b,
        "admin": admin,
        "word": word,
        "rec_key": rec_key,
    }


async def test_member_can_access_own_language(client, db_session, scenario):
    a = scenario["lang_a"]
    headers = await auth_header(db_session, scenario["f_a"])
    res = await client.get(f"{AS}/languages/{a.id}/speakers", headers=headers)
    assert res.status_code == 200


async def test_dashboard_lists_only_accessible_languages(client, db_session, scenario):
    f_a_headers = await auth_header(db_session, scenario["f_a"])
    res = await client.get(f"{AS}/languages", headers=f_a_headers)
    assert res.status_code == 200
    ids = {row["id"] for row in res.json()}
    assert ids == {scenario["lang_a"].id}  # not lang_b

    admin_headers = await auth_header(db_session, scenario["admin"])
    res = await client.get(f"{AS}/languages", headers=admin_headers)
    assert {scenario["lang_a"].id, scenario["lang_b"].id} <= {row["id"] for row in res.json()}


@pytest.mark.parametrize(
    "method,path_for",
    [
        ("get", lambda s: f"{AS}/languages/{s['lang_a'].id}/speakers"),  # path route
        ("get", lambda s: f"{AS}/languages/{s['lang_a'].id}/tier-a/words"),  # path route
        ("delete", lambda s: f"{AS}/tier-a/words/{s['word'].id}"),  # by-id route
        ("get", lambda s: f"{AS}/audio/url?key={s['rec_key']}"),  # cross-lang key
        ("get", lambda s: f"{AS}/languages/{s['lang_a'].id}/members"),  # admin-only
    ],
)
async def test_non_member_is_denied_on_foreign_language(
    client, db_session, scenario, method, path_for
):
    headers = await auth_header(db_session, scenario["f_b"])  # member of B, not A
    res = await client.request(method, path_for(scenario), headers=headers)
    assert res.status_code == 403, f"{method} {path_for(scenario)} -> {res.status_code}"


async def test_other_facilitator_still_works_on_own_language(client, db_session, scenario):
    b = scenario["lang_b"]
    headers = await auth_header(db_session, scenario["f_b"])
    res = await client.get(f"{AS}/languages/{b.id}/speakers", headers=headers)
    assert res.status_code == 200  # deny is scoping, not a blanket failure


async def test_audio_url_unknown_key_is_404(client, db_session, scenario):
    headers = await auth_header(db_session, scenario["f_a"])
    res = await client.get(f"{AS}/audio/url?key=bogus/not/a/real/key", headers=headers)
    assert res.status_code == 404


async def test_admin_can_manage_members(client, db_session, scenario):
    a = scenario["lang_a"]
    admin_headers = await auth_header(db_session, scenario["admin"])

    res = await client.get(f"{AS}/languages/{a.id}/members", headers=admin_headers)
    assert res.status_code == 200
    assert {m["email"] for m in res.json()} == {"fa@example.com"}

    res = await client.post(
        f"{AS}/languages/{a.id}/members",
        json={"email": "fb@example.com"},
        headers=admin_headers,
    )
    assert res.status_code == 201

    # F_B is now a member of A and can access it.
    f_b_headers = await auth_header(db_session, scenario["f_b"])
    res = await client.get(f"{AS}/languages/{a.id}/speakers", headers=f_b_headers)
    assert res.status_code == 200
