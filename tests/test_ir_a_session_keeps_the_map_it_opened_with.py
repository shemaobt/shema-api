"""ENG-1219 — a session keeps the canon it opened with until its passage is approved.

Her ruling of 1 October: «It keeps the map it was opened with until it is approved.» A new
canon is published here the way a re-pin publishes one: the canon served until then is kept
under its pin, and the room serves the vendored files at a new pin. The kept P03 map is told
in a line the vendored one does not have, so which map a turn read is read off the prompts
the voice and the Validator were handed.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models.internalization_room import IRSession
from app.services.internalization_room import background
from app.services.internalization_room.archives import archive_pericope
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
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.release import (
    approve_release,
    compose_internalization_release,
)
from app.services.internalization_room.sessions import (
    create_session,
    save_comprehension,
    session_is_done,
)
from tests.baker import make_app, make_role
from tests.canon_harness import the_canon_moves_on
from tests.opening_harness import another_tablet_of, the_tablet_opens
from tests.release_harness import P, a_claimed_device, at_the_desk, ready_session
from tests.room_harness import (
    heard_every_part,
    nothing_is_read_ahead,
    press_terminei,
    rehearsed_in_parts,
    room_client,
    the_analyst_is_scripted,
    the_bucket_is_in_memory,
    the_room_speaks,
)
from tests.tablet_turn_harness import the_team_says, the_turn_is_scripted
from tests.turn_harness import the_room_agent_is

OLD_PIN = "b" * 40
NEW_PIN = "a" * 40
VENDORED_LINE = "Close-up and slow."
KEPT_LINE = "THE KEPT MAP TELLS IT CLOSE AND SLOW."
VENDORED_P01_ARC = "The passage opens wide, on a whole era,"
KEPT_P01_ARC = "THE KEPT FIRST PASSAGE OPENS ON A WHOLE ERA,"
VENDORED_RULE = "First oath-scene in the pilot."
KEPT_RULE = "THE KEPT RULE: THE FIRST OATH-SCENE."
VENDORED_SILENCE = "Naomi names no place;"
KEPT_SILENCE = "THE KEPT SILENCE: NAOMI NAMES NO PLACE;"
BEINGS = "**3A — Beings**\n"
ELIMELECH = "[[B2-Elimelech]] — אֱלִימֶלֶךְ / Elimelech\n\n"
NAOMI_IN_THE_FIRST_SCENE = '"being_id": "B3",\n            "role_in_scene": "MOTHER_IN_LAW",'
DROPPED_BEAD = "being:S1:B2"
KEPT_FIRST_SILENCE_AT = 11
AUDIT = '"high_risk_register_audit": [\n'
KEPT_ONLY_RULE = '    {"id": "R99", "kind": "KEPT_ONLY", "note": "kept", "do_not_decide": true},\n'


def _rewrite(tree: Path, folder: str, pericope: str, old: str, new: str) -> None:
    (page,) = (tree / "vendor" / folder).glob(f"{pericope}-*.md")
    page.write_text(page.read_text(encoding="utf-8").replace(old, new))


def _the_kept_p03_is_told_its_own_way(tree: Path) -> None:
    _rewrite(tree, "meaning-map", "P03", VENDORED_LINE, KEPT_LINE)


def _the_kept_p01_opens_its_own_way(tree: Path) -> None:
    _rewrite(tree, "meaning-map", "P01", VENDORED_P01_ARC, KEPT_P01_ARC)


def _the_kept_p03_has_its_own_rule_and_silence(tree: Path) -> None:
    _rewrite(tree, "compilation-log", "P03", VENDORED_RULE, KEPT_RULE)
    _rewrite(tree, "meaning-coordinates", "P03", VENDORED_SILENCE, KEPT_SILENCE)


def _the_kept_p03_has_its_own_beings(tree: Path) -> None:
    _rewrite(tree, "meaning-map", "P03", BEINGS, BEINGS + ELIMELECH)
    names = tree / "vendor" / "registry" / "ruth.aliases.json"
    names.write_text(
        names.read_text(encoding="utf-8").replace(
            '"english": "Elimelech",', '"english": "Elimelech as kept",'
        )
    )
    (coordinates,) = (tree / "vendor" / "meaning-coordinates").glob("P03-*.md")
    coordinates.write_text(
        coordinates.read_text(encoding="utf-8").replace(
            NAOMI_IN_THE_FIRST_SCENE,
            NAOMI_IN_THE_FIRST_SCENE.replace(
                "\n", '\n            "referential_form": "STRIPPED_TO_HA_ISHAH",\n', 1
            ),
            1,
        )
    )


def _the_kept_p03_has_a_rule_of_its_own(tree: Path) -> None:
    _rewrite(tree, "compilation-log", "P03", AUDIT, AUDIT + KEPT_ONLY_RULE)


def _demonstrated(*checkpoints: str) -> ComprehensionState:
    return ComprehensionState(
        ledger=[
            EvidenceObservation(
                id=f"ev-{index}",
                unit_id=checkpoint,
                probe_id=f"probe-{index}",
                method=EvidenceMethod.MICRO_TELLBACK,
                result=EvidenceResult.DEMONSTRATED,
            )
            for index, checkpoint in enumerate(checkpoints)
        ],
        practiced_scene_ids=scene_ids_for(P),
    )


@asynccontextmanager
async def _handed(db_session: AsyncSession) -> AsyncIterator[AsyncSession]:
    yield db_session


class Prompts:
    def __init__(self) -> None:
        self.read: list[str] = []

    def since(self, start: int) -> list[str]:
        return self.read[start:]


@pytest.fixture()
def prompts(monkeypatch: pytest.MonkeyPatch) -> Prompts:
    handed = Prompts()

    async def heard(*_: Any, **__: Any) -> HeardSpeech:
        return HeardSpeech(text="Rute disse que ia junto com Noemi")

    async def model(*, system_prompt: str, user_content: str, **_: Any) -> str:
        handed.read.append(system_prompt + "\n" + user_content)
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return "O que mais voces lembram da estrada?"

    the_turn_is_scripted(monkeypatch, heard=heard, model=model)
    return handed


@pytest.fixture()
def per_request(test_engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture()
async def client(db_session: AsyncSession, per_request, monkeypatch: pytest.MonkeyPatch):
    the_bucket_is_in_memory(monkeypatch)
    the_room_speaks(monkeypatch)
    async with room_client(db_session, monkeypatch, per_request=per_request) as c:
        yield c


@pytest.fixture()
async def room_app(db_session: AsyncSession):
    app = await make_app(db_session, app_key="internalization-room", name="Internalization Room")
    await make_role(db_session, app.id, role_key="facilitator", label="Facilitator", is_system=True)
    return app


async def _pin_of(per_request: async_sessionmaker[AsyncSession], session_id: str) -> str | None:
    async with per_request() as fresh:
        return await fresh.scalar(select(IRSession.canon_pin).where(IRSession.id == session_id))


async def test_a_session_open_when_a_new_canon_is_published_still_hands_the_voice_and_the_validator_its_own_map(  # noqa: E501
    client, db_session, prompts, monkeypatch, tmp_path
) -> None:
    _, tablet = await a_claimed_device(db_session)
    _, newcomer = await a_claimed_device(db_session, email="nov@example.com")
    opened = await the_tablet_opens(client, tablet, {"pericope": P, "language": "pt"})
    await the_team_says(client, tablet, opened["session_id"], "antes")

    the_canon_moves_on(monkeypatch, tmp_path, NEW_PIN, keeping=_the_kept_p03_is_told_its_own_way)
    after = await the_tablet_opens(client, newcomer, {"pericope": P, "language": "pt"})
    await the_team_says(client, newcomer, after["session_id"], "na nova")
    start = len(prompts.read)
    await the_team_says(client, tablet, opened["session_id"], "depois")
    guide, validator = prompts.since(start)

    assert KEPT_LINE in guide, "a voz leu o mapa novo no meio da sessão"
    assert KEPT_LINE in validator, "o Validador conferiu contra o mapa novo"
    assert VENDORED_LINE not in guide and VENDORED_LINE not in validator


async def test_a_session_open_when_a_new_canon_is_published_is_held_to_its_own_never_rules_and_silences(  # noqa: E501
    client, db_session, prompts, monkeypatch, tmp_path
) -> None:
    _, tablet = await a_claimed_device(db_session)
    _, newcomer = await a_claimed_device(db_session, email="nov@example.com")
    opened = await the_tablet_opens(client, tablet, {"pericope": P, "language": "pt"})

    the_canon_moves_on(
        monkeypatch, tmp_path, NEW_PIN, keeping=_the_kept_p03_has_its_own_rule_and_silence
    )
    after = await the_tablet_opens(client, newcomer, {"pericope": P, "language": "pt"})
    await the_team_says(client, newcomer, after["session_id"], "na nova")
    start = len(prompts.read)
    await the_team_says(client, tablet, opened["session_id"], "depois")
    _, validator = prompts.since(start)

    assert KEPT_RULE in validator, "o Validador conferiu contra as regras do canon novo"
    assert KEPT_SILENCE in validator, "o Validador guardou os silêncios do canon novo"
    assert VENDORED_RULE not in validator and VENDORED_SILENCE not in validator


async def test_the_ledger_of_a_session_open_when_a_new_canon_is_published_names_its_own_beings(
    client, db_session, prompts, monkeypatch, tmp_path
) -> None:
    _, tablet = await a_claimed_device(db_session)
    _, newcomer = await a_claimed_device(db_session, email="nov@example.com")
    opened = await the_tablet_opens(client, tablet, {"pericope": P, "language": "pt"})

    the_canon_moves_on(monkeypatch, tmp_path, NEW_PIN, keeping=_the_kept_p03_has_its_own_beings)
    after = await the_tablet_opens(client, newcomer, {"pericope": P, "language": "pt"})
    await the_team_says(client, newcomer, after["session_id"], "na nova")
    start = len(prompts.read)
    await the_team_says(client, tablet, opened["session_id"], "depois")
    guide, _ = prompts.since(start)

    assert "Elimelech as kept @ S1" in guide, "a contagem perdeu a conta que o canon novo tirou"
    assert "the woman @ S1" in guide, "a conta da cena 1 levou o nome que o canon novo dá"
    assert "Naomi @ S1" not in guide


async def test_a_settle_of_a_session_open_when_a_new_canon_is_published_still_works_a_bead_the_new_canon_dropped(  # noqa: E501
    db_session, monkeypatch, tmp_path
) -> None:
    kept_session = await create_session(db_session, pericope=P)
    the_canon_moves_on(monkeypatch, tmp_path, NEW_PIN, keeping=_the_kept_p03_has_its_own_beings)
    await create_session(db_session, pericope=P)
    shown: list[str] = []

    async def classifier(*, system_prompt: str, **_: Any) -> str:
        shown.append(system_prompt)
        engaged = {"element_id": DROPPED_BEAD, "new_status": "engaged", "evidence": "Elimeleque"}
        return json.dumps({"decisions": [engaged]})

    the_room_agent_is(monkeypatch, classifier=classifier)
    monkeypatch.setattr(background, "AsyncSessionLocal", lambda: _handed(db_session))
    await background.settle_coverage(
        session_id=kept_session.id,
        turn_id="depois",
        team_utterance="Elimeleque tinha morrido",
        guide_response="E o que mais?",
        pericope_num=P,
    )
    await db_session.refresh(kept_session)

    assert any(DROPPED_BEAD in offer for offer in shown), (
        "o classificador não viu a conta do canon da sessão"
    )
    assert kept_session.coverage_state[DROPPED_BEAD] == "engaged", (
        "a conta que o canon novo tirou foi descartada no meio da sessão"
    )


async def test_a_second_tablet_joining_a_session_open_when_a_new_canon_is_published_sees_and_hears_its_canon(  # noqa: E501
    client, db_session, prompts, monkeypatch, tmp_path
) -> None:
    team, first = await a_claimed_device(db_session)
    second = await another_tablet_of(db_session, team)
    opened = await the_tablet_opens(client, first, {"pericope": P, "language": "pt"})

    the_canon_moves_on(monkeypatch, tmp_path, NEW_PIN, keeping=_the_kept_p03_has_its_own_beings)
    told = await the_team_says(client, first, opened["session_id"], "depois")
    joined = await the_tablet_opens(client, second, {"pericope": P, "language": "pt"})
    start = len(prompts.read)
    await the_team_says(client, second, joined["session_id"], "da outra")
    guide, _ = prompts.since(start)

    assert joined["session_id"] == opened["session_id"]
    assert joined["coverage"]["absence_index"] == KEPT_FIRST_SILENCE_AT, (
        "o segundo tablet desenhou o colar pelo canon novo"
    )
    assert joined["coverage"] == told.json()["coverage"]
    assert "Elimelech as kept @ S1" in guide, "o segundo tablet ouviu a voz do canon novo"


async def test_a_session_open_when_a_new_canon_is_published_is_done_only_on_its_own_canons_floor(
    db_session, monkeypatch, tmp_path
) -> None:
    kept_session = await create_session(db_session, pericope=P)
    the_canon_moves_on(monkeypatch, tmp_path, NEW_PIN, keeping=_the_kept_p03_has_a_rule_of_its_own)
    await create_session(db_session, pericope=P)
    kept_session = await save_comprehension(
        db_session,
        kept_session,
        _demonstrated(*(checkpoint.id for checkpoint in checkpoints_for(P))),
    )
    every_bead_the_new_canon_has = dict.fromkeys(element_keys(P), "engaged")

    kept_session.coverage_state = every_bead_the_new_canon_has
    short_of_its_own_rule = session_is_done(kept_session)
    kept_session.coverage_state = every_bead_the_new_canon_has | {"preserved:R99": "engaged"}

    assert short_of_its_own_rule is False, (
        "a sessão fechou sem a equipe ter trabalhado a conta do seu próprio canon"
    )
    assert session_is_done(kept_session) is True


async def test_the_release_of_a_session_open_when_a_new_canon_is_published_names_the_canon_it_worked_with(  # noqa: E501
    db_session, monkeypatch, tmp_path
) -> None:
    the_canon_moves_on(monkeypatch, tmp_path, OLD_PIN)
    kept_session = await create_session(db_session, pericope=P)
    the_canon_moves_on(monkeypatch, tmp_path, NEW_PIN, keeping=_the_kept_p03_has_a_rule_of_its_own)
    newer, _ = await compose_internalization_release(
        db_session, await create_session(db_session, pericope=P)
    )

    packet, _ = await compose_internalization_release(db_session, kept_session)

    assert packet["canon_vendor_pin"] == OLD_PIN, (
        "o pacote para o Refine nomeou um canon que a equipe nunca trabalhou"
    )
    assert packet["comprehension"]["total_units"] == newer["comprehension"]["total_units"] + 1, (
        "o pacote contou as verificações do canon novo"
    )


async def test_an_approved_passage_opened_again_in_a_new_session_reads_the_canon_current_then_and_keeps_it(  # noqa: E501
    client, db_session, room_app, prompts, monkeypatch, tmp_path
) -> None:
    team, tablet = await a_claimed_device(db_session)
    _, facilitator = await at_the_desk(db_session, room_app, team)
    approved = await ready_session(db_session, project_id=team.id)
    await approve_release(db_session, approved)

    the_canon_moves_on(monkeypatch, tmp_path, OLD_PIN)
    await archive_pericope(db_session, facilitator, project_id=team.id, pericope=P)
    reopened = await the_tablet_opens(client, tablet, {"pericope": P, "language": "pt"})
    the_canon_moves_on(monkeypatch, tmp_path, NEW_PIN, keeping=_the_kept_p03_is_told_its_own_way)
    start = len(prompts.read)
    await the_team_says(client, tablet, reopened["session_id"], "de novo")
    guide, validator = prompts.since(start)

    assert reopened["session_id"] != approved.id
    assert KEPT_LINE in guide and KEPT_LINE in validator, (
        "a nova sessão da passagem aprovada não guardou o canon com que abriu"
    )


async def test_the_ensaio_final_check_of_a_session_open_when_a_new_canon_is_published_reads_its_own_canon(  # noqa: E501
    client, db_session, prompts, monkeypatch, tmp_path
) -> None:
    nothing_is_read_ahead(monkeypatch)
    analyst = the_analyst_is_scripted(monkeypatch)
    kept_session, _ = await rehearsed_in_parts(db_session, 1)

    def kept(tree: Path) -> None:
        _the_kept_p03_is_told_its_own_way(tree)
        _the_kept_p03_has_its_own_rule_and_silence(tree)

    the_canon_moves_on(monkeypatch, tmp_path, NEW_PIN, keeping=kept)
    fresh, _ = await rehearsed_in_parts(db_session, 1)
    for session in (fresh, kept_session):
        pressed = await press_terminei(
            client, session.id, report=await heard_every_part(db_session, session.id)
        )
        assert pressed.status_code == 200, pressed.text[:300]
    read = analyst.shown[-1]

    assert KEPT_LINE in read, "a checagem do ensaio final leu o mapa novo"
    assert KEPT_RULE in read, "a checagem do ensaio final leu as regras do canon novo"
    assert KEPT_SILENCE in read, "a checagem do ensaio final leu os silêncios do canon novo"
    assert VENDORED_LINE not in read and VENDORED_RULE not in read


async def test_the_reading_ahead_of_a_session_open_when_a_new_canon_is_published_reads_its_own_canon(  # noqa: E501
    db_session, monkeypatch, tmp_path
) -> None:
    analyst = the_analyst_is_scripted(monkeypatch)
    monkeypatch.setattr(background, "AsyncSessionLocal", lambda: _handed(db_session))
    kept_session, _ = await rehearsed_in_parts(db_session, 1)
    the_canon_moves_on(monkeypatch, tmp_path, NEW_PIN, keeping=_the_kept_p03_is_told_its_own_way)
    fresh, _ = await rehearsed_in_parts(db_session, 1)

    await background.read_ahead(session_id=fresh.id)
    await background.read_ahead(session_id=kept_session.id)

    assert KEPT_LINE in analyst.shown[-1], "a leitura antecipada leu o mapa novo"
    assert VENDORED_LINE not in analyst.shown[-1]


async def test_the_story_so_far_of_a_session_open_when_a_new_canon_is_published_is_its_own_canons(
    client, db_session, prompts, monkeypatch, tmp_path
) -> None:
    _, tablet = await a_claimed_device(db_session)
    _, newcomer = await a_claimed_device(db_session, email="nov@example.com")
    opened = await the_tablet_opens(client, tablet, {"pericope": P, "language": "pt"})

    the_canon_moves_on(monkeypatch, tmp_path, NEW_PIN, keeping=_the_kept_p01_opens_its_own_way)
    after = await the_tablet_opens(client, newcomer, {"pericope": P, "language": "pt"})
    await the_team_says(client, newcomer, after["session_id"], "na nova")
    start = len(prompts.read)
    await the_team_says(client, tablet, opened["session_id"], "depois")
    guide, validator = prompts.since(start)

    assert KEPT_P01_ARC in guide, "a voz contou a história até aqui pelo canon novo"
    assert KEPT_P01_ARC in validator, "o Validador leu a história até aqui do canon novo"
    assert VENDORED_P01_ARC not in guide and VENDORED_P01_ARC not in validator


async def test_a_passage_first_opened_after_a_new_canon_records_it_and_reads_the_vendored_map_as_today(  # noqa: E501
    client, db_session, per_request, prompts, monkeypatch, tmp_path
) -> None:
    _, earlier_tablet = await a_claimed_device(db_session, email="ant@example.com")
    _, later_tablet = await a_claimed_device(db_session, email="dep@example.com")
    earlier = await the_tablet_opens(client, earlier_tablet, {"pericope": P, "language": "pt"})
    await the_team_says(client, earlier_tablet, earlier["session_id"], "antes")
    read_today = prompts.since(0)

    the_canon_moves_on(monkeypatch, tmp_path, NEW_PIN, keeping=_the_kept_p03_is_told_its_own_way)
    later = await the_tablet_opens(client, later_tablet, {"pericope": P, "language": "pt"})
    start = len(prompts.read)
    await the_team_says(client, later_tablet, later["session_id"], "depois")
    read_after = prompts.since(start)

    guide, validator = read_after
    assert await _pin_of(per_request, later["session_id"]) == NEW_PIN
    assert read_after == read_today
    assert VENDORED_LINE in guide and VENDORED_LINE in validator
    assert KEPT_LINE not in guide and KEPT_LINE not in validator
