"""ENG-938 — the packet carries the check block, in Marcia's names and outside the hash.

Refine reads a `check` block beside the **Version**: whether the check happened, whether the
whole rehearsal was heard, when the verdict was reached, what is still open and where the
retroverification file is. The packet said none of that — `back_translation.checked` was the
whole of it, the force lived only on the row, and the analyst's note travelled in full.

The block is a view of the release row and not part of the hashed content (ADR 0020): two of
its facts, the force and the **Version**, are written after the packet is built and hashed, so
carrying them inside would make a forced packet and the team's unchanged packet hash
differently and mint a version for nothing.

These cases read the packet the routes serve and the rows the approval writes. The wire names
are written here as literals rather than read off any constant of the app: they are Marcia's,
and renaming one is a decision taken with her rather than a refactor.
"""

from __future__ import annotations

import json
from functools import partial
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSession
from app.services.internalization_room.back_translation import (
    BackTranslationState,
    Finding,
    FindingKind,
    SupersededAttempt,
)
from app.services.internalization_room.release import (
    FORCEABLE_BLOCKERS,
    InternalizationReleaseBlocked,
    approve_release,
    build_internalization_release,
)
from app.services.internalization_room.segments import (
    capture_segment,
    divide_segment,
    final_segments,
)
from app.services.internalization_room.sessions import get_session
from tests.baker import make_app, make_role
from tests.release_harness import (
    APP_KEY,
    CLIP_MS,
    P,
    a_claimed_device,
    a_p02_telling_with_the_swapped_cause,
    a_rehearsal_only_half_heard,
    at_the_desk,
    desk_release,
    desk_release_at,
    never_analysed_telling_back,
    one_stretch,
    ready_session,
    releases_of,
    reported_playback,
    team_headers,
    team_release,
    told_back_with_an_open_finding,
)
from tests.room_harness import (
    played_every_part,
    press_terminei,
    rehearsed_in_parts,
    room_client,
    stored_telling_back,
    the_analyst_reads,
    the_room_speaks,
)

#: Her names for the block and for one entry of its list, written out rather than imported.
#: A case that read them off the module under test would agree with any rename, and the whole
#: point of this slice is that these eight words are hers.
THE_BLOCKS_NAMES = {
    "version",
    "status",
    "conferida",
    "forced",
    "heardComplete",
    "lastCheckAt",
    "findings",
    "retroUrl",
}
AN_ENTRYS_NAMES = {"kind", "frase", "idx", "clipKey"}

#: A note no other string in the packet contains, so a case can ask where it did and did not
#: travel without matching anything else by accident.
THE_ANALYSTS_NOTE = "NOTA-DO-ANALISTA-9f3c"

#: The rehearsal these cases tell back over. It is what this module's own builder writes, so
#: it is the subject a case of its own may name; a case standing on a harness builder reads
#: the take off the stretch instead.
REHEARSAL = "ensaio-1"

#: One rehearsal told back in three stretches, the shape
#: `test_ir_the_version_freezes_the_frase_number.py` uses: three is the smallest reading in
#: which a missing element placed after frase 2 lands on a stretch whose own number is 3.
THREE_STRETCHES = (
    ("Noemi ouviu que o Senhor tinha visitado o seu povo", 0, 20000),
    ("ela saiu do lugar onde estava com as duas noras", 20000, 40000),
    ("e puseram-se a caminho para voltar a Juda", 40000, CLIP_MS),
)


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    async with room_client(db_session, monkeypatch) as room:
        yield room


@pytest.fixture()
async def room_app(db_session: AsyncSession):
    app = await make_app(db_session, app_key=APP_KEY, name="Internalization Room")
    await make_role(db_session, app.id, role_key="facilitator", label="Facilitator", is_system=True)
    return app


async def _live_view(
    db: AsyncSession, session: IRSession, *, waived: frozenset[str] = FORCEABLE_BLOCKERS
) -> dict[str, Any]:
    """The packet this session composes right now, read past the gate the case is not about.

    The composer is what both the live facilitator read and the approval call, so this is the
    view the block is derived from, with `version` null and `forced` false by rule.
    """
    fresh = await get_session(db, session.id)
    return await build_internalization_release(db, fresh, waived=waived)


async def _three_stretches_told(db: AsyncSession, session: IRSession) -> BackTranslationState:
    for text, starts_ms, ends_ms in THREE_STRETCHES:
        await capture_segment(
            db,
            session,
            take_id=REHEARSAL,
            starts_ms=starts_ms,
            ends_ms=ends_ms,
            bridge_take_id=f"retro-{starts_ms}",
            transcript=text,
        )
    told = await final_segments(db, session.id)
    return BackTranslationState(
        scope=P,
        findings=[],
        checked=True,
        analysed_segment_ids=[stretch.id for stretch in told],
    )


async def _read_again(
    db: AsyncSession, session: IRSession, findings: tuple[Finding, ...]
) -> BackTranslationState:
    """The state a reading that raised these findings leaves behind, stored with the report."""
    told = await final_segments(db, session.id)
    state = BackTranslationState(
        scope=P,
        findings=list(findings),
        checked=not findings,
        analysed_segment_ids=[stretch.id for stretch in told],
    )
    await reported_playback(db, session, state)
    return state


class _AnAnalystRaisingOneAddition:
    """The analyst, answering one addition on the first frase rather than a clean reading.

    `room_harness.Analyst` reads clean, which is the other half of the case: the timestamp has
    to be stamped at a verdict that raised something exactly as at one that did not.
    """

    async def __call__(self, *, system_prompt: str, user_content: str, **_: Any) -> str:
        return json.dumps(
            {"findings": [{"kind": "addition", "note": THE_ANALYSTS_NOTE, "chunk": 1}]}
        )


async def test_the_check_block_spells_marcias_names_verbatim(db_session: AsyncSession) -> None:
    """The acceptance criterion's first half: the block is signed in her names and no others.

    Exactly these keys, so a key added here is added on purpose and a key renamed is a
    conversation with her. The same for one entry of `findings`, which is where her `idx`,
    `clipKey` and `frase` stand for our `segment_id`, `take_id` and the frozen number.
    """
    clean = await ready_session(db_session)
    disputed = await ready_session(db_session, tell=told_back_with_an_open_finding)

    clean_packet = await build_internalization_release(db_session, clean)
    open_finding = await _live_view(db_session, disputed)

    assert set(clean_packet["check"]) == THE_BLOCKS_NAMES
    assert set(open_finding["check"]) == THE_BLOCKS_NAMES
    (entry,) = open_finding["check"]["findings"]
    assert set(entry) == AN_ENTRYS_NAMES


async def test_a_checked_session_reads_conferida(db_session: AsyncSession) -> None:
    """A session the room checked clean, read live: the check happened and nothing was forced."""
    session = await ready_session(db_session)

    check = (await build_internalization_release(db_session, session))["check"]

    assert check["status"] == "conferida"
    assert check["conferida"] is True
    assert check["forced"] is False
    assert check["version"] is None
    assert check["findings"] == []
    assert check["heardComplete"] is True
    assert check["retroUrl"] == (
        f"/api/internalization-room/facilitator/sessions/{session.id}/retroverificacao"
    )


async def test_a_forced_release_reads_forcada_as_stored(
    client, db_session: AsyncSession, room_app
) -> None:
    """The draft a person minted over an open finding says so, under the number it was given.

    The stored packet is the contract: the block is stamped from the row the approval writes,
    so `version` is that row's number and `forced` is true. `status` is about the check and
    `forced` about the force, and here the check did not happen.

    The live read of the same session still answers 409 (ENG-937): a forced row reads back by
    its version and nowhere else.
    """
    project, _credential = await a_claimed_device(db_session)
    session = await a_p02_telling_with_the_swapped_cause(db_session, project)
    desk, _facilitator = await at_the_desk(db_session, room_app, project)
    (told,) = await final_segments(db_session, session.id)

    forced = await client.post(desk_release(session.id), headers=desk, json={"force": True})
    read = await client.get(desk_release_at(session.id, 1), headers=desk)
    live = await client.get(desk_release(session.id), headers=desk)

    assert forced.status_code == 200, forced.text
    assert read.status_code == 200, read.text
    check = read.json()["check"]
    assert check["status"] == "forcada"
    assert check["forced"] is True
    assert check["conferida"] is False
    assert check["version"] == 1
    assert check["findings"] == [
        {"kind": "addition", "frase": 1, "idx": told.id, "clipKey": told.take_id}
    ]
    (row,) = await releases_of(db_session, session.id)
    assert row.packet["check"] == check, "o bloco servido é o guardado, e não um recomposto"
    assert live.status_code == 409, live.text


async def test_a_never_analysed_session_reads_sem_conferencia(db_session: AsyncSession) -> None:
    """A telling-back the analyst never read: no check happened, and nothing was overruled.

    Composed past `telling_back_never_analysed` because no consumer reaches this packet today:
    the blocker is missing material rather than a dispute, so no facilitator's code opens it
    and neither route serves it. The third word of `status` exists for her format to be whole,
    and this is the state it names.
    """
    session = await ready_session(db_session, tell=never_analysed_telling_back)

    check = (
        await _live_view(db_session, session, waived=frozenset({"telling_back_never_analysed"}))
    )["check"]

    assert check["status"] == "sem_conferencia"
    assert check["conferida"] is False
    assert check["forced"] is False
    assert check["lastCheckAt"] is None
    assert check["findings"] == []


async def test_an_open_finding_without_a_force_reads_sem_conferencia(
    db_session: AsyncSession,
) -> None:
    """Read and not clean, with nobody overruling it: the check did not happen.

    This is the view `approve_release` composes before it stamps the row, which is why the
    same session read back after a force says `forcada` and this one does not.
    """
    session = await ready_session(db_session, tell=told_back_with_an_open_finding)

    check = (await _live_view(db_session, session))["check"]

    assert check["status"] == "sem_conferencia"
    assert check["conferida"] is False
    assert check["forced"] is False
    assert [entry["kind"] for entry in check["findings"]] == ["addition"]


async def test_the_analysts_note_is_nowhere_in_the_packet(db_session: AsyncSession) -> None:
    """ENG-892: what is open travels as a kind and an address, and never as why.

    The note cites internal rule ids and uses words banned from the team's ears, and Refine is
    where the team works. It is not deleted — it keeps a reader in the **Retroverification
    file**, which is the one artifact written for somebody allowed to see them.

    Two greps, and the difference between them is the point. The key is looked for over the
    whole telling-back rather than over the list the note used to travel in, so a key added to
    a finding later cannot bring it back in the other list — the superseded attempt is here for
    exactly that, being a second list of the same thing. It is not looked for over the whole
    packet because `comprehension` carries a `note` of its own, which is the room's own note
    about a probe and nothing the analyst ever wrote.

    The analyst's *words* are looked for over the whole packet, and that is the grep that
    survives a field nobody has written yet: whatever block a future key lands in, the marker
    is what says the note reached it. What stays on a finding is the address the block shares.
    """
    session = await ready_session(
        db_session, tell=partial(told_back_with_an_open_finding, note=THE_ANALYSTS_NOTE)
    )
    state = await stored_telling_back(db_session, session)
    state.superseded = [
        SupersededAttempt(
            findings=[Finding(kind=FindingKind.MISSING, note=THE_ANALYSTS_NOTE, chunk=1)]
        )
    ]
    await reported_playback(db_session, session, state)

    packet = await _live_view(db_session, session)

    assert '"note"' not in json.dumps(packet["back_translation"])
    assert THE_ANALYSTS_NOTE not in json.dumps(packet)
    assert packet["schema_version"] == "tripod.internalization-release.v0.6"
    assert set(packet["back_translation"]["findings"][0]) == {
        "kind",
        "segment_id",
        "chunk",
        "fills_silence",
        "raised_by_check",
    }


async def test_conferida_and_heard_complete_never_disagree_with_the_gate(
    client, db_session: AsyncSession, room_app
) -> None:
    """The two facts the block reports are the two the gate asks, and they cannot drift.

    A session checked clean over a rehearsal the team heard twenty of sixty-one seconds of is
    both things at once: the check happened, and the listening did not cover the recording. So
    `conferida` is true while `heardComplete` is false, and the gate names the unheard part
    over the very same session. Forced from the Desk, the row keeps `conferida` and adds the
    force — the status is about the check, the flag about the force.
    """
    project, _credential = await a_claimed_device(db_session)
    session = await a_rehearsal_only_half_heard(db_session, project)
    desk, _facilitator = await at_the_desk(db_session, room_app, project)

    with pytest.raises(InternalizationReleaseBlocked) as refused:
        await build_internalization_release(db_session, await get_session(db_session, session.id))

    assert "playback_did_not_cover_the_clip" in refused.value.blockers
    half_heard = (await _live_view(db_session, session))["check"]
    assert half_heard["conferida"] is True
    assert half_heard["heardComplete"] is False

    forced = await client.post(desk_release(session.id), headers=desk, json={"force": True})
    read = await client.get(desk_release_at(session.id, 1), headers=desk)

    assert forced.status_code == 200, forced.text
    assert read.status_code == 200, read.text
    assert read.json()["check"]["status"] == "conferida"
    assert read.json()["check"]["forced"] is True
    assert read.json()["check"]["heardComplete"] is False

    heard_whole = await ready_session(db_session)
    whole = await build_internalization_release(db_session, heard_whole)
    assert whole["check"]["heardComplete"] is True


async def test_the_check_block_sits_outside_the_hash(
    client, db_session: AsyncSession, room_app, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Three sides of one rule: the block moves without the content moving.

    Two reads of an unchanged session carry one hash and one block, `lastCheckAt` included —
    it is the moment of the verdict and not of the read, so the session is one a verdict
    really stamped rather than one built with the field empty. And a forced row's stored
    packet and the live view of that very session hash the same although their `status`
    disagree, which is the case ADR 0020 was written for: inside the hash, a force would mint
    a version for nothing the next time the team approved.
    """
    the_room_speaks(monkeypatch)
    the_analyst_reads(monkeypatch)
    unchanged, parts = await rehearsed_in_parts(db_session, 1)
    pressed = await press_terminei(
        client, unchanged.id, report=played_every_part([part.id for part in parts])
    )

    assert pressed.status_code == 200, pressed.text
    first = await _live_view(db_session, unchanged, waived=frozenset())
    second = await _live_view(db_session, unchanged, waived=frozenset())

    assert first["check"]["lastCheckAt"] is not None, "senão a igualdade abaixo é None == None"
    assert first["package_sha256"] == second["package_sha256"]
    assert first["check"] == second["check"]

    project, _credential = await a_claimed_device(db_session)
    session = await a_p02_telling_with_the_swapped_cause(db_session, project)
    desk, _facilitator = await at_the_desk(db_session, room_app, project)

    forced = await client.post(desk_release(session.id), headers=desk, json={"force": True})
    stored = (await client.get(desk_release_at(session.id, 1), headers=desk)).json()
    live = await _live_view(db_session, session)

    assert forced.status_code == 200, forced.text
    assert stored["package_sha256"] == live["package_sha256"]
    assert stored["check"]["status"] == "forcada"
    assert live["check"]["status"] == "sem_conferencia"


async def test_the_verdict_stamps_when_the_check_ran(
    client, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`lastCheckAt` is when the check last ran, written where `checked` is written.

    At every verdict and not only at a clean one: the question it answers is when the analyst
    last read this telling-back, which a team that came out with a finding also has an answer
    to. A state saved before this deploy carries none, and reads null beside a `status` that
    still says `conferida` — the field is optional on a JSON column, so no row was migrated.
    """
    the_room_speaks(monkeypatch)
    the_analyst_reads(monkeypatch)
    clean, parts = await rehearsed_in_parts(db_session, 1)

    assert (await stored_telling_back(db_session, clean)).checked_at is None

    answered = await press_terminei(
        client, clean.id, report=played_every_part([part.id for part in parts])
    )

    assert answered.status_code == 200, answered.text
    stamped = await stored_telling_back(db_session, clean)
    assert stamped.checked is True
    assert stamped.checked_at is not None
    packet = await _live_view(db_session, clean, waived=frozenset())
    assert packet["check"]["lastCheckAt"] == stamped.checked_at.isoformat()
    assert packet["check"]["status"] == "conferida"

    from app.services.internalization_room import back_translation as bt_service

    monkeypatch.setattr(bt_service, "call_agent", _AnAnalystRaisingOneAddition())
    disputed, its_parts = await rehearsed_in_parts(db_session, 1)

    raised = await press_terminei(
        client, disputed.id, report=played_every_part([part.id for part in its_parts])
    )

    assert raised.status_code == 200, raised.text
    after_a_finding = await stored_telling_back(db_session, disputed)
    assert after_a_finding.checked is False
    assert after_a_finding.checked_at is not None
    disputed_check = (await _live_view(db_session, disputed))["check"]
    assert disputed_check["status"] == "sem_conferencia"
    assert disputed_check["lastCheckAt"] == after_a_finding.checked_at.isoformat()

    before_this_deploy = await ready_session(db_session)
    older = await build_internalization_release(db_session, before_this_deploy)
    assert older["check"]["lastCheckAt"] is None
    assert older["check"]["status"] == "conferida"


async def test_frase_is_the_frozen_number_of_the_stretch_the_finding_points_at(
    db_session: AsyncSession,
) -> None:
    """The block's number is the packet's own, never the number the analyst gave.

    A missing element placed *after* frase 2 resolves to the third stretch (ADR 0007), so its
    `chunk` is 2 while the stretch it points at is frase 3. The block ships beside
    `segments[]` and has to agree with it, so it reads the position and not the chunk.

    The number is read back out of the packet's own `segments[]` as well as against the
    literal, because the two are enumerated in two places and only their agreement is the
    promise the block makes: a block whose number its own list does not carry addresses
    nothing.

    A finding pointing at no stretch at all has no number to give, and it carries a `chunk`
    all the same — a missing element placed after the last frase names that frase and resolves
    to nothing (ADR 0007). So `frase` is absent rather than null, and an implementation reading
    the chunk when the position is missing is exactly what that case catches.
    """
    session = await ready_session(db_session, project_id="time-de-rute", tell=_three_stretches_told)
    told = await final_segments(db_session, session.id)
    third = told[2]
    await _read_again(
        db_session,
        session,
        (
            Finding(
                kind=FindingKind.MISSING,
                note="nao disseram que voltaram para Juda",
                segment_id=third.id,
                chunk=2,
            ),
            Finding(
                kind=FindingKind.MISSING,
                note="falta o que veio depois de tudo o que contaram",
                segment_id=None,
                chunk=3,
            ),
        ),
    )

    packet = await _live_view(db_session, session)

    on_the_stretch, nowhere = packet["check"]["findings"]
    assert on_the_stretch["frase"] == 3, "a frase é a posição congelada, e o chunk dela discorda"
    assert on_the_stretch["frase"] == next(
        stretch["frase"]
        for stretch in packet["back_translation"]["segments"]
        if stretch["segment_id"] == third.id
    ), "o bloco e a lista que viaja ao lado dele contam a mesma frase, ou o bloco não promete nada"
    assert on_the_stretch["idx"] == third.id
    assert on_the_stretch["clipKey"] == REHEARSAL
    assert "frase" not in nowhere, "o chunk que a analista deu não vira frase de trecho nenhum"
    assert nowhere["idx"] is None
    assert nowhere["clipKey"] is None


async def test_a_finding_on_a_divided_stretch_names_no_frase(db_session: AsyncSession) -> None:
    """A stretch the team cut in two is in no reading, so a finding on it has no number.

    The cut renumbers the reading and moves neither standing finding (ADR 0018): the two go on
    naming the stretch the team has to record again, which by then sits in `divided_segments[]`
    rather than in `segments[]`. The block is a view of that list, so it names the finding's
    own `segment_id` and stops there — a consumer resolves the recording through the list that
    carries the stretch.

    The halves are told back before the force because a wordless stretch is `untold_stretch`,
    which is missing material and no code forces it.
    """
    session = await ready_session(
        db_session, project_id="time-que-dividiu", tell=_three_stretches_told
    )
    told = await final_segments(db_session, session.id)
    third = told[2]
    await _read_again(
        db_session,
        session,
        (
            Finding(
                kind=FindingKind.ADDITION,
                note="disseram que elas choraram alto",
                segment_id=third.id,
                chunk=3,
            ),
        ),
    )
    halves = await divide_segment(db_session, session, third, at_ms=50000)
    for half, text in zip(
        halves, ("a primeira metade contada", "a segunda metade contada"), strict=True
    ):
        await capture_segment(
            db_session,
            session,
            take_id=half.take_id,
            starts_ms=half.starts_ms,
            ends_ms=half.ends_ms,
            bridge_take_id="retro-dividido",
            transcript=text,
            replaces=half,
        )

    release = await approve_release(
        db_session, await get_session(db_session, session.id), forced_by="a-facilitadora"
    )

    (entry,) = release.packet["check"]["findings"]
    assert entry["idx"] == third.id
    assert "frase" not in entry
    assert entry["clipKey"] is None
    listed = release.packet["back_translation"]
    assert third.id not in {stretch["segment_id"] for stretch in listed["segments"]}
    assert third.id in {stretch["segment_id"] for stretch in listed["divided_segments"]}


async def test_the_teams_approval_after_a_force_returns_the_stored_block(
    client, db_session: AsyncSession, room_app
) -> None:
    """The early return writes nothing, so what comes back is the block the force stamped.

    An unchanged packet answers with the release that already exists (ADR 0014), and that
    release was a person's act. A team approval that re-derived the block here would quietly
    turn `forcada` into the team's own word for a draft the team never approved.
    """
    project, credential = await a_claimed_device(db_session)
    session = await a_p02_telling_with_the_swapped_cause(db_session, project)
    desk, _facilitator = await at_the_desk(db_session, room_app, project)

    forced = await client.post(desk_release(session.id), headers=desk, json={"force": True})
    again = await client.post(team_release(session.id), headers=team_headers(credential))
    read = await client.get(desk_release_at(session.id, 1), headers=desk)

    assert forced.status_code == 200, forced.text
    assert again.status_code == 200, again.text
    assert again.json()["version"] == 1
    assert read.status_code == 200, read.text
    assert read.json()["check"]["status"] == "forcada"
    assert read.json()["check"]["forced"] is True


async def test_the_stored_block_names_its_own_version_and_the_live_one_none(
    client, db_session: AsyncSession, room_app
) -> None:
    """Each stored block names the number its row was given; the live one names none.

    `version` is null on the live read by rule and not by reading the packet's own `version`
    key — which on a session whose content *is* the latest release says 2 (ADR 0020). The two
    answer different questions: the packet's says which approved draft this content is, and
    the block's says which release this block was stamped from.
    """
    project, credential = await a_claimed_device(db_session)
    session = await ready_session(db_session, project_id=project.id)
    desk, _facilitator = await at_the_desk(db_session, room_app, project)

    first = await client.post(team_release(session.id), headers=team_headers(credential))
    await one_stretch(db_session, session, text="Rute espigou no campo de Boaz")
    second = await client.post(team_release(session.id), headers=team_headers(credential))
    v1 = await client.get(desk_release_at(session.id, 1), headers=desk)
    v2 = await client.get(desk_release_at(session.id, 2), headers=desk)
    live = await client.get(desk_release(session.id), headers=desk)

    assert first.json()["version"] == 1, first.text
    assert second.json()["version"] == 2, second.text
    assert v1.json()["check"]["version"] == 1
    assert v2.json()["check"]["version"] == 2
    assert live.status_code == 200, live.text
    assert live.json()["version"] == 2, "o conteúdo vivo é o da versão 2, e o pacote diz isso"
    assert live.json()["check"]["version"] is None
    assert live.json()["check"]["forced"] is False
