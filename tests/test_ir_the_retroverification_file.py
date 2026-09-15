"""ENG-892 — the facilitator and the consultant read everything the check learned.

The **Retroverification file** is the one artifact written for somebody allowed to see the
**Analyst**'s own words. Until now nothing carried a session's history out for a person: the
**Packet** was the only door and it is the team's working material, so the note travelled to
Refine and the consultant had no file at all.

What the route answers is the record of the check: every **Release** of the passage and who
forced one, the stretches standing now with the **Frase number** the latest version froze,
every earlier telling of each with its count, the tellings whose chain was abandoned, the
findings with their notes, the listening part by part, the **Hard stretch** marks placed on
the stretch standing now, and one link per **Take** including the ones a retelling replaced.

Served only to a facilitator of that team, on the release read's own scoping: a stranger is
told the session does not exist, because this file is the whole of what a team recorded.

Every case here reads the route's JSON and the rows the room wrote, through the room's own
write paths. Nothing reaches into the assembly.
"""

from __future__ import annotations

from hashlib import sha256

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSegment, IRSession, IRTake
from app.models.internalization_room import PlayedTake
from app.services.internalization_room.back_translation import BackTranslationState
from app.services.internalization_room.segments import (
    capture_segment,
    divide_segment,
    final_segments,
    retired_segments,
)
from app.services.internalization_room.sessions import (
    begin_back_translation_again,
    get_session,
    report_playback,
)
from app.services.internalization_room.takes import takes_of
from tests.baker import make_app, make_role
from tests.hard_stretch_harness import a_session as _a_session
from tests.hard_stretch_harness import marks as _marks
from tests.hard_stretch_harness import (
    rehearse as _rehearse,
)
from tests.hard_stretch_harness import (
    tell as _tell,
)
from tests.hard_stretch_harness import (
    told as _told,
)
from tests.release_harness import (
    APP_KEY,
    CLIP_MS,
    THE_FINDING,
    P,
    a_claimed_device,
    a_p02_telling_with_the_swapped_cause,
    at_the_desk,
    desk_release,
    desk_retro,
    never_analysed_telling_back,
    ready_session,
    releases_of,
    retro_take,
    team_headers,
    team_release,
)
from tests.room_harness import (
    PART_MS,
    rehearsed_in_parts,
    room_client,
    the_bucket_is_in_memory,
    the_room_speaks,
    the_transcriber_says,
)

#: The rehearsal these cases tell back over, as the room's own builders name it.
REHEARSAL = "ensaio-1"

#: The audio route the file points at, one link per take. A path and never a signed link: a
#: signed URL expires in minutes and this document outlives it.
AUDIO_ROUTE = "/api/internalization-room/facilitator/takes/{take_id}/audio"

#: The three sentences the file says to the consultant, in the language the room speaks to her.
NOT_APPROVED = "Este rascunho não foi aprovado: a numeração das frases é a da leitura de agora"
READING_MOVED = "A leitura mudou desde a versão 1: frases sem número não estavam nela"
NEVER_READ = "O analista nunca leu esta tradução: não houve conferência"

#: One rehearsal told back in two stretches, so an approval can freeze two numbers and a third
#: stretch told afterwards can have none.
TWO_STRETCHES = (
    ("Noemi ouviu que o Senhor tinha visitado o seu povo", 0, 30000),
    ("ela saiu do lugar onde estava com as duas noras", 30000, CLIP_MS),
)

FIRST_TELLING = "Noemi voltou para Juda"
SECOND_TELLING = "Noemi voltou para Juda com Rute"
THIRD_TELLING = "Noemi voltou para Juda com Rute, a moabita"


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    """The room's routes, with the transcriber, the bucket and the Speaker stood in for.

    The cases that tell a stretch again do it through the tablet's own route, which stores
    audio and speaks back; the cases that write rows directly need none of it and are not
    harmed by it.
    """
    said: list[str] = []
    the_transcriber_says(monkeypatch, said)
    the_bucket_is_in_memory(monkeypatch)
    the_room_speaks(monkeypatch)
    async with room_client(db_session, monkeypatch) as room:
        room.said = said  # type: ignore[attr-defined]
        yield room


@pytest.fixture()
async def room_app(db_session: AsyncSession):
    app = await make_app(db_session, app_key=APP_KEY, name="Internalization Room")
    await make_role(db_session, app.id, role_key="facilitator", label="Facilitator", is_system=True)
    return app


async def _a_retro_take(db: AsyncSession, session: IRSession, name: str) -> IRTake:
    """One recording of the team explaining a stretch, as a row of its own.

    A row rather than a bare id, because the file lists a link per take and a name nothing
    wrote would prove nothing about which recordings are reachable.
    """
    take = retro_take(session.id, sha256=sha256(name.encode()).hexdigest())
    db.add(take)
    await db.commit()
    return take


async def _read(db: AsyncSession, session: IRSession) -> BackTranslationState:
    """The state one whole clean reading of every stretch that counts leaves behind."""
    told = await final_segments(db, session.id)
    return BackTranslationState(
        scope=P, checked=True, analysed_segment_ids=[stretch.id for stretch in told]
    )


async def _told_once(db: AsyncSession, session: IRSession) -> BackTranslationState:
    """One stretch, explained on a retro take the file can point at."""
    retro = await _a_retro_take(db, session, "primeira")
    await capture_segment(
        db,
        session,
        take_id=REHEARSAL,
        starts_ms=0,
        ends_ms=CLIP_MS,
        bridge_take_id=retro.id,
        transcript=FIRST_TELLING,
    )
    return await _read(db, session)


async def _told_in_two_stretches(db: AsyncSession, session: IRSession) -> BackTranslationState:
    for text, starts_ms, ends_ms in TWO_STRETCHES:
        retro = await _a_retro_take(db, session, f"retro-{starts_ms}")
        await capture_segment(
            db,
            session,
            take_id=REHEARSAL,
            starts_ms=starts_ms,
            ends_ms=ends_ms,
            bridge_take_id=retro.id,
            transcript=text,
        )
    return await _read(db, session)


async def _tell_again(
    db: AsyncSession, session: IRSession, stretch: IRSegment, retro: IRTake, text: str
) -> None:
    """The team tells one stretch again over the same slice: a new row for the same position."""
    await capture_segment(
        db,
        session,
        take_id=stretch.take_id,
        starts_ms=stretch.starts_ms,
        ends_ms=stretch.ends_ms,
        bridge_take_id=retro.id,
        transcript=text,
        pass_number=stretch.pass_number,
        replaces=stretch,
    )


async def _the_file(client: httpx.AsyncClient, session_id: str, desk: dict[str, str]) -> dict:
    answered = await client.get(desk_retro(session_id), headers=desk)
    assert answered.status_code == 200, answered.text
    return answered.json()


async def _approved_by_the_team(
    client: httpx.AsyncClient, session_id: str, credential: str
) -> None:
    approved = await client.post(team_release(session_id), headers=team_headers(credential))
    assert approved.status_code == 200, approved.text


async def test_a_facilitator_reads_the_file_of_a_clean_session(
    client: httpx.AsyncClient, db_session: AsyncSession, room_app
) -> None:
    """The acceptance criterion's first half: the file of a session checked clean.

    Every part of it is read against the rows and against the stored packet — the numbers are
    the ones the **Version** froze and not a fresh enumeration, and every take of the session
    is reachable by a link of its own.
    """
    project, credential = await a_claimed_device(db_session)
    session = await ready_session(db_session, project_id=project.id, tell=_told_once)
    desk, _facilitator = await at_the_desk(db_session, room_app, project)
    await _approved_by_the_team(client, session.id, credential)

    file = await _the_file(client, session.id, desk)

    (row,) = await releases_of(db_session, session.id)
    assert file["session_id"] == session.id
    assert file["releases"][0]["version"] == 1
    assert file["releases"][0]["forced_by"] is None
    assert file["releases"][0]["session_id"] == session.id
    assert file["numbering"] == "frozen"
    assert file["notices"] == []
    assert file["findings"] == []
    frozen = {one["segment_id"]: one["frase"] for one in row.packet["back_translation"]["segments"]}
    assert [one["frase"] for one in file["stretches"]] == [
        frozen[one["segment_id"]] for one in file["stretches"]
    ]
    assert [one["take_id"] for one in file["takes"]] == [
        take.id for take in await takes_of(db_session, session.id)
    ]
    assert [one["url"] for one in file["takes"]] == [
        AUDIO_ROUTE.format(take_id=take.id) for take in await takes_of(db_session, session.id)
    ]
    assert [one["heard"] for one in file["listening"]] == [True]


async def test_the_file_lists_every_version_of_the_passage_whoever_minted_it(
    client: httpx.AsyncClient, db_session: AsyncSession, room_app
) -> None:
    """A **Version** is numbered per passage per team, and the file is a history of the passage.

    Two conversations about one passage share the sequence, so a draft the second approved is a
    draft of the passage the first is about. Listed per session instead, the consultant reading
    one of them would be shown a history with a version missing from it and no way to tell.
    """
    project, credential = await a_claimed_device(db_session)
    first = await ready_session(db_session, project_id=project.id, tell=_told_once)
    await _approved_by_the_team(client, first.id, credential)
    second = await ready_session(db_session, project_id=project.id, tell=_told_in_two_stretches)
    await _approved_by_the_team(client, second.id, credential)
    desk, _facilitator = await at_the_desk(db_session, room_app, project)

    file = await _the_file(client, first.id, desk)

    assert [one["version"] for one in file["releases"]] == [1, 2]
    assert [one["session_id"] for one in file["releases"]] == [first.id, second.id]


async def test_a_version_another_session_minted_does_not_take_this_ones_numbers(
    client: httpx.AsyncClient, db_session: AsyncSession, room_app
) -> None:
    """A **Release** freezes the reading of the session it was built from, and only that one.

    The number is per passage per team, so the list beside this one carries both versions. What
    it does not carry across is the numbering: a comment a listener filed against frase 1 of
    this session's v1 has to go on meaning that stretch whatever another conversation about the
    same passage approves afterwards. Read off the passage's last version instead, this file
    came back with every number gone and a line saying the reading had moved — about a reading
    that had not moved at all.
    """
    project, credential = await a_claimed_device(db_session)
    mine = await ready_session(db_session, project_id=project.id, tell=_told_once)
    await _approved_by_the_team(client, mine.id, credential)
    theirs = await ready_session(db_session, project_id=project.id, tell=_told_in_two_stretches)
    await _approved_by_the_team(client, theirs.id, credential)
    desk, _facilitator = await at_the_desk(db_session, room_app, project)

    file = await _the_file(client, mine.id, desk)

    assert [one["version"] for one in file["releases"]] == [1, 2]
    assert file["numbering"] == "frozen"
    assert file["approved"] is True
    assert [one["frase"] for one in file["stretches"]] == [1]
    assert file["notices"] == []


async def test_a_stretch_whose_mother_tongue_was_recorded_again_keeps_what_was_said(
    client: httpx.AsyncClient, db_session: AsyncSession, room_app
) -> None:
    """Re-recording the native audio leaves a stretch standing with nothing said on it yet.

    It is a real unit and the tablet asks for it, and the telling that came before it is the
    team's own words about the passage. Listed as only what was told back, the new row was in
    no list at all and the old one was in nobody's history — so the one thing the consultant
    came for left the document in silence, which is the loss `divided_segments` was added to
    the packet to stop.

    It carries no number, because the numbering of a live reading is the enumeration the
    analyst was given and a stretch with nothing said on it was not in it.
    """
    project, _credential = await a_claimed_device(db_session)
    session = await ready_session(db_session, project_id=project.id, tell=_told_once)
    desk, _facilitator = await at_the_desk(db_session, room_app, project)
    told = (await final_segments(db_session, session.id))[0]
    moved = await capture_segment(
        db_session,
        session,
        take_id="ensaio-2",
        starts_ms=0,
        ends_ms=CLIP_MS,
        replaces=told,
    )

    file = await _the_file(client, session.id, desk)

    (standing,) = file["stretches"]
    assert standing["segment_id"] == moved.id
    assert standing["transcript"] is None
    assert "frase" not in standing
    assert [one["segment_id"] for one in standing["history"]] == [told.id]
    assert standing["history"][0]["transcript"] == FIRST_TELLING
    assert file["abandoned"] == []


async def test_the_file_of_a_forced_session_says_who_forced_it_and_keeps_the_note(
    client: httpx.AsyncClient, db_session: AsyncSession, room_app
) -> None:
    """The other half: a draft a person minted over a finding the team stopped answering.

    Who forced it and when live only on the release row, and the analyst's own words live
    here and nowhere else — the packet beside it carries the kind and the address alone.
    """
    project, _credential = await a_claimed_device(db_session)
    session = await a_p02_telling_with_the_swapped_cause(db_session, project)
    desk, facilitator = await at_the_desk(db_session, room_app, project)
    forced = await client.post(desk_release(session.id), headers=desk, json={"force": True})
    assert forced.status_code == 200, forced.text

    file = await _the_file(client, session.id, desk)

    assert file["releases"][0]["forced_by"] == facilitator.id
    assert file["releases"][0]["forced_at"] is not None
    assert file["releases"][0]["forced_open_findings"][0]["note"] == THE_FINDING
    (finding,) = file["findings"]
    assert finding["note"] == THE_FINDING
    assert finding["kind"] == "addition"
    assert finding["segment_id"] == file["stretches"][0]["segment_id"]
    assert finding["chunk"] == 1
    assert file["checked"] is False
    assert file["analysed"] is True


async def test_another_teams_facilitator_gets_404_and_no_file(
    client: httpx.AsyncClient, db_session: AsyncSession, room_app
) -> None:
    """The file is the whole of what a team recorded, so it is scoped like the release read.

    The owner reaching the same session is what makes the refusal mean scoping rather than an
    id nobody minted.
    """
    mine, _credential = await a_claimed_device(db_session, email="dona@example.com")
    theirs, _other = await a_claimed_device(db_session, email="estranha@example.com")
    session = await ready_session(db_session, project_id=mine.id, tell=_told_once)
    owner, _her = await at_the_desk(db_session, room_app, mine)
    stranger, _them = await at_the_desk(db_session, room_app, theirs)

    refused = await client.get(desk_retro(session.id), headers=stranger)

    assert refused.status_code == 404, refused.text
    assert "stretches" not in refused.json()
    assert (await client.get(desk_retro(session.id), headers=owner)).status_code == 200


async def test_every_telling_of_a_stretch_travels_with_its_count(
    client: httpx.AsyncClient, db_session: AsyncSession, room_app
) -> None:
    """A **Correction** is a new row, and the file carries the whole chain (ADR 0004).

    Oldest first under the stretch standing now, each with the words the team said that time
    and the moment it stopped counting — and the recordings of the superseded tellings are
    reachable too, because what they said the first time is a signal for the consultant.
    """
    project, _credential = await a_claimed_device(db_session)
    session = await ready_session(db_session, project_id=project.id, tell=_told_once)
    desk, _facilitator = await at_the_desk(db_session, room_app, project)
    first = (await final_segments(db_session, session.id))[0]
    second_retro = await _a_retro_take(db_session, session, "segunda")
    await _tell_again(db_session, session, first, second_retro, SECOND_TELLING)
    second = (await final_segments(db_session, session.id))[0]
    third_retro = await _a_retro_take(db_session, session, "terceira")
    await _tell_again(db_session, session, second, third_retro, THIRD_TELLING)

    file = await _the_file(client, session.id, desk)

    (standing,) = file["stretches"]
    assert standing["tellings"] == 3
    assert standing["transcript"] == THIRD_TELLING
    assert [one["tellings"] for one in standing["history"]] == [1, 2]
    assert [one["transcript"] for one in standing["history"]] == [FIRST_TELLING, SECOND_TELLING]
    assert [one["segment_id"] for one in standing["history"]] == [first.id, second.id]
    assert all(one["superseded_at"] is not None for one in standing["history"])
    linked = {one["take_id"]: one["url"] for one in file["takes"]}
    for one in standing["history"]:
        assert linked[one["bridge_take_id"]] == AUDIO_ROUTE.format(take_id=one["bridge_take_id"])


async def test_an_abandoned_telling_back_is_listed_apart(
    client: httpx.AsyncClient, db_session: AsyncSession, room_app
) -> None:
    """A telling-back started over abandons its stretches: nothing took their place.

    They are not history *of* anything standing now, so listing them inside a chain would
    tell the consultant a stretch was retold when the team threw the recording away.
    """
    project, _credential = await a_claimed_device(db_session)
    session = await ready_session(db_session, project_id=project.id, tell=_told_once)
    desk, _facilitator = await at_the_desk(db_session, room_app, project)
    thrown_away = (await final_segments(db_session, session.id))[0]
    await begin_back_translation_again(db_session, await get_session(db_session, session.id))
    fresh_retro = await _a_retro_take(db_session, session, "de-novo")
    await capture_segment(
        db_session,
        session,
        take_id="ensaio-2",
        starts_ms=0,
        ends_ms=CLIP_MS,
        bridge_take_id=fresh_retro.id,
        transcript=SECOND_TELLING,
    )

    file = await _the_file(client, session.id, desk)

    (abandoned,) = file["abandoned"]
    assert abandoned["segment_id"] == thrown_away.id
    assert abandoned["transcript"] == FIRST_TELLING
    (retired,) = await retired_segments(db_session, session.id)
    assert retired.superseded_by_id is None
    assert [one["transcript"] for one in file["stretches"]] == [SECOND_TELLING]
    assert file["stretches"][0]["history"] == []


async def test_a_chain_that_ends_on_a_stretch_the_team_divided_was_not_abandoned(
    client: httpx.AsyncClient, db_session: AsyncSession, room_app
) -> None:
    """A stretch the team divided still counts, so a chain reaching it reached something.

    **Abandoned** means nothing took a stretch's place: the telling-back started over on a
    recording the team threw away (ADR 0004). Dividing is the opposite — the team heard two
    ideas in what they had said, which is them working — and reading the one as the other
    would tell the consultant they lost a telling that is exactly where they left it.

    Read off the leaves, a divided stretch is in neither list: not retired, because nothing
    replaced it, and not final, because it is not a unit any more. That is the hole this pins.
    """
    project, _credential = await a_claimed_device(db_session)
    session = await ready_session(db_session, project_id=project.id, tell=_told_once)
    desk, _facilitator = await at_the_desk(db_session, room_app, project)
    first = (await final_segments(db_session, session.id))[0]
    second_retro = await _a_retro_take(db_session, session, "antes-da-divisao")
    await _tell_again(db_session, session, first, second_retro, SECOND_TELLING)
    told_twice = (await final_segments(db_session, session.id))[0]
    await divide_segment(db_session, session, told_twice, at_ms=30000)

    file = await _the_file(client, session.id, desk)

    assert [row.id for row in await retired_segments(db_session, session.id)] == [first.id]
    assert file["abandoned"] == []


async def test_the_frozen_numbers_are_the_latest_releases_and_a_new_stretch_has_none(
    client: httpx.AsyncClient, db_session: AsyncSession, room_app
) -> None:
    """The number a listener filed a comment against keeps meaning what it meant.

    A stretch told after the approval was in no reading the version froze, so it carries no
    number at all — absent rather than null, the packet's own rule — and a line says so.
    """
    project, credential = await a_claimed_device(db_session)
    session = await ready_session(db_session, project_id=project.id, tell=_told_in_two_stretches)
    desk, _facilitator = await at_the_desk(db_session, room_app, project)
    await _approved_by_the_team(client, session.id, credential)
    late_retro = await _a_retro_take(db_session, session, "tardia")
    await capture_segment(
        db_session,
        session,
        take_id=REHEARSAL,
        starts_ms=CLIP_MS,
        ends_ms=CLIP_MS + 10000,
        bridge_take_id=late_retro.id,
        transcript="e chegaram a Belem no comeco da colheita",
    )

    file = await _the_file(client, session.id, desk)

    assert file["numbering"] == "frozen"
    assert [one.get("frase") for one in file["stretches"]] == [1, 2, None]
    assert "frase" not in file["stretches"][2]
    assert READING_MOVED in file["notices"]


async def test_an_unapproved_session_numbers_the_live_reading_and_says_so(
    client: httpx.AsyncClient, db_session: AsyncSession, room_app
) -> None:
    """With no **Version** there is nothing frozen, and the file must not pretend there is.

    The numbers are the reading of right now, and the line beside them says exactly that: a
    consultant filing a comment against frase 2 of an unapproved draft has been told what
    that number is worth.
    """
    project, _credential = await a_claimed_device(db_session)
    session = await ready_session(db_session, project_id=project.id, tell=_told_in_two_stretches)
    desk, _facilitator = await at_the_desk(db_session, room_app, project)

    file = await _the_file(client, session.id, desk)

    assert file["numbering"] == "live"
    assert file["approved"] is False
    assert file["releases"] == []
    assert [one["frase"] for one in file["stretches"]] == [1, 2]
    assert NOT_APPROVED in file["notices"]


async def test_a_session_the_analyst_never_read_says_so(
    client: httpx.AsyncClient, db_session: AsyncSession, room_app
) -> None:
    """Never read and read clean leave the same defaults, so the file has to name the difference.

    Told the passage carries no finding, a consultant would read a check that never happened
    as one that came out clean.
    """
    project, _credential = await a_claimed_device(db_session)
    session = await ready_session(
        db_session, project_id=project.id, tell=never_analysed_telling_back
    )
    desk, _facilitator = await at_the_desk(db_session, room_app, project)

    file = await _the_file(client, session.id, desk)

    assert file["analysed"] is False
    assert file["checked"] is False
    assert file["checked_at"] is None
    assert NEVER_READ in file["notices"]
    assert file["findings"] == []
    assert [one["transcript"] for one in file["stretches"]] == ["Noemi voltou com Rute"]


async def test_a_hard_stretch_mark_lands_on_the_stretch_standing_now(
    client: httpx.AsyncClient, db_session: AsyncSession, room_app
) -> None:
    """A mark names the first telling of a chain, and the consultant reads where it stands.

    The row cannot move — it is written once and cleared by nothing — so the file walks the
    chain forward and says both: which stretch the mark is about now, and the name the row
    carries. A chain the team abandoned leads to no stretch standing, and the file says that
    with a null rather than by pointing at a row nobody can hear any more.
    """
    project, _credential = await a_claimed_device(db_session)
    session_id = await _a_session(db_session, team_id=project.id)
    desk, _facilitator = await at_the_desk(db_session, room_app, project)
    take_id = await _rehearse(client, session_id)
    await _told(client, session_id, take_id, 1)
    first = (await final_segments(db_session, session_id))[0]
    for saying in ("o trecho de novo", "o trecho mais uma vez", "o trecho pela quarta vez"):
        again = await _tell(client, session_id, take_id, 1, again=True, saying=saying)
        assert again.status_code == 200, again.text
    standing = (await final_segments(db_session, session_id))[0]

    file = await _the_file(client, session_id, desk)

    (mark,) = file["hard_stretches"]
    (row,) = await _marks(db_session, session_id)
    assert mark["first_telling_id"] == first.id
    assert mark["segment_id"] == standing.id
    assert mark["tellings"] == 3
    assert mark["crossed_at"] == row.crossed_at.isoformat()
    assert row.segment_id == first.id

    await begin_back_translation_again(db_session, await get_session(db_session, session_id))

    after = await _the_file(client, session_id, desk)

    (orphaned,) = after["hard_stretches"]
    assert orphaned["first_telling_id"] == first.id
    assert orphaned["segment_id"] is None


async def test_the_listening_report_names_each_part(
    client: httpx.AsyncClient, db_session: AsyncSession, room_app
) -> None:
    """One entry per part of the rehearsal, and the file says which one nobody heard.

    A part is its own recording, so what the team heard of one is judged against that part
    alone (ADR 0017). An attempt the team replaced keeps the listening it reported at the
    time, which is the record of what that reading stood on and is never evidence about the
    recording standing now.
    """
    project, _credential = await a_claimed_device(db_session)
    session, (first, second, third) = await rehearsed_in_parts(db_session, 3, project_id=project.id)
    desk, _facilitator = await at_the_desk(db_session, room_app, project)
    heard_two = [
        PlayedTake(take_id=part.id, played_ranges=[(0, PART_MS)], clip_duration_ms=PART_MS)
        for part in (first, second)
    ]
    state = await _read(db_session, session)
    await report_playback(
        db_session,
        session,
        state,
        played_by_take=heard_two,
        played_ranges=[(0, PART_MS)],
        clip_duration_ms=PART_MS,
    )

    file = await _the_file(client, session.id, desk)

    assert {one["take_id"]: one["heard"] for one in file["listening"]} == {
        first.id: True,
        second.id: True,
        third.id: False,
    }
    assert [one["take_id"] for one in file["listening"] if not one["heard"]] == [third.id]
    assert [one["clip_duration_ms"] for one in file["listening"] if one["heard"]] == [
        PART_MS,
        PART_MS,
    ]

    await begin_back_translation_again(db_session, await get_session(db_session, session.id))

    archived = await _the_file(client, session.id, desk)

    (attempt,) = archived["superseded_attempts"]
    assert [entry["take_id"] for entry in attempt["played_by_take"]] == [first.id, second.id]
