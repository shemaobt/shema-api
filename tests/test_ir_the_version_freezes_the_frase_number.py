"""A **Version** freezes the **Frase number** beside the stretch it was given to.

The number the team heard the voice say — *"na frase 3, vocês traduziram…"* — is a position
in one reading, and every reading renumbers: a cut makes a fourth frase out of three, a fresh
telling starts the count over. A listener's comment filed against frase 3 has to keep meaning
what it meant, so the pairing of the number and the stretch is frozen when the team approves
and read back out of that **Release**, never recomputed from the rows.

These cases move the passage in the three ways the room offers after an approval — a cut, a
telling again in place, the telling-back started over — and ask the stored packet of the
version before it what it still says. They also ask which retro take a frozen stretch names,
because the number is only half of the address: the other half is the recording of the team
explaining it, and the room keeps three kinds of retro take that explained nothing the
version carries.

Everything goes through `approve_release` and the room's own services. Nothing is mocked.
"""

from __future__ import annotations

from hashlib import sha256

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRRelease, IRSegment, IRSession, IRTake
from app.services.internalization_room.back_translation import (
    BackTranslationState,
    Finding,
    FindingKind,
    current_findings,
    findings_remaining,
    segments_block,
)
from app.services.internalization_room.release import (
    InternalizationReleaseBlocked,
    approve_release,
)
from app.services.internalization_room.segments import (
    capture_segment,
    divide_segment,
    final_segments,
)
from app.services.internalization_room.sessions import (
    back_translation_of,
    begin_back_translation_again,
)
from tests.release_harness import (
    P,
    ready_session,
    reported_playback,
    retro_take,
)
from tests.room_harness import a_piece_still_to_be_told

TEAM = "equipe-de-rute"
TABLET = "tablet-1"
REHEARSAL = "ensaio-1"
CLIP_MS = 61000

#: One rehearsal told back in three stretches, each a slice of the same recording. The texts
#: are the team's own words and the numbers are milliseconds inside that one file.
THREE_STRETCHES = (
    ("Noemi ouviu que o Senhor tinha visitado o seu povo", 0, 20000),
    ("ela saiu do lugar onde estava com as duas noras", 20000, 40000),
    ("e puseram-se a caminho para voltar a Juda", 40000, CLIP_MS),
)


def _frozen(release: IRRelease) -> list[dict]:
    return release.packet["back_translation"]["segments"]


async def _a_retro_take(
    db: AsyncSession, session: IRSession, name: str, *, ordinal: int | None = None
) -> IRTake:
    """One recording of the team explaining a stretch, as a row of its own.

    `name` only has to tell the takes of a case apart; it fills the hash the storage key is
    built from, which is unique per session.
    """
    take = retro_take(session.id, sha256=sha256(name.encode()).hexdigest(), ordinal=ordinal)
    db.add(take)
    await db.commit()
    return take


async def _read(
    db: AsyncSession, session: IRSession, findings: tuple[Finding, ...] = ()
) -> BackTranslationState:
    """The state one whole reading of every stretch that counts leaves behind."""
    told = await final_segments(db, session.id)
    return BackTranslationState(
        scope=P,
        findings=list(findings),
        checked=not findings,
        analysed_segment_ids=[stretch.id for stretch in told],
    )


async def _read_and_reported(
    db: AsyncSession, session: IRSession, findings: tuple[Finding, ...] = ()
) -> BackTranslationState:
    """The same reading, stored with the team's report of what the tablet played."""
    state = await _read(db, session, findings)
    await reported_playback(db, session, state)
    return state


async def _three_stretches(db: AsyncSession, session: IRSession) -> BackTranslationState:
    """The passage told back in three stretches of one rehearsal.

    Each on a retro take of its own, because which take gave a stretch its words is half of
    what a frozen entry says.
    """
    for text, starts_ms, ends_ms in THREE_STRETCHES:
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


async def _told_in_three_stretches(db: AsyncSession) -> IRSession:
    """A session the team could approve, told back in three stretches."""
    return await ready_session(db, project_id=TEAM, tell=_three_stretches)


async def _tell_again(
    db: AsyncSession, session: IRSession, stretch: IRSegment, retro: IRTake, text: str
) -> IRSegment:
    """The team tells one stretch again over the same slice: a new row for the same position."""
    return await capture_segment(
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


async def _stored_again(db: AsyncSession, release: IRRelease) -> IRRelease:
    """The release row as the database holds it now, not as this session remembers it."""
    await db.refresh(release)
    return release


@pytest.mark.asyncio
async def test_the_approved_packet_numbers_every_stretch_from_one_in_listening_order(
    db_session: AsyncSession,
) -> None:
    """The acceptance criterion: the packet carries the number the reading gave each stretch.

    Contiguous from one, in the order the team told them — the same enumeration the analyst
    was given, which is what makes the number in the snapshot the number the voice said — and
    beside it the one retro take that gave the stretch its words.
    """
    session = await _told_in_three_stretches(db_session)
    told = await final_segments(db_session, session.id)

    release = await approve_release(db_session, session, device_id=TABLET)
    approved = [dict(entry) for entry in _frozen(release)]

    assert [entry["frase"] for entry in approved] == [1, 2, 3]
    assert [entry["segment_id"] for entry in approved] == [stretch.id for stretch in told]
    assert [entry["retro_take_id"] for entry in approved] == [
        stretch.bridge_take_id for stretch in told
    ]

    stored = await _stored_again(db_session, release)
    assert _frozen(stored) == approved, (
        "o que a equipe aprovou é o que ficou na linha, e é de lá que um ouvinte lê"
    )


@pytest.mark.asyncio
async def test_a_cut_after_the_approval_appears_only_in_the_next_version(
    db_session: AsyncSession,
) -> None:
    """Cutting frase 2 in two makes four frases — in version two, and nowhere else.

    Version one was approved over three stretches and says so for good: a comment filed
    against its frase 3 still reaches the stretch the team heard third.
    """
    session = await _told_in_three_stretches(db_session)
    first = await approve_release(db_session, session, device_id=TABLET)
    before = [stretch.id for stretch in await final_segments(db_session, session.id)]

    for half in await divide_segment(
        db_session, session, (await final_segments(db_session, session.id))[1], at_ms=30000
    ):
        retro = await _a_retro_take(db_session, session, f"retro-metade-{half.starts_ms}")
        await _tell_again(db_session, session, half, retro, "o que a equipe contou desta metade")
    await _read_and_reported(db_session, session)

    second = await approve_release(db_session, session, device_id=TABLET)

    assert second.version == 2
    frozen = _frozen(second)
    assert [entry["frase"] for entry in frozen] == [1, 2, 3, 4]
    assert len({entry["segment_id"] for entry in frozen}) == 4
    assert (frozen[0]["segment_id"], frozen[3]["segment_id"]) == (before[0], before[2]), (
        "as metades entram onde estava a frase que foi cortada, não no fim da leitura"
    )

    stored = await _stored_again(db_session, first)
    assert [entry["frase"] for entry in _frozen(stored)] == [1, 2, 3]
    assert [entry["segment_id"] for entry in _frozen(stored)] == before


@pytest.mark.asyncio
async def test_a_stretch_told_again_in_place_keeps_its_frase_in_the_next_version(
    db_session: AsyncSession,
) -> None:
    """Telling frase 2 again leaves it frase 2, on a new row and a new retro take.

    A correction is a new row for the same position (ADR 0004), so the stretch the team told
    again has an id it did not have before. The number is what did not move, and version one
    keeps the pair it froze.
    """
    session = await _told_in_three_stretches(db_session)
    first = await approve_release(db_session, session, device_id=TABLET)
    before = [stretch.id for stretch in await final_segments(db_session, session.id)]

    retro = await _a_retro_take(db_session, session, "retro-outra-vez")
    await _tell_again(
        db_session,
        session,
        (await final_segments(db_session, session.id))[1],
        retro,
        "desta vez elas ouviram que havia pao em Juda",
    )
    await _read_and_reported(db_session, session)

    second = await approve_release(db_session, session, device_id=TABLET)

    told_now = await final_segments(db_session, session.id)
    frozen = _frozen(second)
    assert [entry["frase"] for entry in frozen] == [1, 2, 3]
    assert frozen[1]["segment_id"] == told_now[1].id
    assert frozen[1]["segment_id"] != before[1]
    assert frozen[1]["retro_take_id"] == retro.id
    assert (frozen[0]["segment_id"], frozen[2]["segment_id"]) == (before[0], before[2])

    stored = await _stored_again(db_session, first)
    assert [entry["segment_id"] for entry in _frozen(stored)] == before
    assert [entry["frase"] for entry in _frozen(stored)] == [1, 2, 3]


@pytest.mark.asyncio
async def test_starting_the_telling_back_over_numbers_only_the_next_version(
    db_session: AsyncSession,
) -> None:
    """The team threw the recording away and told the passage back again, from the top.

    Every stretch of version one stopped counting and three new ones were told, so the second
    approval numbers three stretches nobody had seen. Version one is untouched: its frases
    still name the stretches that were abandoned.
    """
    session = await _told_in_three_stretches(db_session)
    first = await approve_release(db_session, session, device_id=TABLET)
    before = [stretch.id for stretch in await final_segments(db_session, session.id)]

    await begin_back_translation_again(db_session, session)
    for text, starts_ms, ends_ms in THREE_STRETCHES:
        retro = await _a_retro_take(db_session, session, f"retro-de-novo-{starts_ms}")
        await capture_segment(
            db_session,
            session,
            take_id=REHEARSAL,
            starts_ms=starts_ms,
            ends_ms=ends_ms,
            bridge_take_id=retro.id,
            transcript=text,
        )
    await _read_and_reported(db_session, session)

    second = await approve_release(db_session, session, device_id=TABLET)

    assert second.version == 2
    assert [entry["frase"] for entry in _frozen(second)] == [1, 2, 3]
    assert {entry["segment_id"] for entry in _frozen(second)}.isdisjoint(before)

    stored = await _stored_again(db_session, first)
    assert [entry["segment_id"] for entry in _frozen(stored)] == before
    assert [entry["frase"] for entry in _frozen(stored)] == [1, 2, 3]


@pytest.mark.asyncio
async def test_a_standing_finding_keeps_its_stretch_when_frase_three_is_divided(
    db_session: AsyncSession,
) -> None:
    """Cutting frase 3 while two findings stand on it moves neither of them.

    The number on a finding is the number the analyst gave it, and the analyst is numbered off
    the same list the packet freezes — so while nothing has been divided since that reading,
    a standing finding's `chunk` **is** the stretch's `frase`, which is what this asks first.

    Then a finding keeps `segment_id`, the stretch it was about, and keeps `chunk` beside it
    (ADR 0018). The cut renumbers the reading and nothing else, so the two go on naming the
    stretch the team has to record again — and they go on not being a swap, which is joined on
    the frase and not on the stretch: the addition was told under frase 3, and the missing
    element was placed after frase 2, which is where frase 3 begins (ADR 0007, pinned by
    `test_ir_a_missing_element_says_where_it_goes.py`).
    """
    session = await _told_in_three_stretches(db_session)
    told = await final_segments(db_session, session.id)
    third = told[2]
    release = await approve_release(db_session, session, device_id=TABLET)
    numbered = [line.split(". ", 1)[0] for line in segments_block(told).splitlines()]
    assert numbered == [str(entry["frase"]) for entry in _frozen(release)], (
        "a analista e o pacote contam a mesma lista, senão o número do achado não é a frase"
    )

    await _read_and_reported(
        db_session,
        session,
        (
            Finding(
                kind=FindingKind.ADDITION,
                note="disseram que elas choraram alto",
                segment_id=third.id,
                chunk=3,
            ),
            Finding(
                kind=FindingKind.MISSING,
                note="nao disseram que voltaram para Juda",
                segment_id=third.id,
                chunk=2,
            ),
        ),
    )
    frase_of_the_third = _frozen(release)[2]["frase"]
    addition, missing = back_translation_of(session).findings
    assert addition.chunk == frase_of_the_third
    assert missing.chunk + 1 == frase_of_the_third, "depois da frase 2 é onde a frase 3 começa"

    halves = await divide_segment(db_session, session, third, at_ms=50000)

    standing = back_translation_of(session).findings
    assert [finding.segment_id for finding in standing] == [third.id, third.id]
    assert {half.id for half in halves}.isdisjoint({finding.segment_id for finding in standing})
    assert findings_remaining(standing) == 2
    assert len(current_findings(back_translation_of(session))) == 1, (
        "dois achados de frases diferentes não são uma troca, e uma troca falaria os dois"
    )


async def _every_shape_of_retro_take(
    db: AsyncSession,
) -> tuple[IRSession, dict[str, IRTake], dict[str, str]]:
    """A session holding, beside the takes that gave the version its words, the three that did not.

    The first stretch was told again, so its first retro take hangs on a row that stopped
    counting. The second was told again into a recording nobody could make out: the route
    stores the take at the stretch's number and captures nothing, which is the row written
    here directly; the route's own shape is pinned in
    `test_internalization_room_segment_verbs.py`, by the case about the count being spent on
    the attempt and not on the result.

    The third was divided, so the take that explained the whole of it belongs to a
    stretch that is no longer a unit, and each half was told on a take of its own.
    """
    session = await _told_in_three_stretches(db)
    told = await final_segments(db, session.id)
    superseded_take, second_take, divided_take = (stretch.bridge_take_id for stretch in told)

    told_again = await _a_retro_take(db, session, "retro-primeira-de-novo")
    await _tell_again(db, session, told[0], told_again, "Noemi ouviu falar do povo dela")

    heard_nothing = await _a_retro_take(db, session, "retro-sem-palavra", ordinal=told[1].ordinal)

    halves = await divide_segment(db, session, told[2], at_ms=50000)
    half_takes = []
    for half in halves:
        retro = await _a_retro_take(db, session, f"retro-metade-{half.starts_ms}")
        await _tell_again(db, session, half, retro, "o que a equipe contou desta metade")
        half_takes.append(retro)
    await _read_and_reported(db, session)

    takes = {
        take.id: take
        for take in (await db.execute(select(IRTake).where(IRTake.session_id == session.id)))
        .scalars()
        .all()
    }
    return (
        session,
        {
            "superseded": takes[superseded_take],
            "second": takes[second_take],
            "divided_parent": takes[divided_take],
            "empty": heard_nothing,
            "told_again": told_again,
            "head": half_takes[0],
            "tail": half_takes[1],
        },
        {"retold": told[0].id, "divided": told[2].id},
    )


@pytest.mark.asyncio
async def test_a_superseded_an_empty_and_a_divided_parents_retro_take_never_enter_the_frozen_list(
    db_session: AsyncSession,
) -> None:
    """A frozen stretch names the one recording that gave it its words, and no other.

    Three retro takes of this session explained nothing the version carries: one hangs on a
    telling the team replaced, one told nothing at all, and one explained a stretch the team
    then cut in two. They stay in the packet as history, because the team recorded them and
    that is the record; none of them is what a frozen stretch points at.
    """
    session, takes, set_aside = await _every_shape_of_retro_take(db_session)

    release = await approve_release(db_session, session, device_id=TABLET)

    assert [entry["retro_take_id"] for entry in _frozen(release)] == [
        takes["told_again"].id,
        takes["second"].id,
        takes["head"].id,
        takes["tail"].id,
    ]
    never = {takes[name].id for name in ("superseded", "empty", "divided_parent")}
    assert never.isdisjoint({entry["retro_take_id"] for entry in _frozen(release)})
    assert never <= {
        take["take_id"] for take in release.packet["back_translation"]["retro_takes"]
    }, "a história fica: a equipe gravou, e o pacote guarda o que ela gravou"

    aside = (
        release.packet["back_translation"]["superseded_segments"]
        + release.packet["back_translation"]["divided_segments"]
    )
    named = {entry["segment_id"]: entry for entry in aside}
    assert named[set_aside["retold"]]["retro_take_id"] == takes["superseded"].id
    assert named[set_aside["divided"]]["retro_take_id"] == takes["divided_parent"].id
    assert all("retro_take_id" in entry for entry in aside), (
        "uma vista, uma forma: quem saiu da leitura ainda diz em que gravação foi explicado"
    )
    assert all("frase" not in entry for entry in aside), (
        "nenhuma delas esteve na leitura que a equipe ouviu, e ausente não é nulo"
    )


@pytest.mark.asyncio
async def test_frase_and_segment_id_are_each_unique_within_a_version(
    db_session: AsyncSession,
) -> None:
    """Inside one version the number and the stretch answer for each other, exactly once.

    That is the whole of what the pairing promises a reader: a comment filed against a frase
    reaches one stretch, and a stretch shown on a screen has one number to say out loud. Asked
    of the row the approval stored, over a passage that was told again, cut and told again —
    the three ways a stretch can be written twice, which is where a repeated number would come
    from.
    """
    session, _, _ = await _every_shape_of_retro_take(db_session)

    release = await approve_release(db_session, session, device_id=TABLET)
    frozen = _frozen(await _stored_again(db_session, release))

    assert [entry["frase"] for entry in frozen] == list(range(1, len(frozen) + 1))
    assert len({entry["segment_id"] for entry in frozen}) == len(frozen)


@pytest.mark.asyncio
async def test_a_stretch_left_untold_by_a_cut_cannot_be_approved(
    db_session: AsyncSession,
) -> None:
    """An approved version does not let the approval after it through on a stretch without words.

    That a wordless stretch refuses a release at all is
    `test_ir_no_stretch_travels_without_words.py::test_a_release_is_refused_while_a_stretch_has_no_words`,
    which asserts the whole blocker list. What is here is the version beside it: the team has
    already approved once, so the refusal has to hold on the path that mints the *next*
    number, and hold without disturbing the one already frozen. That is what lets every other
    case here assume a frozen stretch has words.
    """
    session = await _told_in_three_stretches(db_session)
    first = await approve_release(db_session, session, device_id=TABLET)

    standing = (await final_segments(db_session, session.id))[0]
    await a_piece_still_to_be_told(db_session, session, standing)

    with pytest.raises(InternalizationReleaseBlocked) as refused:
        await approve_release(db_session, session, device_id=TABLET)

    assert "untold_stretch" in refused.value.blockers
    versions = (
        (
            await db_session.execute(
                select(IRRelease.version).where(IRRelease.session_id == session.id)
            )
        )
        .scalars()
        .all()
    )
    assert list(versions) == [first.version], "nada foi numerado por cima do que já está frio"
