"""The request lifecycle through the real routes: draft, read, submit, revise.

The guarantee under all of it is one sentence — **the mesa evaluates what the team
submitted** — and it is why ``_document.py`` exists and why these tests compare documents
rather than fields. Everything else here is the shape of the rules around that: who reaches
which rows, what happens when two copies of one draft disagree, and what a *revisar*
decision opens.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.db.models.resource_request import (
    RRDecision,
    RREvaluation,
    RRRequest,
    RRSnapshot,
)
from app.utils import resource_request_vocabularies as v
from app.utils.resource_request_typed_fields import PROMOTED_TO_SPINE
from tests.baker import make_user
from tests.test_resource_requests.conftest import auth_header, grant

REQUESTS = "/api/resource-requests/requests"


def answers(request_type: str = "traducao") -> dict[str, str]:
    """Every required answer filled, with the three that are columns given real values."""
    filled = dict.fromkeys(v.REQUIRED_TEXT_FIELDS[request_type], "preenchido")
    filled["tpp_date"] = "2026-08-25"
    filled["leader_date"] = "2026-08-25"
    filled["amount_requested"] = "1200.00"
    for key in filled:
        allowed = v.VOCABULARY_VALUES.get(key)
        if allowed:
            filled[key] = allowed[0]
    return filled


def draft(request_type: str = "traducao", **over: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "request_type": request_type,
        "currency": "BRL",
        "declaration": True,
        "fields": answers(request_type),
        "langs": [],
        "team": [{"name": "Ana", "role": "coordenação"}] if request_type == "traducao" else [],
        "chrono": [],
        "budget": [
            {"category_key": key, "description": "", "quantity": None, "amount": None}
            for key in v.BUDGET_CATEGORY_KEYS
        ],
    }
    payload.update(over)
    return payload


async def as_team(db_session, rrf_app, email: str = "equipe@rr.test") -> dict[str, str]:
    user = await make_user(db_session, email=email)
    await grant(db_session, user, rrf_app, "equipe")
    return await auth_header(db_session, user)


async def as_mesa(db_session, rrf_app, email: str = "mesa@rr.test") -> dict[str, str]:
    user = await make_user(db_session, email=email)
    await grant(db_session, user, rrf_app, "mesa")
    return await auth_header(db_session, user)


async def create(client, headers, **over: object) -> dict:
    res = await client.post(REQUESTS, json=draft(**over), headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


# ——— the draft ———————————————————————————————————————————————————————————————————


async def test_a_draft_is_created_owned_by_the_session_that_opened_it(
    db_session, client, rrf_app
) -> None:
    """``created_by`` comes from the token and is never in the payload.

    It is what GATE-02 D1 made possible by answering that everyone has an account, and it is
    what every scoping rule below stands on.
    """
    headers = await as_team(db_session, rrf_app)

    body = await create(client, headers)

    assert body["submitted_at"] is None
    assert body["stage"] == "triagem"
    assert body["created_by"] is not None


async def test_what_the_read_returns_is_what_the_write_accepts(db_session, client, rrf_app) -> None:
    """One shape both ways, which is what makes the snapshot comparison below meaningful."""
    headers = await as_team(db_session, rrf_app)
    created = await create(client, headers)

    read = await client.get(f"{REQUESTS}/{created['id']}", headers=headers)
    assert read.status_code == 200

    again = await client.patch(
        f"{REQUESTS}/{created['id']}", json=read.json()["document"], headers=headers
    )

    assert again.status_code == 200, again.text
    assert again.json()["document"] == read.json()["document"]


async def test_an_answer_survives_the_round_trip_through_the_columns(
    db_session, client, rrf_app
) -> None:
    """The six promoted answers go out in ``fields`` and come back in ``fields``.

    They are stored in columns, and a reader of this API should never have to know which six
    those are.
    """
    headers = await as_team(db_session, rrf_app)
    sent = draft()
    sent["fields"]["reg_name"] = "Projeto Xerente"

    res = await client.post(REQUESTS, json=sent, headers=headers)
    body = res.json()

    assert body["document"]["fields"]["reg_name"] == "Projeto Xerente"
    assert body["document"]["fields"]["amount_requested"] == "1200.00"
    assert body["document"]["fields"]["tpp_date"] == "2026-08-25"


async def test_an_unparsable_amount_is_refused_on_its_field(db_session, client, rrf_app) -> None:
    """422 and located, not a 500 from a cast three layers down."""
    headers = await as_team(db_session, rrf_app)
    sent = draft()
    sent["fields"]["amount_requested"] = "mil e duzentos"

    res = await client.post(REQUESTS, json=sent, headers=headers)

    assert res.status_code == 422
    assert "fields" in str(res.json()["detail"])


async def test_the_listing_carries_the_spine_and_not_the_documents(
    db_session, client, rrf_app
) -> None:
    """§4.2 made the sections their own table so a listing never drags the 45 answers."""
    headers = await as_team(db_session, rrf_app)
    await create(client, headers)

    res = await client.get(REQUESTS, headers=headers)

    assert res.status_code == 200
    assert len(res.json()) == 1
    assert res.json()[0]["document"] == {}


# ——— who reaches which rows ——————————————————————————————————————————————————————


async def test_a_team_does_not_reach_another_teams_request(db_session, client, rrf_app) -> None:
    """**404 and not 403**, because a 403 would confirm the id exists.

    That is the one thing a team must not learn about another team's request, so *missing*
    and *out of scope* are made indistinguishable from outside.
    """
    mine = await as_team(db_session, rrf_app, "one@rr.test")
    theirs = await as_team(db_session, rrf_app, "two@rr.test")
    created = await create(client, mine)

    res = await client.get(f"{REQUESTS}/{created['id']}", headers=theirs)

    assert res.status_code == 404


async def test_a_team_lists_only_its_own(db_session, client, rrf_app) -> None:
    mine = await as_team(db_session, rrf_app, "one@rr.test")
    theirs = await as_team(db_session, rrf_app, "two@rr.test")
    await create(client, mine)
    await create(client, theirs)

    listed = (await client.get(REQUESTS, headers=mine)).json()

    assert len(listed) == 1


async def test_the_mesa_reaches_every_request(db_session, client, rrf_app) -> None:
    """GATE-02 D4: the mesa may read and edit what a team wrote, and triage needs all of it."""
    team = await as_team(db_session, rrf_app)
    mesa = await as_mesa(db_session, rrf_app)
    created = await create(client, team)

    assert (await client.get(f"{REQUESTS}/{created['id']}", headers=mesa)).status_code == 200
    assert len((await client.get(REQUESTS, headers=mesa)).json()) == 1


async def test_a_mesa_member_who_is_also_equipe_still_reaches_every_request(
    db_session, client, rrf_app
) -> None:
    """The account ``auto_approve`` actually produces, and the reason the rule subtracts.

    Since ``20260828_rr02`` whoever registers is ``equipe``, so a mesa member holds ``equipe``
    **plus** ``mesa`` — two rows, with no constraint on ``(user_id, app_id)`` to prevent it.
    ``as_mesa`` above grants one role and cannot see this: ``reaches_every_request`` asks
    ``granted - {TEAM_ROLE, LEADER_ROLE}``, and asked the other way round — ``TEAM_ROLE in
    granted`` — it would answer *team* for exactly this account and hide the board from the
    mesa. The Líder's own middle reach is ``test_endorsement.py``'s subject.
    """
    team = await as_team(db_session, rrf_app)
    created = await create(client, team)

    user = await make_user(db_session, email="mesa-e-equipe@rr.test")
    await grant(db_session, user, rrf_app, "equipe")
    await grant(db_session, user, rrf_app, "mesa")
    both = await auth_header(db_session, user)

    assert (await client.get(f"{REQUESTS}/{created['id']}", headers=both)).status_code == 200
    assert len((await client.get(REQUESTS, headers=both)).json()) == 1


# ——— reconciliation ——————————————————————————————————————————————————————————————


async def test_a_client_copy_saved_later_wins_silently(db_session, client, rrf_app) -> None:
    """The ordinary case: the browser has the newer save, and nothing is worth saying."""
    headers = await as_team(db_session, rrf_app)
    created = await create(client, headers)
    later = datetime.now(UTC) + timedelta(minutes=5)

    res = await client.patch(
        f"{REQUESTS}/{created['id']}",
        json=draft(),
        params={"saved_at": later.isoformat()},
        headers=headers,
    )

    assert res.status_code == 200
    assert res.json()["discarded"] is None


async def test_a_client_copy_saved_earlier_is_discarded_and_says_so(
    db_session, client, rrf_app
) -> None:
    """The harsh half, and the one the issue asks to be explicit about.

    Writing the older copy anyway would make *latest wins* a phrase with no consequence and
    would throw away a save that happened after the one being sent. The answer names which
    side won and when each was saved, so a client can show it rather than guess.
    """
    headers = await as_team(db_session, rrf_app)
    created = await create(client, headers)
    stale = datetime.now(UTC) - timedelta(days=1)

    sent = draft()
    sent["fields"]["reg_name"] = "nome antigo"
    res = await client.patch(
        f"{REQUESTS}/{created['id']}",
        json=sent,
        params={"saved_at": stale.isoformat()},
        headers=headers,
    )

    assert res.status_code == 200
    discarded = res.json()["discarded"]
    assert discarded["winner"] == "server"
    assert discarded["client_saved_at"] is not None
    assert discarded["server_saved_at"] is not None
    assert res.json()["document"]["fields"]["reg_name"] != "nome antigo"


async def test_a_client_that_tracks_no_timestamp_simply_writes(db_session, client, rrf_app) -> None:
    """A first sync has nothing to compare, and refusing it would strand that client."""
    headers = await as_team(db_session, rrf_app)
    created = await create(client, headers)

    res = await client.patch(f"{REQUESTS}/{created['id']}", json=draft(), headers=headers)

    assert res.status_code == 200
    assert res.json()["discarded"] is None


async def test_a_saved_at_with_no_offset_is_refused_rather_than_guessed(
    db_session, client, rrf_app
) -> None:
    """The one place this module parts company with ``app/utils/stored_time.py``.

    That module reads a naive moment as UTC, and is right to: it normalises what the
    *database* wrote, and UTC is the only thing this codebase stores. A moment off the
    **wire** carries whatever the sender's clock had — and guessing wrong on this particular
    field does not draw a time three hours off, it decides whose work is thrown away. A
    ``saved_at`` sent as bare Brasília time would read three hours early and could discard
    the newer save.

    Cheap to comply with: JavaScript's own ``toISOString()`` already carries the ``Z``.
    """
    headers = await as_team(db_session, rrf_app)
    created = await create(client, headers)

    res = await client.patch(
        f"{REQUESTS}/{created['id']}",
        json=draft(),
        params={"saved_at": "2026-08-28T12:00:00"},
        headers=headers,
    )

    assert res.status_code == 400, res.text
    assert "offset" in res.json()["detail"]


# ——— submission ——————————————————————————————————————————————————————————————————


async def test_submitting_freezes_exactly_what_the_read_returns(
    db_session, client, rrf_app
) -> None:
    """The guarantee the whole issue is built around, asserted end to end.

    The snapshot is a **copy** of the read path and not a projection of it, so this is a
    comparison of two whole documents rather than of a few fields. A second serializer would
    show up here or in production, and only one of those is a good place to find it.
    """
    headers = await as_team(db_session, rrf_app)
    created = await create(client, headers)
    before = (await client.get(f"{REQUESTS}/{created['id']}", headers=headers)).json()

    submitted = await client.post(f"{REQUESTS}/{created['id']}/submit", headers=headers)

    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["document"] == before["document"]
    assert submitted.json()["submitted_at"] is not None
    assert submitted.json()["snapshot_id"]


async def test_the_stored_snapshot_is_the_document_the_team_saw(
    db_session, client, rrf_app
) -> None:
    """Read from the table rather than from the response, so nothing is taken on trust."""
    headers = await as_team(db_session, rrf_app)
    created = await create(client, headers)
    before = (await client.get(f"{REQUESTS}/{created['id']}", headers=headers)).json()

    await client.post(f"{REQUESTS}/{created['id']}/submit", headers=headers)

    stored = (
        await db_session.execute(select(RRSnapshot).where(RRSnapshot.request_id == created["id"]))
    ).scalar_one()
    assert stored.document == before["document"]


async def test_an_incomplete_draft_cannot_be_submitted(db_session, client, rrf_app) -> None:
    """The submission-time rules run against what is stored, not against a fresh payload.

    **400 and not 422**, because there is no body to locate an error in — the refusal is
    about a stored draft, and this API renders ``ValidationError`` as 400. The message
    carries the field names, which is what a client needs to show *what is missing* rather
    than merely *no*.
    """
    headers = await as_team(db_session, rrf_app)
    created = await create(client, headers, declaration=False)

    res = await client.post(f"{REQUESTS}/{created['id']}/submit", headers=headers)

    assert res.status_code == 400, res.text
    assert "declaration" in res.json()["detail"]


async def test_a_submitted_request_is_not_a_draft_any_more(db_session, client, rrf_app) -> None:
    """Editing it would move the ground under an evaluation pointing at a frozen document."""
    headers = await as_team(db_session, rrf_app)
    created = await create(client, headers)
    await client.post(f"{REQUESTS}/{created['id']}/submit", headers=headers)

    res = await client.patch(f"{REQUESTS}/{created['id']}", json=draft(), headers=headers)

    assert res.status_code == 409


async def test_submitting_twice_is_refused(db_session, client, rrf_app) -> None:
    headers = await as_team(db_session, rrf_app)
    created = await create(client, headers)
    await client.post(f"{REQUESTS}/{created['id']}/submit", headers=headers)

    again = await client.post(f"{REQUESTS}/{created['id']}/submit", headers=headers)

    assert again.status_code == 409


@pytest.mark.parametrize("other_role", ["mesa", "gestor"])
async def test_the_mesa_and_the_gestor_read_and_edit_but_do_not_sign(
    db_session, client, rrf_app, other_role: str
) -> None:
    """Submitting is the electronic acceptance (OBT-483), so only the author submits.

    Both roles hold ``edit_requests`` and reach every draft, and both of those stay true —
    the read and the edit below still answer 200. What must not happen is the third thing:
    a button either can reach signing in ``created_by``'s name. The refusal has to say that
    reason, not *no permission* — the guard's own message would be the capability one, and
    the caller holds the capability.

    Neither account is a platform admin, deliberately: ``require_capability`` waves admins
    through by the installation's standing rule (``_deps.py``), so an admin here would get
    past the guard for a reason that proves nothing about the author rule.
    """
    team = await as_team(db_session, rrf_app)
    created = await create(client, team)

    user = await make_user(db_session, email=f"{other_role}@nao-autor.test")
    await grant(db_session, user, rrf_app, other_role)
    headers = await auth_header(db_session, user)

    res = await client.post(f"{REQUESTS}/{created['id']}/submit", headers=headers)

    assert res.status_code == 403, res.text
    assert "electronic acceptance" in res.json()["detail"]
    assert "Capability" not in res.json()["detail"]

    read = await client.get(f"{REQUESTS}/{created['id']}", headers=headers)
    assert read.status_code == 200
    assert read.json()["submitted_at"] is None
    assert (
        await client.patch(f"{REQUESTS}/{created['id']}", json=draft(), headers=headers)
    ).status_code == 200


async def test_another_team_cannot_submit_what_it_cannot_reach(db_session, client, rrf_app) -> None:
    """The third role's negative: for another ``equipe`` the scope answers first, as 404."""
    mine = await as_team(db_session, rrf_app, "one@rr.test")
    theirs = await as_team(db_session, rrf_app, "two@rr.test")
    created = await create(client, mine)

    res = await client.post(f"{REQUESTS}/{created['id']}/submit", headers=theirs)

    assert res.status_code == 404


async def test_the_acceptance_is_served_as_author_plus_instant(db_session, client, rrf_app) -> None:
    """No new column and no captured scribble: who and when are already on the envelope.

    ``created_by`` and ``submitted_at`` are the *aceite eletrônico* the client asked for
    (28/aug/2026), both stamped by the server and neither typable through a payload.
    """
    headers = await as_team(db_session, rrf_app)
    created = await create(client, headers)

    submitted = (await client.post(f"{REQUESTS}/{created['id']}/submit", headers=headers)).json()

    assert submitted["created_by"] == created["created_by"]
    assert submitted["submitted_at"] is not None


async def test_a_submission_blank_on_the_signature_lines_goes_through(
    db_session, client, rrf_app
) -> None:
    """End to end for OBT-483's other half: nothing typed stands in for the acceptance.

    ``tpp_date``, ``leader_name`` and ``leader_date`` are submitted empty and the
    submission is accepted; ``tpp_name`` stays demanded because it is the requester the
    mesa reads on the card, and the account submitting may not be the Ponto focal.
    """
    headers = await as_team(db_session, rrf_app)
    unsigned = answers()
    for key in ("tpp_date", "leader_name", "leader_date"):
        unsigned[key] = ""
    created = await create(client, headers, fields=unsigned)

    res = await client.post(f"{REQUESTS}/{created['id']}/submit", headers=headers)

    assert res.status_code == 200, res.text

    unnamed = answers()
    unnamed["tpp_name"] = ""
    nameless = await create(client, headers, fields=unnamed)

    refused = await client.post(f"{REQUESTS}/{nameless['id']}/submit", headers=headers)

    assert refused.status_code == 400, refused.text
    assert "tpp_name" in refused.json()["detail"]


async def test_submitting_does_not_move_the_card(db_session, client, rrf_app) -> None:
    """Every stage change is BE-08's, with its ledger movement attached to it."""
    headers = await as_team(db_session, rrf_app)
    created = await create(client, headers)

    submitted = await client.post(f"{REQUESTS}/{created['id']}/submit", headers=headers)

    assert submitted.json()["stage"] == "triagem"


# ——— revision —————————————————————————————————————————————————————————————————————


async def _decide(
    db_session,
    request_id: str,
    decision: RRDecision | None,
    evaluated_at: datetime | None = None,
) -> None:
    """Write the mesa's decision straight to the table — BE-06 is what will write it for real.

    ``evaluated_at`` is stamped from the session by BE-06, and it is what orders two
    decisions on one snapshot, so a test about ordering has to set it.
    """
    snapshot = (
        await db_session.execute(select(RRSnapshot).where(RRSnapshot.request_id == request_id))
    ).scalar_one()
    db_session.add(
        RREvaluation(snapshot_id=snapshot.id, decision=decision, evaluated_at=evaluated_at)
    )
    await db_session.commit()


async def test_a_request_nobody_evaluated_cannot_be_revised(db_session, client, rrf_app) -> None:
    headers = await as_team(db_session, rrf_app)
    created = await create(client, headers)
    await client.post(f"{REQUESTS}/{created['id']}/submit", headers=headers)

    res = await client.post(f"{REQUESTS}/{created['id']}/revise", headers=headers)

    assert res.status_code == 409


@pytest.mark.parametrize(
    "decision", [RRDecision.APPROVED, RRDecision.DECLINED, RRDecision.CONDITIONAL]
)
async def test_only_a_revise_decision_opens_a_revision(
    db_session, client, rrf_app, decision: RRDecision
) -> None:
    """A team cannot reopen what the mesa approved, declined or approved with conditions."""
    headers = await as_team(db_session, rrf_app)
    created = await create(client, headers)
    await client.post(f"{REQUESTS}/{created['id']}/submit", headers=headers)
    await _decide(db_session, created["id"], decision)

    res = await client.post(f"{REQUESTS}/{created['id']}/revise", headers=headers)

    assert res.status_code == 409


async def test_a_revision_is_a_new_row_linked_to_what_was_evaluated(
    db_session, client, rrf_app
) -> None:
    """Both stay queryable, which is the DoD's own word.

    ``revision_of_id`` points at the **snapshot** and not at the request: what the mesa read
    is a frozen document, and its comments reference section numbers that have to keep
    meaning what they meant.
    """
    headers = await as_team(db_session, rrf_app)
    created = await create(client, headers)
    submitted = (await client.post(f"{REQUESTS}/{created['id']}/submit", headers=headers)).json()
    await _decide(db_session, created["id"], RRDecision.REVISE)

    res = await client.post(f"{REQUESTS}/{created['id']}/revise", headers=headers)

    assert res.status_code == 201, res.text
    revision = res.json()
    assert revision["id"] != created["id"]
    assert revision["revision_of_id"] == submitted["snapshot_id"]
    assert revision["submitted_at"] is None

    assert (await client.get(f"{REQUESTS}/{created['id']}", headers=headers)).status_code == 200
    assert (await client.get(f"{REQUESTS}/{revision['id']}", headers=headers)).status_code == 200


async def test_a_revision_carries_the_content_forward(db_session, client, rrf_app) -> None:
    """It copies rather than points, because from here it is the team's to change.

    All of it but one line: the Líder's display pair goes back **blank**, even where a
    draft had typed it — since BE-16 the endorsement is what writes ``leader_name``/
    ``leader_date``, so a revision starts with the line its own endorsement will fill,
    and ``test_endorsement.py`` owns that half of the story.
    """
    headers = await as_team(db_session, rrf_app)
    created = await create(client, headers)
    before = (await client.get(f"{REQUESTS}/{created['id']}", headers=headers)).json()
    await client.post(f"{REQUESTS}/{created['id']}/submit", headers=headers)
    await _decide(db_session, created["id"], RRDecision.REVISE)

    revision = (await client.post(f"{REQUESTS}/{created['id']}/revise", headers=headers)).json()

    unendorsed = dict(
        before["document"],
        fields={**before["document"]["fields"], "leader_name": "", "leader_date": ""},
    )
    assert revision["document"] == unendorsed


async def test_editing_a_revision_leaves_the_evaluated_snapshot_alone(
    db_session, client, rrf_app
) -> None:
    """What the mesa scored has to stay exactly as scored — the point of the whole chain."""
    headers = await as_team(db_session, rrf_app)
    created = await create(client, headers)
    submitted = (await client.post(f"{REQUESTS}/{created['id']}/submit", headers=headers)).json()
    await _decide(db_session, created["id"], RRDecision.REVISE)
    revision = (await client.post(f"{REQUESTS}/{created['id']}/revise", headers=headers)).json()

    changed = draft()
    changed["fields"]["reg_name"] = "corrigido depois da mesa"
    await client.patch(f"{REQUESTS}/{revision['id']}", json=changed, headers=headers)

    frozen = (
        await db_session.execute(
            select(RRSnapshot).where(RRSnapshot.id == submitted["snapshot_id"])
        )
    ).scalar_one()
    assert frozen.document["fields"]["reg_name"] != "corrigido depois da mesa"
    assert frozen.document == submitted["document"]


async def test_a_revision_opened_by_the_mesa_still_belongs_to_the_team(
    db_session, client, rrf_app
) -> None:
    """Dono é quem criou o documento, and clicking *revise* is not creating it.

    ``open_revision`` copies ``created_by`` from the original on purpose: a revision that
    belonged to the mesa member who opened it would 404 the team out of its own document
    — the owner's narrow scope reaches only what it authored.
    """
    headers = await as_team(db_session, rrf_app)
    created = await create(client, headers)
    await client.post(f"{REQUESTS}/{created['id']}/submit", headers=headers)
    await _decide(db_session, created["id"], RRDecision.REVISE)
    mesa = await as_mesa(db_session, rrf_app)

    revision = (await client.post(f"{REQUESTS}/{created['id']}/revise", headers=mesa)).json()

    assert revision["created_by"] == created["created_by"]
    assert (await client.get(f"{REQUESTS}/{revision['id']}", headers=headers)).status_code == 200


async def test_the_original_keeps_its_own_rows(db_session, client, rrf_app) -> None:
    """A revision is additive: two requests exist afterwards, not one that moved."""
    headers = await as_team(db_session, rrf_app)
    created = await create(client, headers)
    await client.post(f"{REQUESTS}/{created['id']}/submit", headers=headers)
    await _decide(db_session, created["id"], RRDecision.REVISE)

    await client.post(f"{REQUESTS}/{created['id']}/revise", headers=headers)

    rows = (await db_session.execute(select(RRRequest))).scalars().all()
    assert len(rows) == 2


async def test_a_section_only_edit_still_moves_the_saved_at_the_rule_compares(
    db_session, client, rrf_app
) -> None:
    """The reconciliation rule is only as good as the instant it compares against.

    ``onupdate`` fires when the ``rr_requests`` row is dirty, and a draft's ordinary edit is
    not on that row: the six promoted answers rarely move after the first save, while the
    section document and the budget lines — other tables — change every time. So the spine's
    own timestamp would sit still through almost every save, an older offline copy would
    compare as newer, and it would overwrite the newer work **silently** — which is the one
    thing this whole rule exists not to do.

    Found in review of PR #269.
    """
    headers = await as_team(db_session, rrf_app)
    created = await create(client, headers)
    first = created["updated_at"]

    only_a_section = draft()
    free_text = next(
        key
        for key in only_a_section["fields"]
        if key not in PROMOTED_TO_SPINE and key not in v.VOCABULARY_VALUES
    )
    only_a_section["fields"][free_text] = "resposta nova"
    res = await client.patch(f"{REQUESTS}/{created['id']}", json=only_a_section, headers=headers)

    assert res.status_code == 200, res.text
    assert res.json()["updated_at"] > first, (
        "a section-only edit left updated_at where it was, so the next stale copy wins"
    )
