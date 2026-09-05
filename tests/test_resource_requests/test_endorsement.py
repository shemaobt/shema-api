"""The Líder de Base's half of the lifecycle: the reading his signature requires, the act.

GATE-02 D2 named the role and GATE-03 D2 put its act in the system (BE-16, OBT-476). What
is under test here fails for three different reasons and is grouped that way: the **scope**
— the Líder reaches every submitted request and no draft of another team (``_scope.py``'s
written decision); the **act** — endorsing stamps ``endorsed_by``/``endorsed_at`` and
births ``leader_name``/``leader_date``, with its two refusals; and the **fallout** — where
the endorsed line lands of the two documents, and a revision going back to the base
unendorsed.

⚠️ No negative test here uses a platform admin (``test_capabilities.py`` says why).
"""

from __future__ import annotations

from sqlalchemy import select

from app.db.models.resource_request import RRDecision, RRRequest, RRSnapshot
from tests.baker import make_user
from tests.test_resource_requests.conftest import auth_header, grant
from tests.test_resource_requests.test_requests import (
    REQUESTS,
    _decide,
    answers,
    as_team,
    create,
    draft,
)


async def as_lider(
    db_session, rrf_app, email: str = "lider@rr.test", display_name: str | None = None
) -> dict[str, str]:
    user = await make_user(db_session, email=email, display_name=display_name)
    await grant(db_session, user, rrf_app, "lider")
    return await auth_header(db_session, user)


async def submitted_by_team(db_session, client, rrf_app) -> dict:
    team = await as_team(db_session, rrf_app)
    created = await create(client, team)
    res = await client.post(f"{REQUESTS}/{created['id']}/submit", headers=team)
    assert res.status_code == 200, res.text
    return res.json()


# ——— the reading the endorsement requires ————————————————————————————————————————


async def test_the_lider_reads_every_submitted_request_and_no_draft(
    db_session, client, rrf_app
) -> None:
    """The scope decided in ``_scope.py``: his reach starts where a document freezes.

    A draft is the team's work still moving; what the Líder signs is the submitted,
    frozen document, so that is where his reading begins. The draft answers 404 and not
    403 for the standing reason — out of scope must not confirm the id exists.
    """
    team = await as_team(db_session, rrf_app)
    moving = await create(client, team)
    frozen = await create(client, team)
    await client.post(f"{REQUESTS}/{frozen['id']}/submit", headers=team)
    lider = await as_lider(db_session, rrf_app)

    listed = (await client.get(REQUESTS, headers=lider)).json()

    assert [row["id"] for row in listed] == [frozen["id"]]
    assert (await client.get(f"{REQUESTS}/{frozen['id']}", headers=lider)).status_code == 200
    assert (await client.get(f"{REQUESTS}/{moving['id']}", headers=lider)).status_code == 404


async def test_a_lider_who_is_also_equipe_keeps_his_own_drafts_and_no_others(
    db_session, client, rrf_app
) -> None:
    """The account BE-17 will actually produce: ``auto_approve`` makes everyone ``equipe``.

    The two reaches add instead of the narrow one replacing the floor: his own draft stays
    his through ``created_by``, the submitted request arrives through the Líder's reach,
    and another team's draft stays invisible — which is what tells this union apart from
    ``Reach.every``.
    """
    team = await as_team(db_session, rrf_app)
    others_draft = await create(client, team)
    others_submitted = await create(client, team)
    await client.post(f"{REQUESTS}/{others_submitted['id']}/submit", headers=team)

    user = await make_user(db_session, email="lider-equipe@rr.test")
    await grant(db_session, user, rrf_app, "equipe")
    await grant(db_session, user, rrf_app, "lider")
    both = await auth_header(db_session, user)
    own_draft = await create(client, both)

    listed = {row["id"] for row in (await client.get(REQUESTS, headers=both)).json()}

    assert listed == {own_draft["id"], others_submitted["id"]}
    assert (await client.get(f"{REQUESTS}/{others_draft['id']}", headers=both)).status_code == 404


async def test_the_lider_reads_and_does_not_write(db_session, client, rrf_app) -> None:
    """Read without edit, end to end — the guard the frontend mirrors as ``ReadOnlyPart``.

    The refusal is the capability's, because unlike the mesa and the Gestor the Líder
    never held ``edit_requests``: creating, editing and submitting are not his verbs at
    all, not his verbs on the wrong rows.
    """
    request = await submitted_by_team(db_session, client, rrf_app)
    lider = await as_lider(db_session, rrf_app)

    assert (await client.get(f"{REQUESTS}/{request['id']}", headers=lider)).status_code == 200

    refused_create = await client.post(REQUESTS, json=draft(), headers=lider)
    refused_edit = await client.patch(f"{REQUESTS}/{request['id']}", json=draft(), headers=lider)
    refused_submit = await client.post(f"{REQUESTS}/{request['id']}/submit", headers=lider)

    for res in (refused_create, refused_edit, refused_submit):
        assert res.status_code == 403, res.text
        assert "edit_requests" in res.json()["detail"]


# ——— the act —————————————————————————————————————————————————————————————————————


async def test_endorsing_stamps_the_act_and_births_the_leader_line(
    db_session, client, rrf_app
) -> None:
    """The DoD's own sentence: ``leader_name``/``leader_date`` are born from the endorsement.

    The act rides in the envelope (``endorsed_by``/``endorsed_at``, the shape the
    acceptance already has) and the display pair lands in the document, where the
    contract's 45 keys put it — the endorser's account name and the act's own day.
    """
    request = await submitted_by_team(db_session, client, rrf_app)
    lider = await as_lider(db_session, rrf_app, display_name="Eva da Base")

    res = await client.post(f"{REQUESTS}/{request['id']}/endorse", headers=lider)

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["endorsed_at"] is not None
    assert body["document"]["fields"]["leader_name"] == "Eva da Base"
    assert body["document"]["fields"]["leader_date"] == body["endorsed_at"][:10]

    row = (
        await db_session.execute(select(RRRequest).where(RRRequest.id == request["id"]))
    ).scalar_one()
    assert body["endorsed_by"] == row.endorsed_by is not None


async def test_a_draft_cannot_be_endorsed_and_the_refusal_says_why(
    db_session, client, rrf_app
) -> None:
    """An endorsement of a moving document would vouch for whatever it becomes.

    The caller is the one account that can even reach an unsubmitted draft while holding
    the capability — its own author, who is also a Líder — so the answer is the real
    reason (409) and never the scope's 404.
    """
    user = await make_user(db_session, email="autor-lider@rr.test")
    await grant(db_session, user, rrf_app, "equipe")
    await grant(db_session, user, rrf_app, "lider")
    both = await auth_header(db_session, user)
    own_draft = await create(client, both)

    res = await client.post(f"{REQUESTS}/{own_draft['id']}/endorse", headers=both)

    assert res.status_code == 409
    assert "submitted" in res.json()["detail"]


async def test_endorsing_twice_is_refused_not_overwritten(db_session, client, rrf_app) -> None:
    """A signature is not a value to update: the second act would replace who vouched."""
    request = await submitted_by_team(db_session, client, rrf_app)
    first = await as_lider(db_session, rrf_app, "primeiro@rr.test")
    second = await as_lider(db_session, rrf_app, "segundo@rr.test")
    endorsed = await client.post(f"{REQUESTS}/{request['id']}/endorse", headers=first)
    assert endorsed.status_code == 200

    res = await client.post(f"{REQUESTS}/{request['id']}/endorse", headers=second)

    assert res.status_code == 409
    assert "already endorsed" in res.json()["detail"]


async def test_no_other_role_endorses(db_session, client, rrf_app) -> None:
    """The mesa's ``?`` cell, decided and asserted: the signature does not accumulate.

    The endorsement attests that the project belongs to the Líder's base — the mesa
    endorsing to itself would empty the act it reads, and the Gestor's *quase tudo* stops
    at the same line approving does.
    """
    request = await submitted_by_team(db_session, client, rrf_app)

    for role in ("equipe", "mesa", "gestor"):
        user = await make_user(db_session, email=f"{role}@nao-endossa.test")
        await grant(db_session, user, rrf_app, role)
        headers = await auth_header(db_session, user)

        res = await client.post(f"{REQUESTS}/{request['id']}/endorse", headers=headers)

        assert res.status_code == 403, f"{role} endorsed: {res.text}"
        assert "endorse_request" in res.json()["detail"]


async def test_the_author_who_is_also_lider_may_endorse_his_own(
    db_session, client, rrf_app
) -> None:
    """Self-endorsement is allowed, on record: the paper form never demanded two people.

    A small base's leader may be its own Ponto focal, and forbidding the pair would be a
    rule the client never gave. ``endorsed_by`` records the fact either way — nothing is
    hidden, which is what makes the absence of the rule safe to keep.
    """
    user = await make_user(db_session, email="base-de-um@rr.test")
    await grant(db_session, user, rrf_app, "equipe")
    await grant(db_session, user, rrf_app, "lider")
    both = await auth_header(db_session, user)
    own = await create(client, both)
    await client.post(f"{REQUESTS}/{own['id']}/submit", headers=both)

    res = await client.post(f"{REQUESTS}/{own['id']}/endorse", headers=both)

    assert res.status_code == 200
    assert res.json()["endorsed_by"] == res.json()["created_by"]


# ——— the fallout —————————————————————————————————————————————————————————————————


async def test_the_snapshot_keeps_what_was_submitted_and_the_live_row_carries_the_endorsement(
    db_session, client, rrf_app
) -> None:
    """Which of the two documents carries the Líder's line — decided, and pinned here.

    The endorsement lands **after** the freeze and can only land after it: only a submitted
    request is endorsable, and ``rr_snapshots`` is append-only in the database. So the
    snapshot goes on saying what the team sent and the read path shows the endorser
    (PR #281, review). The two documents are compared **whole**, because the claim is not
    merely that the line moved but that it is the only thing that ever does — everything
    else a submitted request holds is frozen by ``update_draft``'s refusal.
    """
    team = await as_team(db_session, rrf_app)
    typed = answers()
    typed["leader_date"] = "2020-01-02"
    created = await create(client, team, fields=typed)
    submitted = (await client.post(f"{REQUESTS}/{created['id']}/submit", headers=team)).json()
    lider = await as_lider(db_session, rrf_app, display_name="Eva da Base")

    endorsed = (await client.post(f"{REQUESTS}/{created['id']}/endorse", headers=lider)).json()

    frozen = (
        await db_session.execute(
            select(RRSnapshot).where(RRSnapshot.id == submitted["snapshot_id"])
        )
    ).scalar_one()
    assert frozen.document["fields"]["leader_name"] == ""
    assert frozen.document["fields"]["leader_date"] == "2020-01-02"

    live = (await client.get(f"{REQUESTS}/{created['id']}", headers=lider)).json()["document"]
    assert live["fields"]["leader_name"] == "Eva da Base"
    assert live["fields"]["leader_date"] == endorsed["endorsed_at"][:10]

    moved = {
        key for key, value in live["fields"].items() if value != frozen.document["fields"][key]
    }
    assert moved == {"leader_name", "leader_date"}
    assert {key: value for key, value in live.items() if key != "fields"} == {
        key: value for key, value in frozen.document.items() if key != "fields"
    }


async def test_a_revision_goes_back_to_the_base_unendorsed(db_session, client, rrf_app) -> None:
    """A signature given to a frozen version does not follow a text about to change.

    The revision carries neither the act nor the display pair born from it, while the
    team's own typed half (``tpp_name``) still travels — the line ``open_revision``
    stopped copying is exactly the one that now has a writer.
    """
    team = await as_team(db_session, rrf_app)
    created = await create(client, team)
    await client.post(f"{REQUESTS}/{created['id']}/submit", headers=team)
    lider = await as_lider(db_session, rrf_app)
    endorsed = (await client.post(f"{REQUESTS}/{created['id']}/endorse", headers=lider)).json()
    assert endorsed["endorsed_at"] is not None
    await _decide(db_session, created["id"], RRDecision.REVISE)

    revision = (await client.post(f"{REQUESTS}/{created['id']}/revise", headers=team)).json()

    assert revision["endorsed_by"] is None
    assert revision["endorsed_at"] is None
    assert revision["document"]["fields"]["leader_name"] == ""
    assert revision["document"]["fields"]["leader_date"] == ""
    assert revision["document"]["fields"]["tpp_name"] != ""
