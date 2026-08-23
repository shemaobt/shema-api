import json
import sys
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models.internalization_room import IRPromptKey, IRSessionStatus
from app.services.internalization_room import sessions as service
from app.services.internalization_room._default_prompts import default_prompt
from app.services.internalization_room.canon.elements import element_keys
from app.services.internalization_room.classify_coverage import _parse, classify_coverage
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
from app.services.internalization_room.coverage import CoverageStatus, initial_state
from app.services.internalization_room.release import (
    InternalizationReleaseBlocked,
    build_internalization_release,
)

CLASSIFIER = default_prompt(IRPromptKey.COVERAGE_CLASSIFIER)["prompt"]
P = "P03"


def _settings() -> Settings:
    return Settings(database_url="sqlite+aiosqlite:///./test.db", google_api_key="fake")


def _fully_supported_comprehension(pericope: str) -> ComprehensionState:
    ledger = [
        EvidenceObservation(
            id=f"ev-{index}",
            unit_id=checkpoint.id,
            probe_id=f"probe-{index}",
            method=EvidenceMethod.MICRO_TELLBACK,
            result=EvidenceResult.DEMONSTRATED,
        )
        for index, checkpoint in enumerate(checkpoints_for(pericope))
    ]
    return ComprehensionState(
        ledger=ledger,
        practiced_scene_ids=scene_ids_for(pericope),
        recording_consent_given=True,
    )


def _whole_passage_engaged(pericope: str) -> str:
    return json.dumps(
        {
            "decisions": [
                {"element_id": key, "new_status": "engaged", "evidence": "a equipe trabalhou"}
                for key in element_keys(pericope)
            ]
        }
    )


@pytest.fixture
def patch_classifier(monkeypatch: pytest.MonkeyPatch):
    module = sys.modules["app.services.internalization_room.classify_coverage"]

    def _install(reply: str) -> None:
        async def agent(*, system_prompt: str, user_content: str, **kwargs: Any) -> str:
            return reply

        monkeypatch.setattr(module, "call_agent", agent)

    return _install


async def test_a_later_settle_does_not_darken_an_earned_bead(db_session: AsyncSession) -> None:
    session = await service.create_session(db_session, pericope=P)
    keys = element_keys(P)
    earned = dict.fromkeys(keys, CoverageStatus.NOT_ENCOUNTERED.value)
    earned[keys[0]] = CoverageStatus.ENGAGED.value
    await service.apply_coverage(db_session, session.id, earned)

    stale = dict.fromkeys(keys, CoverageStatus.NOT_ENCOUNTERED.value)
    stale[keys[1]] = CoverageStatus.SURFACED.value
    await service.apply_coverage(db_session, session.id, stale)

    assert session.coverage_state[keys[0]] == CoverageStatus.ENGAGED.value


def test_a_decision_lands_in_the_bucket_its_new_status_names() -> None:
    reply = json.dumps(
        {
            "decisions": [
                {"element_id": "scene:1", "new_status": "engaged", "evidence": "contaram a cena"},
                {"element_id": "scene:2", "new_status": "surfaced", "evidence": "o Guia citou"},
            ]
        }
    )

    verdict = _parse(reply)

    assert verdict == {"engaged": ["scene:1"], "surfaced": ["scene:2"]}, (
        "o parser lia engaged e surfaced no topo, chaves que o prompt nunca emite, "
        "e toda troca voltava com duas listas vazias"
    )


async def test_a_settled_exchange_moves_the_bead_the_classifier_named(patch_classifier) -> None:
    keys = element_keys(P)
    patch_classifier(
        json.dumps(
            {
                "decisions": [
                    {"element_id": keys[0], "new_status": "engaged", "evidence": "contaram a cena"}
                ]
            }
        )
    )

    settled = await classify_coverage(
        coverage_state=initial_state(P),
        team_utterance="a equipe contou a cena",
        guide_response="o Guia devolveu a pergunta",
        classifier_prompt=CLASSIFIER,
        pericope_num=P,
        settings=_settings(),
    )

    assert settled[keys[0]] == CoverageStatus.ENGAGED.value, (
        "a troca atravessava o classificador e voltava com o tracker intacto, "
        "então nenhuma conta do colar avançava"
    )


async def test_a_passage_settled_from_decisions_closes_the_session(
    db_session: AsyncSession, patch_classifier
) -> None:
    patch_classifier(_whole_passage_engaged(P))
    session = await service.create_session(db_session, pericope=P, bridge_mode="guided_microchecks")
    session = await service.save_comprehension(
        db_session, session, _fully_supported_comprehension(P)
    )

    settled = await classify_coverage(
        coverage_state=initial_state(P),
        team_utterance="a equipe trabalhou a passagem inteira",
        guide_response="o Guia acompanhou",
        classifier_prompt=CLASSIFIER,
        pericope_num=P,
        settings=_settings(),
    )
    session = await service.apply_coverage(db_session, session.id, settled)

    assert session.status is IRSessionStatus.DONE, (
        "o classificador nunca movia uma conta, então o piso jamais era atingido "
        "e a passagem não tinha como terminar"
    )


async def test_a_settled_passage_drops_the_coverage_blocker_from_the_release(
    db_session: AsyncSession, patch_classifier
) -> None:
    patch_classifier(_whole_passage_engaged(P))
    session = await service.create_session(db_session, pericope=P)

    settled = await classify_coverage(
        coverage_state=initial_state(P),
        team_utterance="a equipe trabalhou a passagem inteira",
        guide_response="o Guia acompanhou",
        classifier_prompt=CLASSIFIER,
        pericope_num=P,
        settings=_settings(),
    )
    session = await service.apply_coverage(db_session, session.id, settled)

    with pytest.raises(InternalizationReleaseBlocked) as blocked:
        await build_internalization_release(db_session, session)

    assert "coverage_floor_not_met" not in blocked.value.blockers, (
        "o colar ficava vazio por mais que a equipe trabalhasse, "
        "e a soltura respondia piso não atingido para sempre"
    )
