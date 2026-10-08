import asyncio
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.db.models.internalization_room import IRSession
from app.services.internalization_room.canon.elements import element_keys
from app.services.internalization_room.coverage import CoverageStatus
from app.services.internalization_room.sessions import (
    apply_coverage,
    is_panorama,
    session_is_done,
)


async def advance(db: AsyncSession, session: IRSession) -> None:
    await apply_coverage(
        db,
        session.id,
        dict.fromkeys(element_keys(session.pericope), CoverageStatus.ENGAGED.value),
    )


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

        await advance(db, session)

        print(f"sessao {session.id}")
        print(f"pericope {session.pericope}")
        print(f"done: {session_is_done(session)} | status: {session.status.value}")


if __name__ == "__main__":
    asyncio.run(main())
