"""ENG-849 — a **Correction** carries audio and keeps the slice of the **Stretch** it replaces.

One correction is left in the room: the same stretch told again, in the bridge language, over
the recording it already sits in (ADR 0025). So `replace` takes audio and never nothing, and a
call naming a slice that is not this stretch's is refused for that plain reason — not by the rule
that refused a moved slice only when a telling came with it, which went with the path it guarded.

The refusal is one function in the service, asked by the route before it spends a byte on a
request that cannot succeed. Whether the caller also sent words changes nothing: a version
never moves the slice, so a stretch whose *recording* is wrong sends the team back to record
the **Part** again (ADR 0023), which is an upload and not a version.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.db.models.internalization_room import IRSegment, IRTake, IRTakeKind
from app.services.internalization_room.segments import capture_segment, final_segments
from app.services.internalization_room.sessions import RETELLS_BEFORE_A_WARNING
from app.services.internalization_room.takes import current_parts, take_by_id, takes_of
from tests.hard_stretch_harness import FROM_THE_DATABASE
from tests.release_harness import KEY, PREFIX, TABLET
from tests.room_harness import (
    PART_MS,
    another_rehearsal_take,
    record_the_part_again,
    rehearsed_in_parts,
    room_client,
    stretch_on,
    tell_back_about,
    the_bucket_is_in_memory,
    the_room_speaks,
)

HEADERS = {"X-Room-Key": KEY, "X-Room-Device": TABLET}

#: The telling the team records over the stretch they are correcting. Bytes of its own, so a
#: case can tell a recording that was stored from one that was refused before anything was.
AUDIO = b"a equipe contou o trecho outra vez"

#: How far a call may miss the stretch's own range and still name its recording. Half a second
#: is what a team tapping the edge of a band would be off by, not a different stretch.
A_LITTLE_MS = 500

#: What the refusal may not say. The rule it replaces spoke of the product's two kinds of
#: correction, and a message carrying any of these words would be that rule surviving in the one
#: place the team can read.
RETIRED_WORDS = ("correction", "telling", "mother tongue", "two", "rebuild")


@pytest.fixture(autouse=True)
def voice(monkeypatch: pytest.MonkeyPatch) -> None:
    """The Speaker and the synthesizer, so a route answers without a model or a bucket."""
    the_room_speaks(monkeypatch)


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    """The room's routes, with the bucket in memory and the transcriber answering in place."""
    from app.api.internalization_room import segments as segments_api

    the_bucket_is_in_memory(monkeypatch)

    async def _heard(*_: Any, **__: Any) -> str:
        return "o trecho contado outra vez"

    monkeypatch.setattr(segments_api, "heard", _heard)
    async with room_client(db_session, monkeypatch) as room:
        yield room


async def _replace(
    client: httpx.AsyncClient,
    session_id: str,
    segment_id: str,
    *,
    take_id: str,
    starts_ms: int,
    ends_ms: int,
    audio: bytes | None = AUDIO,
) -> httpx.Response:
    """Correct a stretch the way the tablet does: the slice, and the telling recorded over it.

    `audio=None` is the call the route no longer has a branch for, sent only by the case about
    its absence.
    """
    return await client.post(
        f"{PREFIX}/sessions/{session_id}/segments/{segment_id}/replace",
        headers=HEADERS,
        data={"take_id": take_id, "starts_ms": str(starts_ms), "ends_ms": str(ends_ms)},
        files={"file": ("de-novo.m4a", audio, "audio/mp4")} if audio is not None else None,
    )


async def _standing(db: AsyncSession, session_id: str) -> list[IRSegment]:
    """The stretches that count, read off the database and not off what is already loaded.

    The route writes through this very session and nothing expires on commit, so a row it
    retired still answers with the values it carried before. Read fresh first, and let
    `final_segments` say which of them count.
    """
    await db.execute(
        select(IRSegment)
        .where(IRSegment.session_id == session_id)
        .execution_options(**FROM_THE_DATABASE)
    )
    return await final_segments(db, session_id)


async def _take_ids(
    db: AsyncSession, session_id: str, *, kind: IRTakeKind | None = None
) -> list[str]:
    """The recordings this session holds, of one kind or of every kind, read fresh."""
    query = select(IRTake).where(IRTake.session_id == session_id)
    if kind is not None:
        query = query.where(IRTake.kind == kind)
    result = await db.execute(query.execution_options(**FROM_THE_DATABASE))
    return sorted(take.id for take in result.scalars().all())


async def _fresh_takes(db: AsyncSession, session_id: str) -> list[IRTake]:
    """Every recording of the session, read off the database, in the order `takes_of` reads."""
    await db.execute(
        select(IRTake).where(IRTake.session_id == session_id).execution_options(**FROM_THE_DATABASE)
    )
    return await takes_of(db, session_id)


# ---------------------------------------------------------------------------
# 1. A correction with nothing in it
# ---------------------------------------------------------------------------


async def test_a_replacement_without_audio_is_a_validation_error(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """There is no correction to express without the recording of it.

    A call with no file used to be read as the mother tongue re-recorded over a slice of its
    own — a unit the team never records, because a stretch is a listening pause and not
    something anybody rehearsed (ADR 0025). With that branch gone the file is not optional, so
    its absence is the app's own bug and the refusal is the route's own signature, before any
    service is reached and before anything is stored.
    """
    session, (part,) = await rehearsed_in_parts(db_session, 1)
    told = await stretch_on(db_session, session, part)
    was = (told.id, told.pass_number, told.tellings)
    its_slice = (part.id, told.starts_ms, told.ends_ms)
    takes_before = await _take_ids(db_session, session.id)

    refused = await _replace(
        client,
        session.id,
        was[0],
        take_id=its_slice[0],
        starts_ms=its_slice[1],
        ends_ms=its_slice[2],
        audio=None,
    )

    assert refused.status_code == 422, refused.text
    assert "file" in str(refused.json()), "e é o arquivo que falta, não outro campo qualquer"
    standing = await _standing(db_session, session.id)
    assert [(one.id, one.pass_number, one.tellings) for one in standing] == [was], (
        "o trecho continua de pé, no mesmo passe e com a mesma conta de contagens"
    )
    assert await _take_ids(db_session, session.id) == takes_before, "nada foi guardado"


# ---------------------------------------------------------------------------
# 2. A correction addressed at another recording
# ---------------------------------------------------------------------------


async def test_a_replacement_over_another_recording_is_refused_before_anything_is_kept(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """A version never moves the slice, and the reason says only that.

    The team whose *recording* is wrong records the **Part** again, which is an upload under
    that part's number and retires that part's stretches (ADR 0023). Nothing about it comes
    through here, so a call naming another recording is knowable from the stretch and the form
    fields — and is answered before the bytes are kept and the transcriber paid, which is the
    argument the telling-back route already makes for the slice that is not a slice.
    """
    session, (part,) = await rehearsed_in_parts(db_session, 1)
    told = await stretch_on(db_session, session, part)
    was = (told.id, told.take_id, told.starts_ms, told.ends_ms, told.tellings)
    elsewhere = await another_rehearsal_take(db_session, session, sha256="f" * 64)
    elsewhere_id = elsewhere.id
    retro_before = await _take_ids(db_session, session.id, kind=IRTakeKind.RETRO)

    refused = await _replace(
        client, session.id, was[0], take_id=elsewhere_id, starts_ms=0, ends_ms=PART_MS
    )

    assert refused.status_code == 400, refused.text
    said = refused.json()["detail"]
    assert was[1] in said, "a recusa nomeia a gravação em que o trecho está"
    assert elsewhere_id in said, "e a que o pedido nomeou"
    for word in RETIRED_WORDS:
        assert word not in said.lower(), f"a razão não fala de {word}"
    assert await _take_ids(db_session, session.id, kind=IRTakeKind.RETRO) == retro_before, (
        "nada foi guardado para um pedido que termina em recusa"
    )
    assert [
        (one.id, one.take_id, one.starts_ms, one.ends_ms, one.tellings)
        for one in await _standing(db_session, session.id)
    ] == [was], "o trecho continua de pé onde estava"


# ---------------------------------------------------------------------------
# 3. A correction addressed at another range of its own recording
# ---------------------------------------------------------------------------


async def test_a_replacement_over_a_moved_range_of_its_own_recording_is_refused(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """The recording is not the slice: naming the right file at the wrong seconds moves it too.

    A stretch is a slice of one recording (ADR 0005), so a version keeping the file and moving
    the milliseconds is a version of somebody else's audio under this stretch's id. The same
    refusal answers it, and it is the case that makes the message say the seconds and not only
    the recording.
    """
    session, (part,) = await rehearsed_in_parts(db_session, 1)
    told = await stretch_on(db_session, session, part)
    was = (told.id, told.starts_ms, told.ends_ms)
    take_id = part.id
    retro_before = await _take_ids(db_session, session.id, kind=IRTakeKind.RETRO)

    refused = await _replace(
        client,
        session.id,
        was[0],
        take_id=take_id,
        starts_ms=was[1] + A_LITTLE_MS,
        ends_ms=was[2],
    )

    assert refused.status_code == 400, refused.text
    assert refused.json()["detail"] == (
        f"The slice from {was[1] + A_LITTLE_MS} ms to {was[2]} ms of {take_id} "
        f"is not this stretch's: it sits from {was[1]} ms to {was[2]} ms of {take_id}"
    ), "a razão inteira: a fatia que o pedido pediu, e a fatia em que o trecho está"
    assert await _take_ids(db_session, session.id, kind=IRTakeKind.RETRO) == retro_before, (
        "nada foi guardado"
    )
    assert [
        (one.id, one.starts_ms, one.ends_ms) for one in await _standing(db_session, session.id)
    ] == [was], "o trecho continua de pé onde estava"


# ---------------------------------------------------------------------------
# 4. The rule underneath, with no route in front of it
# ---------------------------------------------------------------------------


async def test_the_service_refuses_a_version_that_moves_the_slice(
    db_session: AsyncSession,
) -> None:
    """The rule is the service's, and it does not ask whether words came with the request.

    The route refuses this before anything is kept, which is right and is covered above — but
    it means the guard underneath is never reached from there, and a second layer nobody
    exercises is a line somebody deletes in a refactor with nothing to say so. `capture_segment`
    is called from more than one place already.

    Two shapes go straight at the service, and which words came with them is the point. The
    rule that stood here made the answer depend on the telling — a moved slice carrying words
    was refused, a moved slice arriving bare was written — so a version with no words is the
    case that would go green again if that condition ever came back.

    They also take the two dimensions a slice can move in: the one carrying words names another
    recording, the one carrying none keeps the recording and moves the milliseconds. The route
    short-circuits both before the service is reached, so this is the only place either is asked
    of `capture_segment` itself.
    """
    session, (part,) = await rehearsed_in_parts(db_session, 1)
    told = await stretch_on(db_session, session, part)
    elsewhere = await another_rehearsal_take(db_session, session, sha256="f" * 64)

    with pytest.raises(ValidationError) as carrying_words:
        await capture_segment(
            db_session,
            session,
            take_id=elsewhere.id,
            starts_ms=0,
            ends_ms=PART_MS,
            bridge_take_id="retro-de-novo",
            transcript="o trecho contado outra vez",
            replaces=told,
        )

    with pytest.raises(ValidationError) as carrying_none:
        await capture_segment(
            db_session,
            session,
            take_id=told.take_id,
            starts_ms=told.starts_ms + A_LITTLE_MS,
            ends_ms=told.ends_ms,
            replaces=told,
        )

    assert elsewhere.id in str(carrying_words.value), "nomeia a gravação que o pedido deu"
    assert str(carrying_none.value) == (
        f"The slice from {told.starts_ms + A_LITTLE_MS} ms to {told.ends_ms} ms "
        f"of {told.take_id} is not this stretch's: "
        f"it sits from {told.starts_ms} ms to {told.ends_ms} ms of {told.take_id}"
    ), "e a razão inteira quando o que se move são os milissegundos"
    assert [one.id for one in await _standing(db_session, session.id)] == [told.id], (
        "e a recusa não mexeu no que estava lá"
    )


# ---------------------------------------------------------------------------
# 5. The correction that is left
# ---------------------------------------------------------------------------


async def test_the_short_way_over_the_same_slice_is_one_more_telling(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """The stretch told again over the recording it already sits in: the one correction left.

    It supersedes the row it corrects and adds to the count of tellings on it. The **Pass** is
    carried across and not raised: the pass is which reading of the passage the team is on, and
    correcting a stretch is the same reading told better — the tablet is what says a telling is
    a retell, on the route that tells back.

    Nothing is assembled around it: the recording the team performed is the one that travels
    (ADR 0025), so the answer names no rebuilt passage.
    """
    session, (part,) = await rehearsed_in_parts(db_session, 1)
    told = await stretch_on(db_session, session, part)
    was = (told.id, told.pass_number, told.tellings, told.starts_ms, told.ends_ms)
    take_id = part.id

    answered = await _replace(
        client, session.id, was[0], take_id=take_id, starts_ms=was[3], ends_ms=was[4]
    )

    assert answered.status_code == 200, answered.text
    assert answered.json()["captured"] is True, "a correção foi guardada"
    assert answered.json().get("composed_take_id") is None, "nada foi montado à volta dela"
    standing = await _standing(db_session, session.id)
    assert len(standing) == 1
    assert standing[0].id != was[0], "a correção é uma linha nova, nunca uma edição"
    assert standing[0].pass_number == was[1], "o passe é o mesmo: a mesma leitura, contada melhor"
    assert standing[0].tellings == was[2] + 1, "e é mais uma contagem do trecho"
    assert standing[0].take_id == take_id
    assert (standing[0].starts_ms, standing[0].ends_ms) == (was[3], was[4])

    retired = await db_session.get(IRSegment, was[0], populate_existing=True)
    assert retired is not None and retired.superseded_by_id == standing[0].id, (
        "e a linha que ela corrige aponta para ela"
    )


# ---------------------------------------------------------------------------
# 6. What the harness builds when a part is recorded again
# ---------------------------------------------------------------------------


async def test_a_part_recorded_again_is_the_upload_under_its_number_in_the_harness(
    db_session: AsyncSession,
) -> None:
    """The harness builds a part recorded again the way the product does, and no other way.

    It used to build it out of the path this slice deletes: a version pointing at a fresh
    recording, which is the very thing a version may not be. Pinned here so a future change
    cannot quietly rebuild that chain under the four cases that stand on this builder — those
    read takes and stretches, and would go on passing over a shape the product cannot reach.

    The verb is the upload under the part's number, which retires that part's stretches and
    leaves every other part alone (ADR 0023). The fresh recording is therefore untold, and the
    team telling it back is the second call.
    """
    session, (one, two, three) = await rehearsed_in_parts(db_session, 3)
    was = {part.id: (await stretch_on(db_session, session, part)).id for part in (one, two, three)}
    numbers = (one.id, two.id, three.id, two.ordinal)

    fresh = await record_the_part_again(db_session, session, two, sha256="z" * 64)
    fresh_id, fresh_ordinal = fresh.id, fresh.ordinal

    parts = current_parts(await _fresh_takes(db_session, session.id))
    assert sorted(part.id for part in parts) == sorted([numbers[0], fresh_id, numbers[2]]), (
        "as partes correntes são três, e a da parte dois é a gravação nova"
    )
    assert fresh_ordinal == numbers[3], "e entra sob o número que a parte já tinha"
    standing = await _standing(db_session, session.id)
    assert sorted(stretch.id for stretch in standing) == sorted(
        [was[numbers[0]], was[numbers[2]]]
    ), "as partes um e três ficam com os trechos que tinham, e a dois com nenhum"
    abandoned = await db_session.get(IRSegment, was[numbers[1]], populate_existing=True)
    assert abandoned is not None and abandoned.superseded_at is not None
    assert abandoned.superseded_by_id is None, "abandonado, não substituído por coisa nenhuma"

    await tell_back_about(
        db_session, session, await take_by_id(db_session, fresh_id), bridge_take_id="retro-de-novo"
    )

    on_the_fresh = [
        stretch
        for stretch in await _standing(db_session, session.id)
        if stretch.take_id == fresh_id
    ]
    assert len(on_the_fresh) == 1
    assert on_the_fresh[0].pass_number == 1, "a parte gravada de novo é contada da primeira vez"
    assert on_the_fresh[0].transcript is not None


# ---------------------------------------------------------------------------
# 7. The third telling of a stretch asks for a person
# ---------------------------------------------------------------------------


async def test_the_third_telling_over_the_same_slice_asks_for_a_person(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """A correction spends the retell budget, and the room stops to offer a person.

    `RETELLS_BEFORE_A_WARNING` exists so a team never gets stuck telling the same stretch over
    and over with nobody to ask. It was charged on the telling-back route alone, and corrections
    do not go through there — so the one limit the room has against trapping a team did not
    cover the path they actually correct by. Told once and corrected twice is three tellings,
    and the third is the one that answers.
    """
    session, (part,) = await rehearsed_in_parts(db_session, 1)
    told = await stretch_on(db_session, session, part)
    its_slice = (part.id, told.starts_ms, told.ends_ms)

    standing = told.id
    answers = []
    for _ in range(RETELLS_BEFORE_A_WARNING - told.tellings):
        answered = await _replace(
            client,
            session.id,
            standing,
            take_id=its_slice[0],
            starts_ms=its_slice[1],
            ends_ms=its_slice[2],
        )
        assert answered.status_code == 200, answered.text
        answers.append(answered.json())
        standing = (await _standing(db_session, session.id))[0].id

    assert [one["needs_person"] for one in answers] == [False, True], (
        "a sala só pede alguém na contagem em que o trecho vira difícil, e não antes"
    )
    assert [one.tellings for one in await _standing(db_session, session.id)] == [
        RETELLS_BEFORE_A_WARNING
    ]
