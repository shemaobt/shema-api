"""The rows a release case needs before it can ask the packet anything.

A session the room would let the team approve — comprehension supported, coverage met, a
rehearsal recorded, a stretch told back and read, the playback reported — assembled through
the room's own write paths so every case starts from state the field could produce.

Shared by the cases about the artifact, the frozen numbers, the gate a facilitator forces and
the check block the packet carries, which is why it is here and not in any of them. What a
case lends another lives here; fixtures never travel, so each module keeps its own three-line
fixture calling these.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room._deps import DEVICE_CREDENTIAL_HEADER
from app.core.enums import ProjectRole
from app.db.models.auth import App, Role, User
from app.db.models.internalization_room import (
    IRRelease,
    IRSession,
    IRTake,
    IRTakeKind,
)
from app.db.models.project import Project
from app.models.internalization_room import PlayedTake
from app.services.device import claim_device_as_facilitator, create_device
from app.services.internalization_room.back_translation import (
    BackTranslationState,
    Finding,
    FindingKind,
)
from app.services.internalization_room.canon.elements import element_keys
from app.services.internalization_room.comprehension.checkpoints import (
    checkpoints_for,
    scene_ids_for,
)
from app.services.internalization_room.comprehension.evidence import (
    EvidenceMethod,
    EvidenceObservation,
    EvidenceResult,
)
from app.services.internalization_room.comprehension.state import ComprehensionState
from app.services.internalization_room.coverage import initial_state, merge
from app.services.internalization_room.segments import capture_segment, final_segments
from app.services.internalization_room.sessions import (
    back_translation_of,
    create_session,
    report_playback,
    save_comprehension,
)
from tests.baker import (
    make_language,
    make_project,
    make_project_user_access,
    make_user,
    make_user_app_role,
)

P = "P03"

#: The passage of Marcia's live test, and the one whose map names an act of God the team can
#: swap away: P02 is Ruth 1:6-14.
P02 = "P02"
CLIP_MS = 61000

PREFIX = "/api/internalization-room"
KEY = "sala-de-teste"
APP_KEY = "internalization-room"

#: What the team said on frase 1, and what the story says instead. Scene 1 of
#: `canon/vendor/meaning-map/P02-Ruth-1-6-14.md` has Naomi hear in the fields of Moab that
#: YHWH has visited his people in giving them bread, and rise to return. Putting the
#: daughters-in-law in that place is an addition that also erases rule R1 of
#: `canon/vendor/compilation-log/P02-Ruth-1-6-14-COMPILATION-LOG.md`, marked `do_not_decide`:
#: the reconstructor must preserve the divine subject as the agent of the bread-provision.
SWAPPED_CAUSE = "Noemi decidiu voltar para Judá porque as noras pediram"
THE_FINDING = (
    "a equipe trocou quem faz a coisa: o que move Noemi é a notícia de que YHWH visitou o "
    "seu povo dando-lhe pão, e o pedido das noras entrou no lugar disso (regra R1)"
)

#: The tablet the team approves from. Self-issued and unauthenticated like every other
#: room write: it says which device did this and never which team, which the credential
#: beside it is what answers.
TABLET = "tablet-da-sala"


def team_headers(credential: str) -> dict[str, str]:
    """What a tablet calls the room's own routes with."""
    return {
        "X-Room-Key": KEY,
        DEVICE_CREDENTIAL_HEADER: credential,
        "X-Room-Device": TABLET,
    }


async def a_claimed_device(
    db: AsyncSession, *, email: str = "fac@example.com"
) -> tuple[Project, str]:
    """A device linked to a project, and the credential it calls the room with."""
    user = await make_user(db, email=email)
    language = await make_language(db, name=f"Lang {email}", code=email[:3])
    project = await make_project(db, language.id, name=f"Team {email}")
    await make_project_user_access(db, project.id, user.id, role=ProjectRole.FACILITATOR)
    minted = await create_device(db)
    claimed = await claim_device_as_facilitator(
        db, user=user, code=minted.claim_code, project_id=project.id
    )
    return project, claimed.credential


async def releases_of(db: AsyncSession, session_id: str) -> list[IRRelease]:
    """Every release this session wrote, in the order it numbered them."""
    rows = await db.execute(
        select(IRRelease).where(IRRelease.session_id == session_id).order_by(IRRelease.version)
    )
    return list(rows.scalars().all())


def supported_comprehension(pericope: str, *, carry_one: bool = False) -> ComprehensionState:
    checkpoints = list(checkpoints_for(pericope))
    ledger = []
    for index, checkpoint in enumerate(checkpoints):
        result = (
            EvidenceResult.CARRY_TO_REFINE
            if carry_one and index == 0
            else EvidenceResult.DEMONSTRATED
        )
        ledger.append(
            EvidenceObservation(
                id=f"ev-{index}",
                unit_id=checkpoint.id,
                probe_id=f"probe-{index}",
                method=EvidenceMethod.MICRO_TELLBACK,
                result=result,
            )
        )
    return ComprehensionState(
        ledger=list(ledger),
        practiced_scene_ids=scene_ids_for(pericope),
    )


async def one_stretch(db: AsyncSession, session: IRSession, text: str = "Noemi voltou com Rute"):
    return await capture_segment(
        db,
        session,
        take_id="ensaio-1",
        starts_ms=0,
        ends_ms=61000,
        bridge_take_id="retro-1",
        transcript=text,
    )


async def checked_telling_back(db: AsyncSession, session: IRSession) -> BackTranslationState:
    told = await one_stretch(db, session)
    return BackTranslationState(
        scope=P,
        findings=[],
        checked=True,
        analysed_segment_ids=[told.id],
    )


async def told_back_with_an_open_finding(
    db: AsyncSession, session: IRSession, *, note: str = "a equipe disse que Noemi voltou alegre"
) -> BackTranslationState:
    """A telling-back the team finished and chose not to resolve.

    `analysed_segment_ids` names the stretch because the analyst did read it — that is what
    makes the finding open rather than the verdict unasked.

    `checked` is written as `finding is None`, so an open finding makes it false.

    `note` is the analyst's own words. It is a parameter because one case asks where they do
    and do not travel, and a marker nothing else in the packet contains is what answers it.
    """
    told = await one_stretch(db, session)
    return BackTranslationState(
        scope=P,
        findings=[
            Finding(
                kind=FindingKind.ADDITION,
                note=note,
                segment_id=told.id,
                chunk=1,
            )
        ],
        checked=False,
        analysed_segment_ids=[told.id],
    )


async def never_analysed_telling_back(db: AsyncSession, session: IRSession) -> BackTranslationState:
    """A stretch told back that the analyst has never read.

    `analysed_segment_ids` stays None, which is what `never_analysed` asks, and the defaults it
    leaves behind — no findings, `checked` false — are the same ones a clean check produces.
    That is why the release names this state before it names an open finding.
    """
    await one_stretch(db, session)
    return BackTranslationState(scope=P)


def ensaio_take(
    session_id: str,
    *,
    scope: str = "passagem-inteira",
    pass_number: int | None = None,
    ordinal: int | None = None,
    sha256: str = "a" * 64,
    created_at: datetime | None = None,
) -> IRTake:
    take = IRTake(
        session_id=session_id,
        device_id="tablet-1",
        pericope=P,
        kind=IRTakeKind.ENSAIO,
        scope=scope,
        pass_number=pass_number,
        ordinal=ordinal,
        storage_key=f"takes/{session_id}/ensaio/{sha256}",
        size_bytes=2048,
        sha256=sha256,
        crc32c="AAAAAAA=",
        content_type="audio/mp4",
    )
    if created_at is not None:
        take.created_at = created_at
    return take


def retro_take(
    session_id: str,
    *,
    scope: str = P,
    pass_number: int | None = None,
    ordinal: int | None = None,
    sha256: str = "a" * 64,
    created_at: datetime | None = None,
) -> IRTake:
    take = IRTake(
        session_id=session_id,
        device_id="tablet-1",
        pericope=P,
        kind=IRTakeKind.RETRO,
        scope=scope,
        pass_number=pass_number,
        ordinal=ordinal,
        storage_key=f"takes/{session_id}/retro/{sha256}",
        size_bytes=2048,
        sha256=sha256,
        crc32c="AAAAAAA=",
        content_type="audio/mp4",
    )
    if created_at is not None:
        take.created_at = created_at
    return take


async def reported_playback(
    db: AsyncSession,
    session: IRSession,
    state: BackTranslationState,
    *,
    played_ranges: list[list[int]] | None = None,
    clip_duration_ms: int | None = 61000,
) -> None:
    """Store the telling-back together with the team's report of what the tablet played.

    Through the room's own write path rather than by filling the fields, because the room
    binds a report to the rehearsal it is about at the moment it arrives. A report assembled
    here would name no recording, which is a state the release is entitled to refuse.

    One entry per part the session's stretches name, each carrying the numbers this call was
    given. These sessions rehearse in one part, so the numbers that used to describe the whole
    passage are the numbers that part is measured by, and every case here keeps the verdict it
    had. The flat pair travels beside it, as a tablet still in the field sends it.

    The defaults describe a part played through; a case about a report that falls short says
    so by naming the numbers it means.
    """
    spans = [[0, 61000]] if played_ranges is None else played_ranges
    told = await final_segments(db, session.id)
    await report_playback(
        db,
        session,
        state,
        played_by_take=[
            PlayedTake(take_id=take_id, played_ranges=spans, clip_duration_ms=clip_duration_ms or 0)
            for take_id in sorted({stretch.take_id for stretch in told})
        ],
        played_ranges=spans,
        clip_duration_ms=clip_duration_ms,
    )


async def rehearsed_session(
    db: AsyncSession,
    *,
    project_id: str | None = None,
    language: str | None = None,
    **comprehension_kwargs,
) -> tuple[IRSession, IRTake]:
    """A session that has done everything a release needs except tell the passage back.

    Comprehension supported, coverage satisfied, the passage rehearsed. The take comes back
    beside the session because the stage after this one is told *about* a recording, and a
    case that has to name the part it played cannot find it by guessing.

    ``language`` is which language the room speaks to this team. It is named here only by the
    cases that were opened naming it: a session that names none takes the floor, and changing
    that under a case would change what the room answers rather than what it is asked.
    """
    session = await create_session(db, pericope=P, project_id=project_id, language=language)
    session.coverage_state = merge(initial_state(P), pericope_num=P, engaged=element_keys(P))
    await save_comprehension(db, session, supported_comprehension(P, **comprehension_kwargs))
    take = ensaio_take(session.id)
    db.add(take)
    await db.commit()
    return session, take


async def ready_session(
    db: AsyncSession,
    *,
    project_id: str | None = None,
    tell: Callable[[AsyncSession, IRSession], Awaitable[BackTranslationState]] | None = None,
    **comprehension_kwargs,
):
    """A session carrying everything the packet refuses to travel without.

    The rehearsed stage above, and then what it is missing: the passage told back and the
    team's report of having played it through.

    ``project_id`` is the team whose conversation this is. It stays optional because most of
    these cases are about the packet and not about whose it is; the release is numbered per
    project, so the cases about the number name one.

    ``tell`` is what the team told back, answering the state one whole reading leaves behind;
    the default is a single stretch, read and clean. A case that needs the passage told in
    several stretches passes its own and inherits the rest of the scaffold rather than
    rebuilding it, which is the only part of this that ever differs.
    """
    session, _take = await rehearsed_session(db, project_id=project_id, **comprehension_kwargs)
    await reported_playback(db, session, await (tell or checked_telling_back)(db, session))
    return session


async def a_p02_telling_with_the_swapped_cause(db: AsyncSession, project: Project) -> IRSession:
    """A P02 session ready in every way but one: frase 1 swapped who caused the return.

    Everything the gate asks for is here — comprehension supported, the floor met, a
    rehearsal recorded, one stretch told back and read by the analyst, the whole part played
    through. The only thing between this session and Refine is the finding the team stopped
    answering.
    """
    session = await create_session(db, pericope=P02, project_id=project.id)
    session.coverage_state = merge(initial_state(P02), pericope_num=P02, engaged=element_keys(P02))
    await save_comprehension(db, session, supported_comprehension(P02))
    db.add(
        IRTake(
            session_id=session.id,
            device_id=TABLET,
            pericope=P02,
            kind=IRTakeKind.ENSAIO,
            scope="passagem-inteira",
            storage_key=f"takes/{session.id}/ensaio/b",
            size_bytes=2048,
            sha256="b" * 64,
            crc32c="AAAAAAA=",
            content_type="audio/mp4",
        )
    )
    await db.commit()
    told = await capture_segment(
        db,
        session,
        take_id="ensaio-1",
        starts_ms=0,
        ends_ms=CLIP_MS,
        bridge_take_id="retro-1",
        transcript=SWAPPED_CAUSE,
    )
    await report_playback(
        db,
        session,
        BackTranslationState(
            scope=P02,
            findings=[
                Finding(
                    kind=FindingKind.ADDITION,
                    note=THE_FINDING,
                    segment_id=told.id,
                    chunk=1,
                )
            ],
            checked=False,
            analysed_segment_ids=[told.id],
        ),
        played_by_take=[
            PlayedTake(take_id=told.take_id, played_ranges=[(0, CLIP_MS)], clip_duration_ms=CLIP_MS)
        ],
        played_ranges=[[0, CLIP_MS]],
        clip_duration_ms=CLIP_MS,
    )
    return session


async def a_rehearsal_only_half_heard(db: AsyncSession, project: Project) -> IRSession:
    """A P02 session clean in every way but one: the tablet played twenty of the sixty-one seconds.

    The telling-back is read and carries no finding, so the only thing between this session and
    Refine is the half of the rehearsal the team closed on without hearing. That is the other
    of the two blockers a facilitator's code can set aside.
    """
    session = await a_p02_telling_with_the_swapped_cause(db, project)
    state = back_translation_of(session)
    state.checked = True
    state.findings = []
    await report_playback(
        db,
        session,
        state,
        played_by_take=[
            PlayedTake(take_id="ensaio-1", played_ranges=[(0, 20000)], clip_duration_ms=CLIP_MS)
        ],
        played_ranges=[[0, 20000]],
        clip_duration_ms=CLIP_MS,
    )
    return session


async def at_the_desk(
    db: AsyncSession, room_app: App, project: Project
) -> tuple[dict[str, str], User]:
    """A facilitator of ``project``: the headers they call with, and the row they are.

    The user comes back beside the headers because a forced release is signed: ``forced_by``
    has to be provably that person and not merely some id.
    """
    from app.services.auth.issue_tokens import issue_tokens

    user = await make_user(db, email=f"desk-{uuid.uuid4()}@example.com")
    role = (
        await db.execute(
            select(Role).where(Role.app_id == room_app.id, Role.role_key == "facilitator")
        )
    ).scalar_one()
    await make_user_app_role(db, user.id, room_app.id, role.id)
    await make_project_user_access(db, project.id, user.id, role=ProjectRole.FACILITATOR)
    access, _refresh = await issue_tokens(db, user)
    return {"Authorization": f"Bearer {access}"}, user


def team_release(session_id: str) -> str:
    return f"{PREFIX}/sessions/{session_id}/release"


def desk_release(session_id: str) -> str:
    return f"{PREFIX}/facilitator/sessions/{session_id}/release"


def desk_release_at(session_id: str, version: int) -> str:
    return f"{PREFIX}/facilitator/sessions/{session_id}/releases/{version}"
