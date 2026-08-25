import asyncio
import sys

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.db.models.internalization_room import IRSession, IRSessionStatus
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
from app.services.internalization_room.coverage import CoverageStatus
from app.services.internalization_room.sessions import is_panorama, session_is_done


async def main() -> None:
    alvo = sys.argv[1] if len(sys.argv) > 1 else None
    async with AsyncSessionLocal() as db:
        query = select(IRSession).order_by(IRSession.created_at.desc())
        if alvo and len(alvo) > 8:
            query = query.where(IRSession.id == alvo)
        elif alvo:
            query = query.where(IRSession.pericope == alvo)
        sessions = (await db.execute(query.limit(20))).scalars().all()
        session = next((s for s in sessions if not is_panorama(s.pericope)), None)
        if session is None:
            print("nenhuma sessao de passagem encontrada")
            return

        session.coverage_state = dict.fromkeys(
            element_keys(session.pericope), CoverageStatus.ENGAGED.value
        )
        ledger = [
            EvidenceObservation(
                id=f"dev-{index}",
                unit_id=checkpoint.id,
                probe_id=f"dev-probe-{index}",
                method=EvidenceMethod.MICRO_TELLBACK,
                result=EvidenceResult.DEMONSTRATED,
                note="atalho de desenvolvimento — nao e evidencia de campo",
            )
            for index, checkpoint in enumerate(checkpoints_for(session.pericope))
        ]
        session.comprehension = ComprehensionState(
            ledger=list(ledger),
            practiced_scene_ids=scene_ids_for(session.pericope),
            recording_consent_given=True,
        ).model_dump(mode="json")
        if session.bridge_mode == "calibration_pending":
            session.bridge_mode = "adaptive"
        session.status = IRSessionStatus.DONE
        await db.commit()

        print(f"sessao {session.id}")
        print(f"pericope {session.pericope} | bridge_mode {session.bridge_mode}")
        print(f"done: {session_is_done(session)} | status: {session.status.value}")


asyncio.run(main())
