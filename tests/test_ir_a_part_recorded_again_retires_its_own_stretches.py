"""ENG-864 — recording a **Part** again retires that part's stretches and nothing else.

The tablet uploads every part of a rehearsal under its own number. A rehearsal take arriving
under a number an earlier take already carries is that part recorded again, and the verb is
that upload: no route of its own and no flag. What it retires is the stretches whose recording
is one of the earlier takes of that number — divided parents and their pieces alike — and what
it leaves standing is every other part, its listening and its words.

What it retires becomes **Abandoned** rows, never deletions: the **Packet** carries them in
`superseded_segments` and the **Retroverification file** in `abandoned`, and the file keeps a
link to both takes.

Because a part can now be retired on its own, the reading order is the part's number and then
the milliseconds inside it (ADR 0021), so the next telling of a re-recorded part reads between
its neighbours instead of after them. Every consumer of that order is here: the packet's
`frase`, the **Check block**'s `frase` and `clipKey`, the file's live numbering and its list of
divided stretches, and the numbered list the **Analyst** is handed.

The packet also says which takes the rehearsal is: one per part, the newest, with the grain it
was told in. The rehearsal thrown away whole keeps its own route and goes on retiring
everything.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import App
from app.db.models.internalization_room import IRSegment, IRSession
from app.db.models.project import Project
from app.services.internalization_room.back_translation import (
    Finding,
    FindingKind,
    VoicedVerdict,
)
from app.services.internalization_room.release import compose_internalization_release
from app.services.internalization_room.segments import (
    capture_segment,
    current_segments,
    divide_segment,
)
from app.services.internalization_room.sessions import (
    back_translation_of,
    get_session,
    save_back_translation,
)
from app.services.internalization_room.takes import take_by_id
from tests.baker import make_app, make_role
from tests.release_harness import (
    APP_KEY,
    KEY,
    PREFIX,
    a_claimed_device,
    at_the_desk,
    desk_retro,
    ready_session,
    rehearsed_session,
    reported_playback,
)
from tests.room_harness import (
    PART_MS,
    REHEARSED_AT,
    another_rehearsal_take,
    press_terminei,
    rehearsed_in_parts,
    room_client,
    stored_telling_back,
    tell_back_about,
    the_bucket_is_in_memory,
    the_room_speaks,
    the_upload_landed_at,
    upload_a_part,
)

#: What the team says when they tell the re-recorded part back. Its own sentence, so a case can
#: find where in the reading it landed without matching anything a builder wrote.
RETOLD = "a parte dois contada de novo"

#: New bytes on every upload, because a take is addressed by the hash of its audio: the same
#: bytes twice are one row and no re-recording at all.
NEW_AUDIO = b"a equipe gravou esta parte outra vez"


class _TheReadingTheAnalystGot:
    """The analyst, keeping the numbered list it was handed as well as the count.

    The room's own double counts the readings and throws the prompt away. One case here asks
    which position each stretch was numbered at *on the way to* the analyst, and that is
    readable nowhere else — the answer that comes back says nothing about the order of the
    question — so this module stands in for the same call and keeps both.

    What is kept is the system prompt, because that is where the numbered stretches are
    rendered; the user content is one fixed sentence asking for the comparison.
    """

    def __init__(self) -> None:
        self.readings: list[str] = []

    async def __call__(self, *, system_prompt: str, user_content: str, **_: Any) -> str:
        self.readings.append(system_prompt)
        return '{"evidence_sufficient": true, "findings": []}'


@pytest.fixture(autouse=True)
def analyst(monkeypatch: pytest.MonkeyPatch) -> _TheReadingTheAnalystGot:
    """The analyst, and what it was actually asked to read."""
    from app.services.internalization_room import back_translation as bt_service

    reader = _TheReadingTheAnalystGot()
    monkeypatch.setattr(bt_service, "call_agent", reader)
    return reader


@pytest.fixture(autouse=True)
def voice(monkeypatch: pytest.MonkeyPatch) -> None:
    """The Speaker and the synthesizer, so `terminei` answers without a model or a bucket."""
    the_room_speaks(monkeypatch)


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    """The room's routes, with the bucket in memory so an upload needs no storage."""
    the_bucket_is_in_memory(monkeypatch)
    async with room_client(db_session, monkeypatch) as room:
        yield room


@pytest.fixture()
async def room_app(db_session: AsyncSession) -> App:
    app = await make_app(db_session, app_key=APP_KEY, name="Internalization Room")
    await make_role(db_session, app.id, role_key="facilitator", label="Facilitator", is_system=True)
    return app


async def _by_part(db: AsyncSession, session_id: str) -> dict[str, IRSegment]:
    """The stretch standing on each part, by the recording it is a slice of."""
    return {stretch.take_id: stretch for stretch in await current_segments(db, session_id)}


async def _stored(db: AsyncSession, stretch: IRSegment) -> IRSegment:
    """The row as the database holds it, not the copy this session has been carrying."""
    await db.refresh(stretch)
    return stretch


async def _standing_ids(db: AsyncSession, session_id: str) -> list[str]:
    return [stretch.id for stretch in await current_segments(db, session_id)]


async def _recorded_again(
    client: httpx.AsyncClient, session: IRSession, *, part: int | None, audio: bytes = NEW_AUDIO
) -> str:
    """Upload a rehearsal part under a number, and answer with the take id the room kept."""
    kept = await upload_a_part(client, session.id, part=part, audio=audio)
    assert kept.status_code == 200, kept.text
    return str(kept.json()["take_id"])


async def _told_on(
    db: AsyncSession, session: IRSession, take_id: str, *, transcript: str = RETOLD
) -> IRSegment:
    """The team tells the fresh recording of a part back."""
    return await tell_back_about(
        db, session, await take_by_id(db, take_id), transcript=transcript, bridge_take_id="retro-2"
    )


async def _packet(db: AsyncSession, session: IRSession) -> dict[str, Any]:
    """The packet this session composes right now, read past whatever is blocking it.

    The composer answers with the artifact and the blockers apart, and it is what both the live
    facilitator read and the approval call are built on. Every case here composes a session the
    gate would refuse — a part just recorded again is a check that has to start over — and the
    refusal is not what the case is about.
    """
    fresh = await get_session(db, session.id)
    artifact, _blockers = await compose_internalization_release(db, fresh)
    return artifact


async def _the_file(
    client: httpx.AsyncClient,
    db: AsyncSession,
    session: IRSession,
    project: Project,
    room_app: App,
) -> dict[str, Any]:
    """The retroverification file, served the way the facilitator reads it."""
    desk, _user = await at_the_desk(db, room_app, project)
    answered = await client.get(desk_retro(session.id), headers=desk)
    assert answered.status_code == 200, answered.text
    return dict(answered.json())


async def _with_findings(
    db: AsyncSession, session: IRSession, findings: list[Finding], *, verdict: bool = False
) -> None:
    """Put the telling-back where a check that has already run would leave it."""
    fresh = await get_session(db, session.id)
    state = back_translation_of(fresh)
    state.findings = findings
    state.checked = not findings
    if verdict:
        state.verdict = VoicedVerdict(clip_key="clipe-1", fixed_line="", used_fail_safe=False)
    await save_back_translation(db, fresh, state)


async def _report_what_was_played(db: AsyncSession, session: IRSession) -> None:
    """The team's report over the parts their stretches are standing on right now."""
    fresh = await get_session(db, session.id)
    await reported_playback(db, fresh, back_translation_of(fresh))


async def test_recording_part_two_again_retires_only_its_own_stretches(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """The rule in one case: the part recorded over loses its stretches and nobody else does.

    This is the case that fails if the verb reaches past the part it was given, so what it
    asserts is which stretches are still standing and not merely that part two's are gone.
    """
    session, (one, two, three) = await rehearsed_in_parts(db_session, 3)
    standing = await _by_part(db_session, session.id)

    await _recorded_again(client, session, part=2)

    assert await _standing_ids(db_session, session.id) == [
        standing[one.id].id,
        standing[three.id].id,
    ], "parts one and three are the same stretches they were"
    assert (await _stored(db_session, standing[one.id])).superseded_at is None
    assert (await _stored(db_session, standing[three.id])).superseded_at is None
    retired = await _stored(db_session, standing[two.id])
    assert retired.superseded_at is not None
    assert retired.superseded_by_id is None, "abandoned, because nothing took its place"


async def test_a_divided_stretch_of_the_part_goes_with_it(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """A **Divided stretch** of the part is the part: the parent and both pieces go together.

    Left standing, the pieces would go on describing audio the team recorded over, and their
    parent would go on being a stretch nothing in the room can reach.
    """
    session, (one, two, three) = await rehearsed_in_parts(db_session, 3)
    standing = await _by_part(db_session, session.id)
    parent = standing[two.id]
    head, tail = await divide_segment(db_session, session, parent, at_ms=PART_MS // 2)

    await _recorded_again(client, session, part=2)

    for row in (parent, head, tail):
        assert (await _stored(db_session, row)).superseded_at is not None
    assert await _standing_ids(db_session, session.id) == [
        standing[one.id].id,
        standing[three.id].id,
    ]


async def test_the_retired_part_is_kept_as_history(
    client: httpx.AsyncClient, db_session: AsyncSession, room_app: App
) -> None:
    """Retired, never deleted: the packet carries the rows and the file carries both takes."""
    project, _credential = await a_claimed_device(db_session)
    session, (_one, two, _three) = await rehearsed_in_parts(db_session, 3, project_id=project.id)
    was = (await _by_part(db_session, session.id))[two.id].id

    fresh = await _recorded_again(client, session, part=2)

    packet = await _packet(db_session, session)
    file = await _the_file(client, db_session, session, project, room_app)

    assert was in [row["segment_id"] for row in packet["back_translation"]["superseded_segments"]]
    assert was in [row["segment_id"] for row in file["abandoned"]]
    named = [row["take_id"] for row in file["takes"]]
    assert two.id in named and fresh in named, "the file keeps every take, the replaced one too"


async def test_the_next_telling_of_part_two_lands_between_parts_one_and_three(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """ADR 0021: a stretch is read by its part's number, then by its milliseconds.

    Numbered by the stretch's own ordinal, the telling that followed a re-recorded part took
    the next free number and read after every part that comes later in the passage.
    """
    session, (one, _two, three) = await rehearsed_in_parts(db_session, 3)
    standing = await _by_part(db_session, session.id)
    fresh = await _recorded_again(client, session, part=2)
    retold = await _told_on(db_session, session, fresh)

    read = (await _packet(db_session, session))["back_translation"]["segments"]

    assert [(row["segment_id"], row["frase"]) for row in read] == [
        (standing[one.id].id, 1),
        (retold.id, 2),
        (standing[three.id].id, 3),
    ]


async def test_the_check_block_numbers_the_new_part_in_its_place(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """The **Check block** reads the same order, and names the recording the team would play."""
    session, _parts = await rehearsed_in_parts(db_session, 3)
    fresh = await _recorded_again(client, session, part=2)
    retold = await _told_on(db_session, session, fresh)
    await _with_findings(
        db_session,
        session,
        [Finding(kind=FindingKind.ADDITION, note="entrou algo", segment_id=retold.id, chunk=2)],
    )

    check = (await _packet(db_session, session))["check"]

    assert check["findings"][0]["frase"] == 2
    assert check["findings"][0]["clipKey"] == fresh


async def test_the_retroverification_file_reads_the_new_part_in_its_place(
    client: httpx.AsyncClient, db_session: AsyncSession, room_app: App
) -> None:
    """The file numbers a reading nobody has approved yet, and it numbers it the same way."""
    project, _credential = await a_claimed_device(db_session)
    session, (one, _two, three) = await rehearsed_in_parts(db_session, 3, project_id=project.id)
    standing = await _by_part(db_session, session.id)
    fresh = await _recorded_again(client, session, part=2)
    retold = await _told_on(db_session, session, fresh)

    file = await _the_file(client, db_session, session, project, room_app)

    assert file["numbering"] == "live"
    assert [(row["segment_id"], row["frase"]) for row in file["stretches"]] == [
        (standing[one.id].id, 1),
        (retold.id, 2),
        (standing[three.id].id, 3),
    ]


async def test_the_analyst_is_numbered_in_reading_order(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: _TheReadingTheAnalystGot
) -> None:
    """The list the analyst reads is the reading, so the re-recorded part is numbered two.

    Numbered last, the analyst would be told the team said the middle of the passage at the
    end, and every finding it placed by number would land on the wrong stretch.
    """
    session, _parts = await rehearsed_in_parts(db_session, 3)
    fresh = await _recorded_again(client, session, part=2)
    await _told_on(db_session, session, fresh)
    await _report_what_was_played(db_session, session)

    answered = await press_terminei(client, session.id)

    assert answered.status_code == 200, answered.text
    numbered = next(line for line in analyst.readings[0].splitlines() if RETOLD in line)
    assert numbered.startswith("2. "), "the part recorded again is read second, not last"


async def test_the_listening_of_parts_one_and_three_survives_and_the_new_take_is_unheard(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: _TheReadingTheAnalystGot
) -> None:
    """The team hears the part they recorded again, and only that one.

    Their listening to the other parts is evidence about recordings that did not move, so a
    rule that made them sit through the whole rehearsal again would be paid for in the parts
    they start skipping.
    """
    session, _parts = await rehearsed_in_parts(db_session, 3)
    await _report_what_was_played(db_session, session)
    fresh = await _recorded_again(client, session, part=2)
    await _told_on(db_session, session, fresh)

    answered = await press_terminei(client, session.id)

    assert answered.status_code == 200, answered.text
    assert answered.json()["unheard_take_ids"] == [fresh]
    assert answered.json()["checked"] is False
    assert analyst.readings == [], "the refusal is answered before anything is read"


async def test_findings_on_the_old_part_leave_and_the_check_starts_over(
    client: httpx.AsyncClient, db_session: AsyncSession, analyst: _TheReadingTheAnalystGot
) -> None:
    """The part's findings go with the part, and the passage is read again from the start.

    A finding about audio the team recorded over is about nothing, and a check that stayed
    clean over it would tell the team a passage they have just changed is settled.
    """
    session, (one, two, three) = await rehearsed_in_parts(db_session, 3)
    standing = await _by_part(db_session, session.id)
    await _with_findings(
        db_session,
        session,
        [
            Finding(
                kind=FindingKind.UNCLEAR,
                note="nao deu para entender",
                segment_id=standing[one.id].id,
            ),
            Finding(kind=FindingKind.ADDITION, note="entrou algo", segment_id=standing[two.id].id),
        ],
        verdict=True,
    )

    fresh = await _recorded_again(client, session, part=2)

    left = await stored_telling_back(db_session, session)
    assert [finding.segment_id for finding in left.findings] == [standing[one.id].id]
    assert left.checked is False
    assert left.verdict is None

    retold = await _told_on(db_session, session, fresh)
    await _report_what_was_played(db_session, session)
    answered = await press_terminei(client, session.id)

    assert answered.status_code == 200, answered.text
    assert len(analyst.readings) == 1
    after = await stored_telling_back(db_session, session)
    assert after.analysed_segment_ids == [
        standing[one.id].id,
        retold.id,
        standing[three.id].id,
    ], "read again whole, and in the order the passage is read"


async def test_a_checked_passage_stops_being_checked(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """A passage the analyst read clean is no longer that passage once a part is recorded again.

    The check is about a reading, and the reading changed. Left standing it would tell the team
    a passage they have just changed is settled, and the stored verdict would be said aloud
    again about stretches that no longer count.
    """
    session, _parts = await rehearsed_in_parts(db_session, 3)
    await _with_findings(db_session, session, [], verdict=True)
    was = await stored_telling_back(db_session, session)
    assert was.checked is True and was.verdict is not None, "the case starts from a clean check"

    await _recorded_again(client, session, part=2)

    after = await stored_telling_back(db_session, session)
    assert after.checked is False
    assert after.verdict is None


async def test_a_piece_re_recorded_onto_another_take_goes_with_its_part(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """A piece of a divided stretch is a piece of that part, whatever take it now sits on.

    A stretch re-recorded in the mother tongue moves onto the take that carries the new audio,
    and when the passage could not be rebuilt around it the piece stays there — on a recording
    with no part number of its own. Kept by the take alone, it would survive its own parent: a
    current row whose parent is abandoned, which the reading walks past and never reaches, and
    which no list the room serves would ever show again.
    """
    session, (one, two, three) = await rehearsed_in_parts(db_session, 3)
    standing = await _by_part(db_session, session.id)
    head, _tail = await divide_segment(db_session, session, standing[two.id], at_ms=PART_MS // 2)
    elsewhere = await another_rehearsal_take(db_session, session, sha256="f" * 64)
    moved = await capture_segment(
        db_session,
        session,
        take_id=elsewhere.id,
        starts_ms=0,
        ends_ms=PART_MS // 2,
        replaces=head,
    )

    await _recorded_again(client, session, part=2)

    assert (await _stored(db_session, moved)).superseded_at is not None
    assert await _standing_ids(db_session, session.id) == [
        standing[one.id].id,
        standing[three.id].id,
    ]


async def test_a_swap_on_the_old_part_leaves_whole(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """A **Swap** is one thing for the team, so half of it can never be left behind.

    The two halves are joined by the frase the analyst numbered, and a missing element placed
    after that frase resolves to the *next* stretch — which is a slice of another part. Dropped
    by the stretch alone, the missing half would come back the following round on its own.
    """
    session, (_one, two, three) = await rehearsed_in_parts(db_session, 3)
    standing = await _by_part(db_session, session.id)
    await _with_findings(
        db_session,
        session,
        [
            Finding(
                kind=FindingKind.ADDITION,
                note="entrou uma relacao",
                segment_id=standing[two.id].id,
                chunk=2,
            ),
            Finding(
                kind=FindingKind.MISSING,
                note="e a que a historia conta saiu",
                segment_id=standing[three.id].id,
                chunk=2,
            ),
        ],
    )

    await _recorded_again(client, session, part=2)

    left = await stored_telling_back(db_session, session)
    assert left.findings == [], "the swap left whole: the missing half sits on part three"


async def test_a_missing_without_an_address_survives_the_re_record(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """A **Missing without an address** points at no part, so no part takes it away.

    It says the team has not recorded something at all, which a fresh recording of one part
    neither answers nor makes untrue.
    """
    session, (_one, two, _three) = await rehearsed_in_parts(db_session, 3)
    standing = await _by_part(db_session, session.id)
    await _with_findings(
        db_session,
        session,
        [
            Finding(
                kind=FindingKind.ADDITION,
                note="entrou algo",
                segment_id=standing[two.id].id,
                chunk=2,
            ),
            Finding(kind=FindingKind.MISSING, note="falta o fim da cena", segment_id=None, chunk=3),
        ],
    )

    await _recorded_again(client, session, part=2)

    left = await stored_telling_back(db_session, session)
    assert [finding.kind for finding in left.findings] == [FindingKind.MISSING]
    assert left.findings[0].segment_id is None
    assert left.checked is False


async def test_the_packet_carries_one_take_per_part_the_newest(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """One take per part, the newest, and the grain the rehearsal was told in.

    Listing every rehearsal take sent the abandoned recording of a part to Refine beside the
    one that replaced it, under labels that told them apart by nothing; and describing a
    rehearsal told in three parts as told whole is a sentence about a file that never existed.
    """
    session, (one, two, three) = await rehearsed_in_parts(db_session, 3)

    fresh = await _recorded_again(client, session, part=2)

    audio = (await _packet(db_session, session))["audio"]
    assert [take["take_id"] for take in audio["rehearsal_takes"]] == [one.id, fresh, three.id]
    assert two.id not in [take["take_id"] for take in audio["rehearsal_takes"]]
    assert audio["recording_grain"] == "parts"


async def test_a_rehearsal_told_whole_reads_whole(db_session: AsyncSession) -> None:
    """A rehearsal recorded in one go is one part, and the packet says so."""
    session = await ready_session(db_session)

    audio = (await _packet(db_session, session))["audio"]

    assert audio["recording_grain"] == "whole"
    assert len(audio["rehearsal_takes"]) == 1


async def test_a_whole_recording_uploaded_again_retires_nothing(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """The rehearsal thrown away whole is the restart route's business, not this verb's.

    An upload carrying no part number says nothing about which part it replaces, and a verb
    that guessed would retire a telling-back the team never asked to lose. Two takes with no
    number agree on it, which is what makes the guess available and the guard necessary.

    The telling stands on the session's own rehearsal take, and that is the whole case: over a
    stretch pointing at a recording that is not there, the verb would find nothing to retire
    whatever it decided, and the case would pass without ever asking the question.
    """
    session, take = await rehearsed_session(db_session)
    await tell_back_about(db_session, session, take)
    await _with_findings(db_session, session, [])
    before = await _standing_ids(db_session, session.id)

    await _recorded_again(client, session, part=None)

    assert await _standing_ids(db_session, session.id) == before
    assert (await stored_telling_back(db_session, session)).checked is True


async def test_a_new_part_number_retires_nothing(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """A number no take carries yet is a part being recorded for the first time."""
    session, _parts = await rehearsed_in_parts(db_session, 3)
    before = await _standing_ids(db_session, session.id)

    await _recorded_again(client, session, part=4)

    assert await _standing_ids(db_session, session.id) == before
    assert len((await _packet(db_session, session))["audio"]["rehearsal_takes"]) == 4


async def test_the_same_bytes_sent_again_leave_the_check_alone(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """The tablet's retry after a lost connection costs the team nothing.

    It re-sends bytes it already sent without asking whether they landed, and a take is
    addressed by the hash of its audio, so the second send is the row that already exists and
    no recording was made. Nothing is retired by it, and a check the team has since earned
    would have been thrown away by a request that changed nothing.
    """
    session, _parts = await rehearsed_in_parts(db_session, 3)
    fresh = await _recorded_again(client, session, part=2)
    await _told_on(db_session, session, fresh)
    await _with_findings(db_session, session, [])
    before = await _standing_ids(db_session, session.id)

    again = await _recorded_again(client, session, part=2)

    assert again == fresh, "the same audio is the same take"
    assert await _standing_ids(db_session, session.id) == before
    assert (await stored_telling_back(db_session, session)).checked is True


async def test_a_retry_of_a_replaced_take_leaves_the_part_that_replaced_it(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """A stale upload out of the outbox is not the team recording the part again.

    The tablet re-sends bytes without asking whether they landed, and its outbox drains
    whenever the link comes back — so the upload that arrives can be one the team recorded over
    long ago. Read as a re-recording, it would abandon the part standing now and take the check
    with it: the team losing the work they just did to a request carrying nothing new.

    Which take is the part is the one question the takes can answer, and it is the same answer
    the **Packet** is built on.

    The first re-record is moved back in time on purpose: the tablet sends no pass with a
    rehearsal part and SQLite stamps the second, so two uploads inside one case are the same
    instant under the same pass, and the case would be asking the engine's row order rather
    than the rule.
    """
    session, _parts = await rehearsed_in_parts(db_session, 3)
    replaced = await _recorded_again(client, session, part=2, audio=b"a primeira regravacao")
    await the_upload_landed_at(db_session, replaced, REHEARSED_AT + timedelta(hours=1))
    await _told_on(db_session, session, replaced, transcript="a parte dois, primeira vez")
    standing = await _recorded_again(client, session, part=2, audio=b"a segunda regravacao")
    told = await _told_on(db_session, session, standing)
    await _with_findings(db_session, session, [])

    retried = await _recorded_again(client, session, part=2, audio=b"a primeira regravacao")

    assert retried == replaced, "the same audio is the take that already holds it"
    assert told.id in await _standing_ids(db_session, session.id)
    assert (await _stored(db_session, told)).superseded_at is None
    assert (await stored_telling_back(db_session, session)).checked is True


async def test_starting_over_still_retires_every_part(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """The recording thrown away whole keeps its own verb, and it still takes everything."""
    session, _parts = await rehearsed_in_parts(db_session, 3)

    answered = await client.post(
        f"{PREFIX}/sessions/{session.id}/back-translation/restart", headers={"X-Room-Key": KEY}
    )

    assert answered.status_code == 200, answered.text
    assert answered.json()["chunks"] == 0
    assert await _standing_ids(db_session, session.id) == []
    assert len((await stored_telling_back(db_session, session)).superseded) == 1


async def test_divided_lists_a_parent_before_its_child(
    client: httpx.AsyncClient, db_session: AsyncSession, room_app: App
) -> None:
    """The file walks the divided stretches the way the reading walks them.

    In row order a divided piece is numbered among its own siblings, so a stretch of the third
    part cut in two, one piece cut again, listed the piece before the stretch it came out of.
    """
    project, _credential = await a_claimed_device(db_session)
    session, (_one, _two, three) = await rehearsed_in_parts(db_session, 3, project_id=project.id)
    root = (await _by_part(db_session, session.id))[three.id]
    head, _tail = await divide_segment(db_session, session, root, at_ms=PART_MS // 2)
    await divide_segment(db_session, session, head, at_ms=PART_MS // 4)

    file = await _the_file(client, db_session, session, project, room_app)

    assert [row["segment_id"] for row in file["divided"]] == [root.id, head.id]


async def test_a_harness_take_names_the_team(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    room_app: App,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A take a case built is a take a facilitator of that team can listen to.

    The audio route refuses a take naming no team before it reads anything else, so a rehearsal
    assembled by the builders was unreachable by behaviour and nothing said so.
    """
    from app.api.internalization_room import takes as take_routes

    monkeypatch.setattr(take_routes, "listen_url", _signed)
    project, _credential = await a_claimed_device(db_session)
    _session, take = await rehearsed_session(db_session, project_id=project.id)
    desk, _user = await at_the_desk(db_session, room_app, project)

    answered = await client.get(
        f"{PREFIX}/facilitator/takes/{take.id}/audio", headers=desk, follow_redirects=False
    )

    assert answered.status_code == 307, answered.text


async def _signed(take: Any) -> str:
    return f"https://storage.example/{take.storage_key}?assinado"
