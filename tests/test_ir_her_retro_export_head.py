"""ENG-1801 — the head of the retroverificação file carries her fields in her order.

Her `retroExport.ts` at the pin (18fa7c4), read off the rows the room wrote, through its own
write paths.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRGrain, IRSession
from app.models.internalization_room import PlayedTake
from app.services.internalization_room.approved_draft import approved_draft
from app.services.internalization_room.back_translation import (
    BackTranslationState,
    CheckRound,
    Finding,
    FindingKind,
    Nuance,
)
from app.services.internalization_room.retro_export import (
    APPROVED_BEFORE_THE_RECORD,
    NOT_APPROVED,
)
from app.services.internalization_room.segments import (
    capture_segment,
    divide_segment,
    final_segments,
    retired_segments,
)
from app.services.internalization_room.sessions import (
    create_session,
    report_playback,
    switch_the_grain,
)
from tests.baker import make_app, make_role
from tests.release_harness import (
    APP_KEY,
    CLIP_MS,
    PREFIX,
    P,
    a_claimed_device,
    a_p02_telling_with_the_swapped_cause,
    a_rehearsal_only_half_heard,
    at_the_desk,
    checked_heard_and_approved,
    checked_telling_back,
    desk_release,
    ensaio_take,
    one_stretch,
    ready_session,
    rehearsed_session,
    team_headers,
    team_release,
    the_one_part_of,
    the_part_recorded_again,
)
from tests.release_harness import (
    exported_file as _exported,
)
from tests.room_harness import (
    PART_MS,
    record_the_part_again,
    rehearsed_in_parts,
    room_client,
    the_bucket_is_in_memory,
)

WORDS = "Noemi voltou com Rute"
TOLD_AGAIN = "Noemi voltou com Rute, contado outra vez"


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    the_bucket_is_in_memory(monkeypatch)
    async with room_client(db_session, monkeypatch) as room:
        yield room


@pytest.fixture()
async def room_app(db_session: AsyncSession):
    app = await make_app(db_session, app_key=APP_KEY, name="Internalization Room")
    await make_role(db_session, app.id, role_key="facilitator", label="Facilitator", is_system=True)
    return app


async def _approved(client, db: AsyncSession, tell=None) -> tuple[IRSession, dict[str, str]]:
    project, credential = await a_claimed_device(db)
    session = await ready_session(db, project_id=project.id, tell=tell)
    headers = team_headers(credential)
    await checked_heard_and_approved(client, db, session.id, headers=headers)
    return session, headers


async def test_an_approved_passage_opens_with_her_keys_in_her_order(client, db_session) -> None:
    session, _ = await _approved(client, db_session)
    (stretch,) = await final_segments(db_session, session.id)
    pericope, stretch_id = session.pericope, stretch.id

    file = await _exported(db_session, session.id)

    assert list(file) == [
        "releaseId", "pericopeId", "version", "finalized", "approval", "frases", "history",
        "checks", "heardByClip", "supersededTakes", "exportedAt",
    ]  # fmt: skip
    assert file["releaseId"].endswith("-v1")
    assert (file["pericopeId"], file["version"], file["finalized"]) == (pericope, 1, True)
    assert abs(datetime.now(UTC) - datetime.fromisoformat(file["exportedAt"])) < timedelta(
        minutes=1
    )
    approval = file["approval"]
    assert (approval["v"], approval["forced"], approval["conferida"]) == (1, False, True)
    assert approval["heardComplete"] is True
    assert approval["frases"] == [
        {"n": 1, "idx": stretch_id, "clipKey": "whole", "coversFrom": 0, "coversTo": CLIP_MS / 1000}
    ]


async def test_an_unapproved_passage_has_no_approval_and_says_so(db_session) -> None:
    project, _ = await a_claimed_device(db_session)
    session = await ready_session(db_session, project_id=project.id)

    file = await _exported(db_session, session.id)

    assert list(file) == [
        "releaseId", "pericopeId", "version", "finalized", "note", "approval", "frases", "history",
        "checks", "heardByClip", "supersededTakes", "exportedAt",
    ]  # fmt: skip
    assert [(one["n"], one["transcript"]) for one in file["frases"]] == [(1, WORDS)]
    (live,) = file["frases"]
    assert (live["clipKey"], live["coversFrom"], live["coversTo"]) == ("whole", 0, CLIP_MS / 1000)
    assert (file["finalized"], file["approval"], file["version"]) == (False, None, 1)
    assert file["note"] == NOT_APPROVED


async def test_a_forced_approval_keeps_its_open_findings_by_address_and_never_the_note(
    client, db_session, room_app
) -> None:
    project, _ = await a_claimed_device(db_session)
    session = await a_p02_telling_with_the_swapped_cause(db_session, project)
    desk, _ = await at_the_desk(db_session, room_app, project)
    forced = await client.post(desk_release(session.id), headers=desk, json={"force": True})
    assert forced.status_code == 200, forced.text
    (stretch,) = await final_segments(db_session, session.id)
    stretch_id = stretch.id

    file = await _exported(db_session, session.id)
    approval = file["approval"]

    assert "note" not in file
    assert (approval["forced"], approval["conferida"]) == (True, False)
    assert approval["findings"] == [
        {"kind": "addition", "frase": 1, "idx": stretch_id, "clipKey": "whole"}
    ]


async def test_a_draft_reopened_by_a_new_take_is_the_next_version(client, db_session) -> None:
    session, _ = await _approved(client, db_session)
    await the_part_recorded_again(db_session, session)

    file = await _exported(db_session, session.id)

    assert (file["version"], file["finalized"], file["approval"]) == (2, False, None)
    assert file["note"] == NOT_APPROVED


async def test_a_version_approved_before_the_record_has_no_approval_and_says_why(
    client, db_session
) -> None:
    session, _ = await _approved(client, db_session)
    release = await approved_draft(db_session, await db_session.get(IRSession, session.id))
    release.packet = {key: value for key, value in release.packet.items() if key != "check"}
    await db_session.commit()

    file = await _exported(db_session, session.id)

    assert (file["finalized"], file["version"], file["approval"]) == (True, 1, None)
    assert file["note"] == APPROVED_BEFORE_THE_RECORD


async def test_a_packet_minted_before_nuances_and_keys_were_stored_still_exports(
    client, db_session
) -> None:
    session, _ = await _approved(client, db_session)
    release = await approved_draft(db_session, await db_session.get(IRSession, session.id))
    packet = deepcopy(release.packet)
    del packet["check"]["nuances"]
    for one in packet["audio"]["rehearsal_takes"]:
        del one["key"], one["duration_ms"]
    for one in packet["back_translation"]["segments"]:
        del one["scene"]
    del packet["release_id"]
    release.packet = packet
    release.version = 3
    approved_at = release.approved_at.isoformat()
    await db_session.commit()

    file = await _exported(db_session, session.id)

    approval = file["approval"]
    assert (file["version"], approval["v"], approval["at"]) == (3, 3, approved_at)
    assert "nuances" not in approval
    assert [(one["key"], one["durationMs"]) for one in approval["takes"]] == [("whole", None)]
    assert [one["clipKey"] for one in approval["frases"]] == ["whole"]


async def test_the_approval_pins_its_takes_and_its_nuances_with_what_the_voice_said(
    client, db_session
) -> None:
    project, credential = await a_claimed_device(db_session)

    now = datetime.now(UTC)

    async def _told(db, session) -> BackTranslationState:
        told = await one_stretch(db, session)
        part = await the_one_part_of(db, session)
        said = Nuance(
            note="n", chunk=1, segment_id=told.id, quote="Rute", story="s", take_id=part.id,
            starts_ms=0, ends_ms=CLIP_MS, voiced="now",
        )  # fmt: skip
        unsaid = said.model_copy(update={"quote": "Juda", "voiced": None})
        round_ = CheckRound(
            at=now, spoken="ok", outcome="pass", conferida=True, nuances=[said], heard_at=now
        )
        return BackTranslationState(
            scope=session.pericope, checked=True, checked_at=now, analysed_segment_ids=[told.id],
            nuances=[said, unsaid], checks=[round_],
        )  # fmt: skip

    session = await ready_session(db_session, project_id=project.id, tell=_told)
    (await the_one_part_of(db_session, session)).duration_ms = CLIP_MS
    await db_session.commit()
    answered = await client.post(team_release(session.id), headers=team_headers(credential))
    assert answered.status_code == 200, answered.text
    (stretch,) = await final_segments(db_session, session.id)
    part = await the_one_part_of(db_session, session)
    wanted = (stretch.id, part.id, part.sha256, part.size_bytes, CLIP_MS)

    approval = (await _exported(db_session, session.id))["approval"]

    assert approval["lastCheckAt"] == now.isoformat()
    assert [one.get("voiced") for one in approval["nuances"]] == [
        "now",
        None,
    ]
    (take,) = approval["takes"]
    assert (take["key"], take["takeId"], take["sha256"], take["bytes"], take["durationMs"]) == (
        "whole", *wanted[1:]
    )  # fmt: skip
    assert approval["nuances"][0]["idx"] == wanted[0]


async def test_a_forced_approval_of_a_clean_check_with_a_part_unheard_says_so(
    client, db_session, room_app
) -> None:
    project, _ = await a_claimed_device(db_session)
    session = await a_rehearsal_only_half_heard(db_session, project)
    desk, _ = await at_the_desk(db_session, room_app, project)
    forced = await client.post(desk_release(session.id), headers=desk, json={"force": True})
    assert forced.status_code == 200, forced.text

    approval = (await _exported(db_session, session.id))["approval"]

    assert (approval["forced"], approval["conferida"], approval["heardComplete"]) == (
        True,
        True,
        False,
    )


async def test_a_packet_that_froze_no_frase_numbers_lists_no_frase_in_the_approval(
    client, db_session
) -> None:
    session, _ = await _approved(client, db_session)
    release = await approved_draft(db_session, await db_session.get(IRSession, session.id))
    packet = deepcopy(release.packet)
    for one in packet["back_translation"]["segments"]:
        del one["frase"]
    release.packet = packet
    await db_session.commit()

    assert (await _exported(db_session, session.id))["approval"]["frases"] == []


async def _two_stretches(db, session) -> BackTranslationState:
    part = await the_one_part_of(db, session)
    told = [
        await capture_segment(
            db,
            session,
            take_id=part.id,
            starts_ms=start,
            ends_ms=end,
            bridge_take_id="retro",
            transcript=words,
        )
        for start, end, words in ((0, 30000, "um"), (30000, CLIP_MS, "dois"))
    ]
    return BackTranslationState(
        scope=session.pericope, checked=True, analysed_segment_ids=[one.id for one in told]
    )


async def _restarted(client, session, headers) -> None:
    restarted = await client.post(
        f"{PREFIX}/sessions/{session.id}/back-translation/restart", headers=headers
    )
    assert restarted.status_code == 200, restarted.text


async def test_the_frases_carry_her_places_and_the_words_as_they_stand(client, db_session) -> None:
    session, _ = await _approved(client, db_session)
    (stretch,) = await final_segments(db_session, session.id)
    stretch_id, stamped = stretch.id, stretch.created_at.isoformat()

    (frase,) = (await _exported(db_session, session.id))["frases"]

    assert list(frase) == [
        "n", "idx", "clipKey", "coversFrom", "coversTo",
        "transcript", "pass", "recordedAt", "stale",
    ]  # fmt: skip
    assert (frase["n"], frase["idx"], frase["clipKey"], frase["coversTo"]) == (
        1, stretch_id, "whole", CLIP_MS / 1000,
    )  # fmt: skip
    assert (frase["transcript"], frase["pass"], frase["stale"]) == (WORDS, 1, False)
    assert (frase["recordedAt"], frase["coversFrom"]) == (stamped, 0)


async def test_dividing_an_approved_stretch_leaves_its_frase_with_its_own_words(
    client, db_session
) -> None:
    session, _ = await _approved(client, db_session, tell=_two_stretches)
    first, *_ = await final_segments(db_session, session.id)
    await divide_segment(db_session, session, first, at_ms=15000)

    frases = (await _exported(db_session, session.id))["frases"]

    assert [(one["n"], one["transcript"], one["stale"]) for one in frases] == [
        (1, "um", False),
        (2, "dois", False),
    ]


async def _in_pieces(db, session) -> BackTranslationState:
    part = await the_one_part_of(db, session)
    first = await capture_segment(
        db, session, take_id=part.id, starts_ms=0, ends_ms=30000,
        bridge_take_id="retro", transcript="um",
    )  # fmt: skip
    second = await capture_segment(
        db, session, take_id=part.id, starts_ms=30000, ends_ms=CLIP_MS,
        bridge_take_id="retro", transcript="dois",
    )  # fmt: skip
    told = []
    pieces = await divide_segment(db, session, first, at_ms=15000)
    for piece, words in zip(pieces, ("meio", "fim"), strict=True):
        told.append(
            await capture_segment(
                db,
                session,
                take_id=part.id,
                starts_ms=piece.starts_ms,
                ends_ms=piece.ends_ms,
                bridge_take_id="retro",
                transcript=words,
                replaces=piece,
            )
        )
    return BackTranslationState(
        scope=session.pericope,
        checked=True,
        analysed_segment_ids=[*(one.id for one in told), second.id],
    )


async def test_an_approved_frase_on_a_piece_of_a_divided_stretch_keeps_the_pieces_words(
    client, db_session
) -> None:
    session, _ = await _approved(client, db_session, tell=_in_pieces)

    frases = (await _exported(db_session, session.id))["frases"]

    assert [(one["n"], one["transcript"], one["stale"]) for one in frases] == [
        (1, "meio", False),
        (2, "fim", False),
        (3, "dois", False),
    ]
    assert not any("supersedes" in one for one in frases)
    assert [one["coversFrom"] for one in frases] == [0, 15, 30]


async def _corrected(db, session) -> BackTranslationState:
    await checked_telling_back(db, session)
    (first,) = await final_segments(db, session.id)
    again = await capture_segment(
        db, session, take_id=first.take_id, starts_ms=first.starts_ms, ends_ms=first.ends_ms,
        bridge_take_id="retro-de-novo", transcript=TOLD_AGAIN, pass_number=2, replaces=first,
    )  # fmt: skip
    return BackTranslationState(
        scope=session.pericope, checked=True, analysed_segment_ids=[again.id]
    )


async def test_a_frase_approved_after_a_correction_names_the_telling_it_replaced(
    client, db_session
) -> None:
    session, _ = await _approved(client, db_session, tell=_corrected)
    (old,) = await retired_segments(db_session, session.id)
    old_id = old.id

    (frase,) = (await _exported(db_session, session.id))["frases"]

    assert (frase["transcript"], frase["pass"], frase["supersedes"]) == (TOLD_AGAIN, 2, old_id)


async def test_an_approved_frase_whose_stretch_no_longer_stands_is_empty_and_stale(
    client, db_session
) -> None:
    session, headers = await _approved(client, db_session)
    (first,) = await final_segments(db_session, session.id)
    first_id = first.id
    await _restarted(client, session, headers)

    (frase,) = (await _exported(db_session, session.id))["frases"]

    assert (frase["n"], frase["idx"], frase["transcript"], frase["stale"]) == (
        1, first_id, "", True,
    )  # fmt: skip


async def test_a_draft_not_approved_lists_no_frase_for_a_piece_not_yet_told(db_session) -> None:
    project, _ = await a_claimed_device(db_session)
    session = await ready_session(db_session, project_id=project.id, tell=_two_stretches)
    first, *_ = await final_segments(db_session, session.id)
    await divide_segment(db_session, session, first, at_ms=15000)

    (frase,) = (await _exported(db_session, session.id))["frases"]

    assert (frase["n"], frase["transcript"], frase["coversFrom"], frase["coversTo"]) == (
        1, "dois", 30, CLIP_MS / 1000,
    )  # fmt: skip


async def test_restarting_over_an_approved_draft_keeps_the_approval_and_empties_the_words(
    client, db_session
) -> None:
    session, headers = await _approved(client, db_session)
    (first,) = await final_segments(db_session, session.id)
    first_id, take_id = first.id, first.take_id
    await _restarted(client, session, headers)

    file = await _exported(db_session, session.id)

    assert (file["finalized"], file["approval"]["v"], "note" in file) == (True, 1, False)
    (frase,) = file["frases"]
    assert (frase["n"], frase["idx"], frase["transcript"], frase["stale"]) == (
        1,
        first_id,
        "",
        True,
    )

    await capture_segment(
        db_session, session, take_id=take_id, starts_ms=0, ends_ms=CLIP_MS,
        bridge_take_id="retro-depois", transcript=TOLD_AGAIN, pass_number=2,
    )  # fmt: skip
    (told,) = (await _exported(db_session, session.id))["frases"]
    assert (told["n"], told["idx"], told["transcript"], told["pass"], told["stale"]) == (
        1, first_id, TOLD_AGAIN, 2, False,
    )  # fmt: skip


async def test_a_correction_over_an_approved_draft_leaves_it_approved_and_shows_the_new_words(
    client, db_session
) -> None:
    session, _ = await _approved(client, db_session)
    (first,) = await final_segments(db_session, session.id)
    await capture_segment(
        db_session,
        session,
        take_id=first.take_id,
        starts_ms=first.starts_ms,
        ends_ms=first.ends_ms,
        bridge_take_id="retro-de-novo",
        transcript=TOLD_AGAIN,
        replaces=first,
    )
    first_id = first.id

    file = await _exported(db_session, session.id)

    assert (file["approval"]["v"], file["finalized"], file["version"]) == (1, True, 1)
    (frase,) = file["frases"]
    assert (frase["idx"], frase["transcript"], frase["supersedes"], frase["stale"]) == (
        first_id, TOLD_AGAIN, first_id, False,
    )  # fmt: skip


async def test_an_approved_frase_finds_its_words_at_its_position_in_its_part(
    client, db_session
) -> None:
    session, headers = await _approved(client, db_session, tell=_two_stretches)
    part = await the_one_part_of(db_session, session)
    take_id = part.id
    await _restarted(client, session, headers)
    await capture_segment(
        db_session, session, take_id=take_id, starts_ms=0, ends_ms=30000,
        bridge_take_id="retro-depois", transcript=TOLD_AGAIN,
    )  # fmt: skip

    frases = (await _exported(db_session, session.id))["frases"]

    assert [(one["n"], one["transcript"], one["stale"]) for one in frases] == [
        (1, TOLD_AGAIN, False),
        (2, "", True),
    ]


async def test_an_approved_frase_of_a_later_part_is_told_again_in_its_own_part(
    client, db_session
) -> None:
    project, credential = await a_claimed_device(db_session)
    session, (_first, second) = await rehearsed_in_parts(db_session, 2, project_id=project.id)
    headers = team_headers(credential)
    await checked_heard_and_approved(client, db_session, session.id, headers=headers)
    second_id = second.id
    await _restarted(client, session, headers)
    await capture_segment(
        db_session, session, take_id=second_id, starts_ms=0, ends_ms=61000,
        bridge_take_id="retro-depois", transcript=TOLD_AGAIN,
    )  # fmt: skip

    frases = (await _exported(db_session, session.id))["frases"]

    assert [(one["clipKey"], one["transcript"], one["stale"]) for one in frases] == [
        ("S1", "", True),
        ("S2", TOLD_AGAIN, False),
    ]


async def test_a_restarted_frase_told_again_and_then_divided_keeps_its_own_words(
    client, db_session
) -> None:
    session, headers = await _approved(client, db_session, tell=_two_stretches)
    part = await the_one_part_of(db_session, session)
    take_id = part.id
    await _restarted(client, session, headers)
    retold = await capture_segment(
        db_session, session, take_id=take_id, starts_ms=0, ends_ms=30000,
        bridge_take_id="retro-depois", transcript=TOLD_AGAIN,
    )  # fmt: skip
    await divide_segment(db_session, session, retold, at_ms=15000)

    frases = (await _exported(db_session, session.id))["frases"]

    assert [(one["transcript"], one["stale"]) for one in frases] == [
        (TOLD_AGAIN, False),
        ("", True),
    ]


async def test_a_corrected_piece_still_answers_for_the_frase_approved_on_it(
    client, db_session
) -> None:
    session, _ = await _approved(client, db_session, tell=_in_pieces)
    told_piece, *_ = await final_segments(db_session, session.id)
    told_id = told_piece.id
    await capture_segment(
        db_session, session, take_id=told_piece.take_id, starts_ms=told_piece.starts_ms,
        ends_ms=told_piece.ends_ms, bridge_take_id="retro-novo", transcript="corrigido",
        replaces=told_piece,
    )  # fmt: skip

    frases = (await _exported(db_session, session.id))["frases"]

    assert [(one["transcript"], one.get("supersedes")) for one in frases][:2] == [
        ("corrigido", told_id),
        ("fim", None),
    ]


async def test_a_restarted_frase_is_not_taken_by_the_first_piece_of_the_stretch_divided_after(
    client, db_session
) -> None:
    session, headers = await _approved(client, db_session, tell=_two_stretches)
    part = await the_one_part_of(db_session, session)
    take_id = part.id
    await _restarted(client, session, headers)
    for start, end, words in ((0, 30000, "novo um"), (30000, CLIP_MS, "novo dois")):
        told = await capture_segment(
            db_session, session, take_id=take_id, starts_ms=start, ends_ms=end,
            bridge_take_id="retro-depois", transcript=words,
        )  # fmt: skip
    await divide_segment(db_session, session, told, at_ms=45000)

    frases = (await _exported(db_session, session.id))["frases"]

    assert [(one["transcript"], one["stale"]) for one in frases] == [
        ("novo um", False),
        ("novo dois", False),
    ]


async def test_a_part_recorded_again_and_not_told_again_keeps_its_frase_listed_as_stale(
    db_session,
) -> None:
    project, _ = await a_claimed_device(db_session)
    session = await ready_session(db_session, project_id=project.id)
    (waiting,) = await final_segments(db_session, session.id)
    waiting_id = waiting.id
    await the_part_recorded_again(db_session, session)

    (frase,) = (await _exported(db_session, session.id))["frases"]

    assert (frase["n"], frase["idx"], frase["transcript"], frase["stale"]) == (
        1, waiting_id, WORDS, True,
    )  # fmt: skip
    assert (frase["clipKey"], frase["coversFrom"], frase["coversTo"]) == (
        "whole", 0, CLIP_MS / 1000,
    )  # fmt: skip


async def test_stale_frases_follow_the_told_ones_without_moving_their_numbers(db_session) -> None:
    project, _ = await a_claimed_device(db_session)
    session, (first, _second) = await rehearsed_in_parts(db_session, 2, project_id=project.id)
    await record_the_part_again(db_session, session, first, sha256="d" * 64)

    frases = (await _exported(db_session, session.id))["frases"]

    assert [(one["n"], one["clipKey"], one["stale"]) for one in frases] == [
        (1, "S2", False),
        (2, "S1", True),
    ]


async def test_history_keeps_what_a_restart_abandoned_and_what_a_correction_replaced(
    client, db_session
) -> None:
    session, headers = await _approved(client, db_session)
    (first,) = await final_segments(db_session, session.id)
    first.created_at -= timedelta(minutes=1)
    await db_session.commit()
    first_id, take_id, stamped = first.id, first.take_id, first.created_at.isoformat()
    await _restarted(client, session, headers)
    (abandoned,) = (await _exported(db_session, session.id))["history"]
    assert list(abandoned) == [
        "idx", "clipKey", "coversFrom", "coversTo", "transcript", "pass", "recordedAt",
        "superseded",
    ]  # fmt: skip
    assert (abandoned["idx"], abandoned["transcript"], abandoned["superseded"]) == (
        first_id, WORDS, False,
    )  # fmt: skip
    assert (abandoned["clipKey"], abandoned["coversFrom"], abandoned["coversTo"]) == (
        "whole", 0, CLIP_MS / 1000,
    )  # fmt: skip
    assert abandoned["recordedAt"] == stamped
    told = await capture_segment(
        db_session, session, take_id=take_id, starts_ms=0, ends_ms=CLIP_MS,
        bridge_take_id="retro-depois", transcript=TOLD_AGAIN, pass_number=2,
    )  # fmt: skip
    told_id = told.id
    await capture_segment(
        db_session, session, take_id=take_id, starts_ms=0, ends_ms=CLIP_MS,
        bridge_take_id="retro-corrigido", transcript="corrigido", pass_number=2, replaces=told,
    )  # fmt: skip

    history = (await _exported(db_session, session.id))["history"]

    assert [(one["transcript"], one["superseded"], one["pass"]) for one in history] == [
        (WORDS, False, 1),
        (TOLD_AGAIN, True, 2),
        ("corrigido", False, 2),
    ]
    assert history[2]["supersedes"] == told_id
    assert "supersedes" not in history[1]


async def test_stretches_written_in_one_transaction_are_listed_in_their_reading_order(
    db_session,
) -> None:
    project, _ = await a_claimed_device(db_session)
    session, part = await rehearsed_session(db_session, project_id=project.id)
    said = [f"parte {n}" for n in range(5)]
    for n, words in enumerate(said):
        await capture_segment(
            db_session, session, take_id=part.id, starts_ms=n * 10000, ends_ms=(n + 1) * 10000,
            bridge_take_id="retro", transcript=words, commit=False,
        )  # fmt: skip
    await db_session.commit()

    file = await _exported(db_session, session.id)

    assert [one["transcript"] for one in file["history"]] == said


async def test_history_lists_told_stretches_only_and_a_piece_enters_once_told(
    client, db_session
) -> None:
    session, _ = await _approved(client, db_session, tell=_two_stretches)
    first, *_ = await final_segments(db_session, session.id)
    first_id = first.id
    piece, other = await divide_segment(db_session, session, first, at_ms=15000)
    piece_id, other_id = piece.id, other.id
    assert piece_id not in {
        one["idx"] for one in (await _exported(db_session, session.id))["history"]
    }

    told = await capture_segment(
        db_session, session, take_id=piece.take_id, starts_ms=piece.starts_ms,
        ends_ms=piece.ends_ms, bridge_take_id="retro-peca", transcript="meio", replaces=piece,
    )  # fmt: skip
    told_id = told.id

    history = (await _exported(db_session, session.id))["history"]
    seen = {one["idx"] for one in history}

    assert first_id in seen and told_id in seen
    assert not {piece_id, other_id} & seen
    assert "supersedes" not in next(one for one in history if one["idx"] == told_id)


async def _checked_three_times(db, session) -> BackTranslationState:
    told = await one_stretch(db, session)
    part = await the_one_part_of(db, session)
    first_at = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
    nuance = Nuance(
        note="detalhe", chunk=1, segment_id=told.id, quote="Rute", story="a história diz Noemi",
        take_id=part.id, starts_ms=0, ends_ms=CLIP_MS, voiced="now",
    )  # fmt: skip
    found = Finding(kind=FindingKind.ADDITION, note="NOTA-1", segment_id=told.id, chunk=1)
    missing_at_the_end = Finding(kind=FindingKind.MISSING, note="FALTOU-NO-FIM", chunk=2)
    rounds = [
        CheckRound(
            at=first_at, findings=[found, missing_at_the_end], spoken="vocês acrescentaram",
            outcome="corrected", conferida=False,
        ),
        CheckRound(
            at=first_at + timedelta(hours=1), spoken="só um detalhe", outcome="pass",
            conferida=True, nuances=[nuance],
        ),
        CheckRound(
            at=first_at + timedelta(hours=2), spoken="vocês contaram bem", outcome="pass",
            conferida=True,
        ),
    ]  # fmt: skip
    return BackTranslationState(
        scope=session.pericope, checked=True, analysed_segment_ids=[told.id], checks=rounds
    )


async def test_every_check_is_listed_with_its_findings_notes_and_the_voice(db_session) -> None:
    project, _ = await a_claimed_device(db_session)
    session = await ready_session(db_session, project_id=project.id, tell=_checked_three_times)
    (stretch,) = await final_segments(db_session, session.id)
    stretch_id = stretch.id

    checks = (await _exported(db_session, session.id))["checks"]

    first, second, third = checks
    assert list(first) == ["at", "findings", "spoken", "outcome", "conferida"]
    assert first["at"] == "2026-10-01T12:00:00+00:00"
    assert (first["spoken"], first["outcome"], first["conferida"]) == (
        "vocês acrescentaram", "corrected", False,
    )  # fmt: skip
    assert first["findings"] == [
        {"kind": "addition", "note": "NOTA-1", "frase": 1, "idx": stretch_id, "clipKey": "whole"},
        {"kind": "missing", "note": "FALTOU-NO-FIM"},
    ]
    (nuance,) = second["findings"]
    assert list(nuance) == ["kind", "note", "frase", "idx", "clipKey", "quote", "story", "voiced"]
    assert (nuance["kind"], nuance["note"], nuance["quote"], nuance["voiced"]) == (
        "nuance", "detalhe", "Rute", "now",
    )  # fmt: skip
    assert nuance["story"] == "a história diz Noemi"
    assert (third["findings"], third["conferida"]) == ([], True)


async def test_heard_by_clip_is_the_share_of_each_part_the_team_heard(db_session) -> None:
    project, _ = await a_claimed_device(db_session)
    half = await a_rehearsal_only_half_heard(db_session, project)
    session, (first, second) = await rehearsed_in_parts(db_session, 2, project_id=project.id)
    lone, lone_part = await rehearsed_session(db_session, project_id=project.id)
    half_id, session_id, lone_id = half.id, session.id, lone.id
    second.duration_ms = 40000
    await db_session.commit()
    played = {
        first.id: [(0, 30000), (30200, PART_MS)],
        second.id: [(0, 10000), (10200, 20000), (30000, 90000)],
    }
    await report_playback(
        db_session,
        session,
        BackTranslationState(scope=session.pericope),
        played_by_take=[
            PlayedTake(take_id=take_id, played_ranges=spans, clip_duration_ms=PART_MS)
            for take_id, spans in played.items()
        ],
        played_ranges=[[0, PART_MS]],
        clip_duration_ms=PART_MS,
    )
    await report_playback(
        db_session,
        lone,
        BackTranslationState(scope=lone.pericope),
        played_by_take=[
            PlayedTake(take_id=lone_part.id, played_ranges=[(0, 1000)], clip_duration_ms=0)
        ],
        played_ranges=[[0, 1000]],
        clip_duration_ms=0,
    )

    assert (await _exported(db_session, half_id))["heardByClip"] == {
        "whole": pytest.approx(20 / 61)
    }
    assert (await _exported(db_session, session_id))["heardByClip"] == {
        "S1": pytest.approx(1.0),
        "S2": pytest.approx(0.75),
    }
    assert (await _exported(db_session, lone_id))["heardByClip"] == {"whole": 0}


async def test_a_replaced_take_is_listed_under_her_name_and_with_no_time_until_the_stamp_exists(
    client, db_session
) -> None:
    session, _ = await _approved(client, db_session)
    old = await the_one_part_of(db_session, session)
    old.duration_ms = 1234
    await db_session.commit()
    wanted = {
        "key": "whole", "takeId": old.id, "sha256": old.sha256, "durationMs": 1234,
        "bytes": old.size_bytes, "contentType": "audio/mp4",
        "recordedAt": old.recorded_at.isoformat(),
        "url": f"/api/internalization-room/facilitator/takes/{old.id}/audio",
    }  # fmt: skip
    old_id = old.id
    await the_part_recorded_again(db_session, session)

    file = await _exported(db_session, session.id)

    (take,) = file["supersededTakes"]
    assert file["version"] == 2
    wanted["filename"] = f"{file['releaseId']}-whole-substituida-{old_id}.m4a"
    assert file["releaseId"].endswith("-v2")
    assert take == wanted


async def test_a_declared_part_is_no_take_to_download(client, db_session) -> None:
    session, _ = await _approved(client, db_session)
    old = await the_one_part_of(db_session, session)
    old.storage_key = f"text-seam/{session.id}/S1"
    await db_session.commit()
    await the_part_recorded_again(db_session, session)

    assert (await _exported(db_session, session.id))["supersededTakes"] == []


async def test_a_check_of_an_approved_draft_numbers_its_findings_as_the_approval_did(
    client, db_session
) -> None:
    project, credential = await a_claimed_device(db_session)
    session = await ready_session(db_session, project_id=project.id, tell=_checked_three_times)
    approved = await client.post(team_release(session.id), headers=team_headers(credential))
    assert approved.status_code == 200, approved.text
    (only,) = await final_segments(db_session, session.id)
    await divide_segment(db_session, session, only, at_ms=15000)

    first, *_ = (await _exported(db_session, session.id))["checks"]

    assert first["findings"][0]["frase"] == 1


async def test_a_grain_switch_is_one_earlier_life_and_its_takes_are_listed_nowhere_else(
    db_session,
) -> None:
    project, _ = await a_claimed_device(db_session)
    session, _take = await rehearsed_session(db_session, project_id=project.id)
    moments = []

    async def _part(sha: str, hours: int) -> None:
        db_session.add(
            ensaio_take(
                session.id,
                pericope=session.pericope,
                scope="parte-1",
                ordinal=1,
                sha256=sha * 64,
                created_at=datetime.now(UTC) + timedelta(hours=hours),
                project_id=project.id,
            )
        )
        await db_session.commit()

    async def _switch(grain: IRGrain) -> None:
        await switch_the_grain(db_session, session, grain, reopens_the_approved_draft=False)
        await db_session.refresh(session)
        moments.append(session.grain_switched_at.isoformat())

    await _part("c", 1)
    await _switch(IRGrain.WHOLE)
    await _switch(IRGrain.SCENE)
    await _part("d", 2)
    await _switch(IRGrain.WHOLE)

    file = await _exported(db_session, session.id)

    assert list(file)[-2:] == ["previous", "exportedAt"]
    assert file["previous"] == [
        {"at": moments[0], "grain": "scene"},
        {"at": moments[2], "grain": "scene"},
    ]
    assert file["supersededTakes"] == []


async def test_choosing_a_grain_before_any_take_is_no_earlier_life(db_session) -> None:
    project, _ = await a_claimed_device(db_session)
    session = await create_session(db_session, pericope=P, project_id=project.id)
    await switch_the_grain(db_session, session, IRGrain.SCENE, reopens_the_approved_draft=False)

    assert "previous" not in await _exported(db_session, session.id)
