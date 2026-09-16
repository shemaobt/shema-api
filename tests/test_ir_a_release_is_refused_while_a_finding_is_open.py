"""ENG-882 — the gate on what leaves the room, and the one code that forces it.

A release used to be built for a session whose telling-back still carried an open finding:
the packet said `checked: false`, listed the finding, and labelled itself ready for Refine
all the same. Downstream that is a draft the room approved, and the community hears it at the
external check as approved — including the halves of it the room's own analyst marked.

Marcia's whole gate is two things: no open finding, and the whole rehearsal heard. A team
that disagrees with a finding has a road already, and it is not the packet: the raised hand,
active the whole session, answered by a person. If that person agrees with the team, the
facilitator forces the release with their own code, and the force is recorded — who, when,
and which findings were open. Every other blocker is missing material rather than a dispute,
and no code forces those.

The route-level half of the slice lives here, in the shape of
`test_ir_a_release_is_a_numbered_row`, because a force is a facilitator act and the refusal
has to be what the tablet actually receives.
"""

from __future__ import annotations

import json
from typing import get_args

import httpx
import pytest
from httpx import ASGITransport
from pydantic import BaseModel
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

import app.db.models  # noqa: F401  (populates Base.metadata with every table)
from app.core.database import Base
from app.db.models.internalization_room import IRSession, IRTake
from app.services.internalization_room.comprehension.checkpoints import checkpoints_for
from app.services.internalization_room.comprehension.evidence import (
    EvidenceMethod,
    EvidenceObservation,
    EvidenceResult,
)
from app.services.internalization_room.segments import capture_segment, retire_every_segment
from app.services.internalization_room.sessions import (
    back_translation_of,
    create_session,
    save_back_translation,
    save_comprehension,
)
from tests.alembic_harness import columns_of, run_alembic, scalar
from tests.baker import (
    make_app,
    make_role,
)
from tests.release_harness import (
    APP_KEY,
    CLIP_MS,
    KEY,
    P02,
    PREFIX,
    TABLET,
    THE_FINDING,
    a_claimed_device,
    a_p02_telling_with_the_swapped_cause,
    a_rehearsal_only_half_heard,
    at_the_desk,
    desk_release,
    desk_release_at,
    one_stretch,
    ready_session,
    releases_of,
    reported_playback,
    supported_comprehension,
    team_headers,
    team_release,
)

REVISION = "20260911_rel02"
PREVIOUS_REVISION = "20260911_hard02"
TABLE = "ir_releases"
NEW_COLUMNS = {"device_id", "forced_by", "forced_at", "forced_open_findings"}
SEEDED_RELEASE = "0b6a1c2d-3e4f-4a5b-8c9d-0e1f2a3b4c5d"
SEEDED_SESSION = "7c1d2e3f-4a5b-4c6d-8e9f-0a1b2c3d4e5f"


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    from fastapi import FastAPI

    from app.api.internalization_room import router
    from app.core.config import get_settings
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    monkeypatch.setattr(get_settings(), "internalization_room_api_key", KEY, raising=False)

    test_app = FastAPI()
    test_app.include_router(router, prefix=PREFIX)
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture()
async def room_app(db_session: AsyncSession):
    app = await make_app(db_session, app_key=APP_KEY, name="Internalization Room")
    await make_role(db_session, app.id, role_key="facilitator", label="Facilitator", is_system=True)
    return app


async def test_a_p02_telling_with_the_swapped_cause_is_refused_by_name(client, db_session):
    """The acceptance criterion: the team asks, and the room says which door is shut.

    `checked` is false because the analyst's reading returned a finding and nobody answered
    it. Before this slice the same request returned the packet, labelled `ready_for_refine`,
    with the finding inside it — and a passage that says God gave the bread read downstream
    as a passage the daughters-in-law talked Naomi into leaving.
    """
    project, credential = await a_claimed_device(db_session)
    session = await a_p02_telling_with_the_swapped_cause(db_session, project)

    refused = await client.post(team_release(session.id), headers=team_headers(credential))

    assert refused.status_code == 409, refused.text
    assert "telling_back_not_checked" in refused.json()["detail"]
    assert await releases_of(db_session, session.id) == []


async def test_a_force_with_nothing_to_waive_is_still_recorded_as_one(client, db_session, room_app):
    """The Desk mints a draft the team never approved, and the row says which of them did it.

    Nothing about this session is refused, so the force waives nothing and the list of what
    was open is empty — and the row is still stamped, because what it records is who took the
    decision. A release the Desk minted is not a release the team approved, and a row that
    hid that would put the team's name on a draft they never called final.

    The half-heard case beside this one also ends with an empty list, but with a blocker
    actually waived. This is the one where there was nothing to waive at all.
    """
    project, _credential = await a_claimed_device(db_session)
    session = await ready_session(db_session, project_id=project.id)
    desk, facilitator = await at_the_desk(db_session, room_app, project)

    forced = await client.post(desk_release(session.id), headers=desk, json={"force": True})

    assert forced.status_code == 200, forced.text
    assert forced.json()["version"] == 1
    assert forced.json()["forced_at"] is not None
    (row,) = await releases_of(db_session, session.id)
    assert row.forced_by == facilitator.id
    assert row.forced_at is not None
    assert row.forced_open_findings == [], "vazio é uma resposta, e não a ausência de uma"
    assert row.device_id is None


async def test_the_facilitator_forces_past_a_rehearsal_only_half_heard(
    client, db_session, room_app
):
    """The other half of her gate, and the other half of what a code sets aside.

    Everything about this session is clean except that the tablet reports playing twenty of
    the sixty-one seconds: the team closed on a recording they did not hear through, which the
    release refuses. It is a dispute about what happened in the room and not missing material,
    so it is forceable — and without a case here, dropping `playback_did_not_cover_the_clip`
    from `FORCEABLE_BLOCKERS` would leave the whole suite green.
    """
    project, credential = await a_claimed_device(db_session)
    session = await a_rehearsal_only_half_heard(db_session, project)
    desk, _facilitator = await at_the_desk(db_session, room_app, project)

    refused = await client.post(team_release(session.id), headers=team_headers(credential))
    forced = await client.post(desk_release(session.id), headers=desk, json={"force": True})

    assert refused.status_code == 409, refused.text
    assert "playback_did_not_cover_the_clip" in refused.json()["detail"]
    assert forced.status_code == 200, forced.text
    assert forced.json()["version"] == 1
    (row,) = await releases_of(db_session, session.id)
    assert row.forced_at is not None
    assert row.forced_open_findings == [], (
        "nada estava em aberto: o que foi forçado foi a escuta, e o registro diz isso"
    )


async def test_the_facilitator_forces_the_release_and_the_row_says_so(client, db_session, room_app):
    """The other half of the gate: the road out, and the record it leaves behind.

    The failure this is against is the old force, which appeared only in the server log: the
    draft reached Refine looking exactly like one nobody had to force. So the row carries who
    forced it, when, and the findings as the packet dumped them at that moment — the session
    goes on changing, and nothing else could answer afterwards what was open.

    `device_id` is null because nobody's tablet did this. A force is the Desk's act.
    """
    project, _credential = await a_claimed_device(db_session)
    session = await a_p02_telling_with_the_swapped_cause(db_session, project)
    desk, facilitator = await at_the_desk(db_session, room_app, project)

    forced = await client.post(desk_release(session.id), headers=desk, json={"force": True})

    assert forced.status_code == 200, forced.text
    assert forced.json()["version"] == 1
    assert forced.json()["forced_at"] is not None
    (row,) = await releases_of(db_session, session.id)
    assert row.forced_by == facilitator.id
    assert row.forced_at is not None
    assert row.device_id is None
    assert row.packet["back_translation"]["checked"] is False
    assert [
        {key: value for key, value in finding.items() if key != "note"}
        for finding in row.forced_open_findings
    ] == row.packet["back_translation"]["findings"]
    assert [finding["kind"] for finding in row.forced_open_findings] == ["addition"]
    assert row.forced_open_findings[0]["note"] == THE_FINDING
    assert row.forced_open_findings[0]["chunk"] == 1


async def _comprehension_in_conflict(db: AsyncSession, session: IRSession) -> None:
    """A critical unit the team answered two ways, which is what needing more work is.

    Emptying the ledger does not say it: with every scene engaged, the coverage stands in for
    the practice report and a unit nobody evidenced blocks nothing. A conflict on a critical
    unit is the state, and it leaves the floor and the rehearsal exactly where they were.
    """
    state = supported_comprehension(P02)
    critical = next(checkpoint for checkpoint in checkpoints_for(P02) if checkpoint.critical)
    state.ledger = [
        *state.ledger,
        EvidenceObservation(
            id="ev-conflito",
            unit_id=critical.id,
            probe_id="probe-conflito",
            method=EvidenceMethod.MICRO_TELLBACK,
            result=EvidenceResult.CONFLICT,
        ),
    ]
    await save_comprehension(db, session, state)


async def _the_floor_not_met(db: AsyncSession, session: IRSession) -> None:
    session.coverage_state = {}
    await db.commit()


async def _no_rehearsal_audio(db: AsyncSession, session: IRSession) -> None:
    await db.execute(delete(IRTake).where(IRTake.session_id == session.id))
    await db.commit()


async def _nothing_told_back(db: AsyncSession, session: IRSession) -> None:
    await retire_every_segment(db, session.id)


async def _never_analysed(db: AsyncSession, session: IRSession) -> None:
    state = back_translation_of(session)
    state.analysed_segment_ids = None
    await save_back_translation(db, session, state)


async def _a_wordless_stretch(db: AsyncSession, session: IRSession) -> None:
    await capture_segment(
        db,
        session,
        take_id="ensaio-1",
        starts_ms=CLIP_MS,
        ends_ms=CLIP_MS + 9000,
        transcript=None,
    )


@pytest.mark.parametrize(
    ("blocker", "break_it"),
    [
        ("comprehension_needs_more_work", _comprehension_in_conflict),
        ("coverage_floor_not_met", _the_floor_not_met),
        ("no_rehearsal_audio", _no_rehearsal_audio),
        ("no_telling_back", _nothing_told_back),
        ("telling_back_never_analysed", _never_analysed),
        ("untold_stretch", _a_wordless_stretch),
    ],
)
async def test_the_force_waives_only_the_two_blockers_of_her_gate(
    client, db_session, room_app, blocker, break_it
):
    """A dispute is forceable; missing material is not.

    The open finding and the unheard part are the two things a person can disagree about
    after looking at them. A coverage floor nobody reached, a rehearsal nobody recorded, a
    stretch nobody told back: there is nothing there to overrule, and a code that waived them
    would let the Desk mint a packet out of a session that never happened.
    """
    project, _credential = await a_claimed_device(db_session)
    session = await a_p02_telling_with_the_swapped_cause(db_session, project)
    await break_it(db_session, session)
    desk, _facilitator = await at_the_desk(db_session, room_app, project)

    refused = await client.post(desk_release(session.id), headers=desk, json={"force": True})

    assert refused.status_code == 409, refused.text
    assert blocker in refused.json()["detail"]
    assert await releases_of(db_session, session.id) == []


async def test_a_panorama_is_never_forced(client, db_session, room_app):
    """The one blocker that is raised alone and before the rest, and stays out of reach."""
    project, _credential = await a_claimed_device(db_session)
    session = await create_session(db_session, pericope="OV", project_id=project.id)
    desk, _facilitator = await at_the_desk(db_session, room_app, project)

    refused = await client.post(desk_release(session.id), headers=desk, json={"force": True})

    assert refused.status_code == 409, refused.text
    assert "panorama_sessions_never_release" in refused.json()["detail"]
    assert await releases_of(db_session, session.id) == []


@pytest.mark.parametrize("body", [{}, {"force": False}])
async def test_a_facilitator_post_without_force_has_nothing_to_force(
    client, db_session, room_app, body
):
    """Forcing is said out loud or it does not happen.

    Its own code rather than the generic conflict: nothing about the passage is wrong and
    nothing downstream changes by retrying — the caller left the word out. Answered before the
    session is looked up, which the absent id below is what proves: the route with no force in
    it has nothing to say about which session it was aimed at.
    """
    project, _credential = await a_claimed_device(db_session)
    session = await a_p02_telling_with_the_swapped_cause(db_session, project)
    desk, _facilitator = await at_the_desk(db_session, room_app, project)

    refused = await client.post(desk_release(session.id), headers=desk, json=body)
    absent = await client.post(desk_release("nao-existe"), headers=desk, json=body)

    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "NOTHING_TO_FORCE"
    assert absent.status_code == 409, absent.text
    assert absent.json()["code"] == "NOTHING_TO_FORCE"
    assert await releases_of(db_session, session.id) == []


async def test_the_team_route_never_reads_force(client, db_session):
    """Approving stays the team's act, and forcing never becomes part of it.

    The version was already never the caller's to send; neither is the gate. A tablet that
    puts the word in its body gets exactly what it would have got without it — the refusal on
    a disputed session, and a plain release on a clean one, with the forced fields empty
    because nobody forced anything.
    """
    project, credential = await a_claimed_device(db_session)
    disputed = await a_p02_telling_with_the_swapped_cause(db_session, project)
    clean = await ready_session(db_session, project_id=project.id)

    refused = await client.post(
        team_release(disputed.id), headers=team_headers(credential), json={"force": True}
    )
    approved = await client.post(
        team_release(clean.id), headers=team_headers(credential), json={"force": True}
    )

    assert refused.status_code == 409, refused.text
    assert "telling_back_not_checked" in refused.json()["detail"]
    assert approved.status_code == 200, approved.text
    assert approved.json()["version"] == 1
    (row,) = await releases_of(db_session, clean.id)
    assert row.forced_by is None
    assert row.forced_at is None
    assert row.forced_open_findings is None


async def test_the_teams_approval_records_the_device(client, db_session):
    """The one team write that used to leave no attribution at all.

    Every other thing a tablet does carries the device that did it; the approval — the act
    that numbers a draft for the external check — did not.
    """
    project, credential = await a_claimed_device(db_session)
    session = await ready_session(db_session, project_id=project.id)

    approved = await client.post(team_release(session.id), headers=team_headers(credential))

    assert approved.status_code == 200, approved.text
    (row,) = await releases_of(db_session, session.id)
    assert row.device_id == TABLET


async def test_forcing_again_with_nothing_changed_returns_the_same_release(
    client, db_session, room_app
):
    """ADR 0014 holds over a force: a version that means nothing changed is worse than none."""
    project, _credential = await a_claimed_device(db_session)
    session = await a_p02_telling_with_the_swapped_cause(db_session, project)
    desk, _facilitator = await at_the_desk(db_session, room_app, project)

    first = await client.post(desk_release(session.id), headers=desk, json={"force": True})
    again = await client.post(desk_release(session.id), headers=desk, json={"force": True})

    assert first.status_code == 200, first.text
    assert again.status_code == 200, again.text
    assert again.json()["release_id"] == first.json()["release_id"]
    assert again.json()["version"] == 1
    assert [row.version for row in await releases_of(db_session, session.id)] == [1]


async def test_forcing_what_the_team_already_approved_returns_the_teams_release(
    client, db_session, room_app
):
    """The same rule reached from the other side, where the release that exists was not forced.

    A clean session the team already numbered has nothing for a force to waive, so the packet
    is the same packet and ADR 0014 hands back the row that already says it. That row is the
    team's, and `forced_at` null is the honest answer about it — the Desk reads it as a draft
    nobody had to force rather than as a force with no clock on it.
    """
    project, credential = await a_claimed_device(db_session)
    session = await ready_session(db_session, project_id=project.id)
    desk, _facilitator = await at_the_desk(db_session, room_app, project)

    approved = await client.post(team_release(session.id), headers=team_headers(credential))
    forced = await client.post(desk_release(session.id), headers=desk, json={"force": True})

    assert approved.status_code == 200, approved.text
    assert forced.status_code == 200, forced.text
    assert forced.json()["release_id"] == approved.json()["release_id"]
    assert forced.json()["forced_at"] is None
    assert [row.version for row in await releases_of(db_session, session.id)] == [1]


async def test_the_desks_read_still_builds_under_the_whole_list(client, db_session, room_app):
    """The GET is a read and never a force, so nothing is waived for it.

    A facilitator looking at a disputed session sees the refusal the team saw. Forcing is an
    act with a body and a record; opening the page is not one.
    """
    project, _credential = await a_claimed_device(db_session)
    session = await a_p02_telling_with_the_swapped_cause(db_session, project)
    desk, _facilitator = await at_the_desk(db_session, room_app, project)

    read = await client.get(desk_release(session.id), headers=desk)

    assert read.status_code == 409, read.text
    assert "telling_back_not_checked" in read.json()["detail"]


async def test_the_desk_reads_a_forced_release_by_its_version(client, db_session, room_app):
    """The stored packet, served as it was approved, under the number it was approved as.

    Nothing served `ir_releases.packet` until now: the only facilitator read rebuilt the
    packet live, which on a forced session is the refusal the team saw and not the draft the
    Desk minted. The two routes are contrasted here once — the live read still answers 409
    over the very session whose version 1 reads back whole.
    """
    project, _credential = await a_claimed_device(db_session)
    session = await a_p02_telling_with_the_swapped_cause(db_session, project)
    desk, _facilitator = await at_the_desk(db_session, room_app, project)

    forced = await client.post(desk_release(session.id), headers=desk, json={"force": True})
    read = await client.get(desk_release_at(session.id, 1), headers=desk)
    live = await client.get(desk_release(session.id), headers=desk)

    assert forced.status_code == 200, forced.text
    assert forced.json()["version"] == 1
    assert read.status_code == 200, read.text
    body = read.json()
    stored = await releases_of(db_session, session.id)
    assert json.dumps(body, sort_keys=True) == json.dumps(stored[0].packet, sort_keys=True), (
        "o pacote servido tem que ser o guardado, e não um recomposto que por acaso coincide"
    )
    assert body["version"] == 1
    assert body["release_id"] == forced.json()["release_id"]
    assert body["back_translation"]["checked"] is False
    assert body["back_translation"]["findings"]
    assert live.status_code == 409, live.text


async def test_a_version_that_was_never_minted_is_not_found(client, db_session, room_app):
    """A number nobody approved is nothing, and the room says so rather than composing one.

    The minted version is read first on purpose: three 404s from a route that does not exist
    read exactly like three 404s from a route that refuses, and only a 200 beside them says
    which of the two answered.
    """
    project, _credential = await a_claimed_device(db_session)
    session = await a_p02_telling_with_the_swapped_cause(db_session, project)
    never = await ready_session(db_session, project_id=project.id)
    desk, _facilitator = await at_the_desk(db_session, room_app, project)

    forced = await client.post(desk_release(session.id), headers=desk, json={"force": True})
    minted = await client.get(desk_release_at(session.id, 1), headers=desk)
    after = await client.get(desk_release_at(session.id, 2), headers=desk)
    before = await client.get(desk_release_at(session.id, 0), headers=desk)
    none_at_all = await client.get(desk_release_at(never.id, 1), headers=desk)

    assert forced.status_code == 200, forced.text
    assert minted.status_code == 200, minted.text
    assert after.status_code == 404, after.text
    assert before.status_code == 404, before.text
    assert none_at_all.status_code == 404, none_at_all.text


async def test_another_teams_facilitator_does_not_read_the_release(client, db_session, room_app):
    """A **Version** is per pericope per team, and another team's is never served.

    What hangs off a release is the whole of what a team recorded — every finding, every
    quote — so the refusal has to be a refusal and not a packet with fewer keys in it.
    """
    project_a, _credential_a = await a_claimed_device(db_session, email="a@example.com")
    project_b, _credential_b = await a_claimed_device(db_session, email="b@example.com")
    session = await a_p02_telling_with_the_swapped_cause(db_session, project_a)
    desk_a, _facilitator_a = await at_the_desk(db_session, room_app, project_a)
    desk_b, _facilitator_b = await at_the_desk(db_session, room_app, project_b)

    forced = await client.post(desk_release(session.id), headers=desk_a, json={"force": True})
    owner = await client.get(desk_release_at(session.id, 1), headers=desk_a)
    stranger = await client.get(desk_release_at(session.id, 1), headers=desk_b)

    assert forced.status_code == 200, forced.text
    assert owner.status_code == 200, owner.text
    assert stranger.status_code == 404, stranger.text
    assert "schema_version" not in stranger.json()


async def test_a_version_this_team_minted_elsewhere_reads_under_this_session(
    client, db_session, room_app
):
    """A **Version** is per pericope per project, and the URL a session names does not narrow it.

    Two conversations of one team about one passage share the sequence — the approval has
    always read the number that way, and this read has to agree with it. Scoping the row to
    the session as well would answer 404 for a draft of the very passage this session is
    standing on, and the packet it served would name a version nobody could then read back.

    The body naming the *other* session is the point: what comes back is the release as it was
    approved, not a packet composed for whoever asked.
    """
    project, credential = await a_claimed_device(db_session)
    approving = await ready_session(db_session, project_id=project.id)
    asking = await ready_session(db_session, project_id=project.id)
    desk, _facilitator = await at_the_desk(db_session, room_app, project)

    minted = await client.post(team_release(approving.id), headers=team_headers(credential))
    read = await client.get(desk_release_at(asking.id, 1), headers=desk)

    assert minted.status_code == 200, minted.text
    assert minted.json()["version"] == 1
    assert read.status_code == 200, read.text
    assert read.json()["release_id"] == minted.json()["release_id"]
    assert read.json()["session_id"] == approving.id
    assert read.json()["session_id"] != asking.id


async def test_the_version_read_is_this_teams_and_never_the_other_teams(
    client, db_session, room_app
):
    """Two teams on one passage each have a version 1, and neither is the other's.

    The scoping of the session is what refuses a stranger; this is the other half, on a
    facilitator who is asking about their own session. A **Version** is per pericope per
    project, so the number alone names two rows here — and a read that went by the number
    would either hand a team the other team's packet or fail over having found both.
    """
    project_a, credential_a = await a_claimed_device(db_session, email="a@example.com")
    project_b, credential_b = await a_claimed_device(db_session, email="b@example.com")
    ours = await ready_session(db_session, project_id=project_a.id)
    theirs = await ready_session(db_session, project_id=project_b.id)
    desk, _facilitator = await at_the_desk(db_session, room_app, project_a)

    our_first = await client.post(team_release(ours.id), headers=team_headers(credential_a))
    their_first = await client.post(team_release(theirs.id), headers=team_headers(credential_b))
    read = await client.get(desk_release_at(ours.id, 1), headers=desk)

    assert our_first.status_code == 200, our_first.text
    assert their_first.status_code == 200, their_first.text
    assert their_first.json()["version"] == 1, "as duas equipes têm uma versão 1 desta passagem"
    assert read.status_code == 200, read.text
    assert read.json()["release_id"] == our_first.json()["release_id"]
    assert read.json()["session_id"] == ours.id


async def test_the_stored_packet_is_served_as_approved_not_rebuilt(client, db_session, room_app):
    """Version 1 goes on reading as version 1 after the team changed the passage.

    A rebuilt packet would answer both numbers with today's content, which is exactly the
    thing the numbered row exists to prevent: Marcia's comments hang off a draft, and a draft
    that silently becomes the next one carries them onto a passage nobody reviewed.
    """
    project, credential = await a_claimed_device(db_session)
    session = await ready_session(db_session, project_id=project.id)
    desk, _facilitator = await at_the_desk(db_session, room_app, project)

    first = await client.post(team_release(session.id), headers=team_headers(credential))
    await one_stretch(db_session, session, text="Rute espigou no campo de Boaz")
    second = await client.post(team_release(session.id), headers=team_headers(credential))

    one = await client.get(desk_release_at(session.id, 1), headers=desk)
    two = await client.get(desk_release_at(session.id, 2), headers=desk)

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert second.json()["version"] == 2
    assert one.status_code == 200, one.text
    assert two.status_code == 200, two.text
    rows = await releases_of(db_session, session.id)
    assert [row.version for row in rows] == [1, 2]
    assert one.json()["package_sha256"] == rows[0].package_sha256
    assert two.json()["package_sha256"] == rows[1].package_sha256
    assert one.json()["package_sha256"] != two.json()["package_sha256"]
    assert one.json()["version"] == 1
    assert two.json()["version"] == 2


async def test_the_teams_approval_after_a_force_returns_the_forced_release(
    client, db_session, room_app
):
    """ADR 0014 reaches the team route too: an unchanged packet returns the release that exists.

    The team asked, was refused, and a person answered the raised hand by forcing the draft.
    Asking again with nothing changed since is the same question the Desk already answered —
    and the tablet used to get the old refusal back, with a numbered draft of that very
    passage sitting in the table.

    The row is returned and not rewritten: the force keeps its clock and the team's device is
    not stamped over an act that was not the team's.
    """
    project, credential = await a_claimed_device(db_session)
    session = await a_p02_telling_with_the_swapped_cause(db_session, project)
    desk, _facilitator = await at_the_desk(db_session, room_app, project)

    refused = await client.post(team_release(session.id), headers=team_headers(credential))
    forced = await client.post(desk_release(session.id), headers=desk, json={"force": True})
    again = await client.post(team_release(session.id), headers=team_headers(credential))

    assert refused.status_code == 409, refused.text
    assert "telling_back_not_checked" in refused.json()["detail"]
    assert forced.status_code == 200, forced.text
    assert again.status_code == 200, again.text
    assert again.json()["release_id"] == forced.json()["release_id"]
    assert again.json()["version"] == 1
    (row,) = await releases_of(db_session, session.id)
    await db_session.refresh(row)
    assert row.forced_at is not None
    assert row.device_id is None


async def test_a_changed_and_still_blocked_session_is_refused_after_a_force(
    client, db_session, room_app
):
    """Compare-first never becomes a team force: what is compared is the packet, not the gate.

    One more stretch told back moves the content while `checked` stays false, so the hash no
    longer matches the forced row and the blocker is judged with nothing waived. The force
    afterwards is the measurement of the premise: it mints version 2, which it could only do
    because the content really did change.
    """
    project, credential = await a_claimed_device(db_session)
    session = await a_p02_telling_with_the_swapped_cause(db_session, project)
    desk, _facilitator = await at_the_desk(db_session, room_app, project)

    forced = await client.post(desk_release(session.id), headers=desk, json={"force": True})
    await one_stretch(db_session, session, text="Rute espigou no campo de Boaz")
    refused = await client.post(team_release(session.id), headers=team_headers(credential))

    assert forced.status_code == 200, forced.text
    assert refused.status_code == 409, refused.text
    assert "telling_back_not_checked" in refused.json()["detail"]
    assert [row.version for row in await releases_of(db_session, session.id)] == [1]

    forced_again = await client.post(desk_release(session.id), headers=desk, json={"force": True})

    assert forced_again.status_code == 200, forced_again.text
    assert forced_again.json()["version"] == 2, (
        "a premissa do caso: o conteúdo mudou, e por isso a recusa acima não foi uma comparação"
    )


async def test_a_changed_and_clean_session_after_a_force_mints_the_next_version(
    client, db_session, room_app
):
    """The other side of compare-first: changed and clean is a new draft, and the team's own.

    The Desk forced past a rehearsal the team had not heard through; the team then played it
    through and asked. Nothing stands in the way now and the content is not what was forced,
    so this is version 2 — stamped with the tablet that approved it and with no force on it.
    """
    project, credential = await a_claimed_device(db_session)
    session = await a_rehearsal_only_half_heard(db_session, project)
    desk, _facilitator = await at_the_desk(db_session, room_app, project)

    forced = await client.post(desk_release(session.id), headers=desk, json={"force": True})
    await reported_playback(db_session, session, back_translation_of(session))
    approved = await client.post(team_release(session.id), headers=team_headers(credential))

    assert forced.status_code == 200, forced.text
    assert forced.json()["version"] == 1
    assert approved.status_code == 200, approved.text
    assert approved.json()["version"] == 2
    rows = await releases_of(db_session, session.id)
    assert [row.version for row in rows] == [1, 2]
    assert rows[1].forced_at is None
    assert rows[1].device_id == TABLET


async def test_the_team_route_refuses_a_panorama(client, db_session):
    """A panorama is not a draft of a passage at all, so the team's route refuses it too.

    The force has its own case beside this one; nothing drove the *team* route on a panorama
    until now. It says nothing about the comparison and cannot: this session has approved
    nothing, so there is no release to compare against whatever the order, and a panorama
    with a prior release is not a state that exists — composing one raises on the map.
    """
    project, credential = await a_claimed_device(db_session)
    session = await create_session(db_session, pericope="OV", project_id=project.id)

    refused = await client.post(team_release(session.id), headers=team_headers(credential))

    assert refused.status_code == 409, refused.text
    assert "panorama_sessions_never_release" in refused.json()["detail"]
    assert await releases_of(db_session, session.id) == []


def _body_fields(route) -> set[str]:
    """Every name this route accepts in a request body, flat.

    A model body contributes its fields and a form body contributes its parameters, because
    what is being asked is whether the word reaches the handler at all — not how it is spelled
    on the wire. An optional model is read through its union, or the room's own `finish` route
    would answer with the parameter's name and hide the three fields it really takes.
    """
    found: set[str] = set()
    for param in getattr(getattr(route, "dependant", None), "body_params", []):
        annotation = param.field_info.annotation
        models = [
            candidate
            for candidate in (annotation, *get_args(annotation))
            if isinstance(candidate, type) and issubclass(candidate, BaseModel)
        ]
        if not models:
            found.add(param.name)
        for model in models:
            found |= set(model.model_fields)
    return found


def test_no_room_caller_route_accepts_force() -> None:
    """A tablet cannot force, and that is a property of every route rather than of one.

    Read off the mounted application, so a room route that grows the word tomorrow fails here
    without anybody remembering this file. The half that is red before the slice is the
    facilitator route existing at all; the half that is the guard, and stays the guard, is
    that no other route reads `force` and that the one that does sits behind the facilitator
    role — the gate object itself, not a path that happens to be spelled `/facilitator`.
    """
    from app.api.facilitator._deps import facilitator_role
    from app.main import app

    gate = facilitator_role.dependency

    def carries(dependant) -> bool:
        return any(sub.call is gate or carries(sub) for sub in dependant.dependencies)

    forcing = sorted(
        (route.path, sorted(route.methods))
        for route in app.routes
        if getattr(route, "path", "").startswith(PREFIX) and "force" in _body_fields(route)
    )

    assert forcing == [(f"{PREFIX}/facilitator/sessions/{{session_id}}/release", ["POST"])]
    assert carries(
        next(route for route in app.routes if getattr(route, "path", "") == forcing[0][0]).dependant
    ), "a rota que lê force não está atrás do papel de facilitador"


@pytest.fixture()
async def applied_database(tmp_path) -> str:
    """The schema as the model now describes it, stamped at this revision, with a release in it.

    Alembic's whole chain does not run on SQLite, which is why every migration test here
    builds the tables from ``Base.metadata`` and stamps the revision under test instead of
    upgrading into it. The seeded row is what makes the round trip worth running: a column
    re-added as NOT NULL, or a downgrade that scratched the table, is found here and nowhere
    else.
    """
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'ir_forced_release_migration.db'}"
    engine = create_async_engine(database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(
            text(
                "INSERT INTO ir_releases (id, session_id, project_id, pericope, version,"
                " package_sha256, packet, approved_at) VALUES (:id, :session_id, 'time-1',"
                " 'P02', 1, :sha, '{}', '2026-09-11 09:00:00')"
            ),
            {"id": SEEDED_RELEASE, "session_id": SEEDED_SESSION, "sha": "c" * 64},
        )
    await engine.dispose()

    stamped = run_alembic(database_url, "stamp", REVISION)
    assert stamped.returncode == 0, stamped.stderr
    return database_url


async def test_the_migration_adds_the_four_columns_both_ways(applied_database):
    assert await columns_of(applied_database, TABLE) >= NEW_COLUMNS

    down = run_alembic(applied_database, "downgrade", PREVIOUS_REVISION)
    assert down.returncode == 0, down.stderr
    assert NEW_COLUMNS.isdisjoint(await columns_of(applied_database, TABLE))

    up = run_alembic(applied_database, "upgrade", REVISION)
    assert up.returncode == 0, up.stderr
    assert await columns_of(applied_database, TABLE) >= NEW_COLUMNS
    assert (
        await scalar(
            applied_database,
            "SELECT forced_by FROM ir_releases WHERE id = :id",
            {"id": SEEDED_RELEASE},
        )
        is None
    ), (
        "a coluna volta vazia e não preenchida: quem prova que ela é anulável é o próprio "
        "upgrade acima, que numa tabela com linhas falharia se fosse NOT NULL — esta linha "
        "recusa um server_default que inventasse um facilitador para quem nunca forçou nada"
    )
    assert await scalar(applied_database, f"SELECT count(*) FROM {TABLE}", {}) == 1
