from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models import GuidanceSession, TutorTurn


async def test_session_and_turn_roundtrip():
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        gs = GuidanceSession(child_id="c", attempt_id="a", problem_id="p", problem_result_id="r")
        s.add(gs); await s.flush()
        assert gs.max_tier_reached == 1 and gs.resolved is False and gs.entry_point == "post_grade"
        s.add(TutorTurn(session_id=gs.id, role="tutor", text="Let's look at #3.",
                        input_source=None, visuals=[{"type": "math", "tex": "3+3", "display": False}], tier=1))
        await s.commit()
        turns = (await s.exec(select(TutorTurn).where(TutorTurn.session_id == gs.id))).all()
        assert len(turns) == 1 and turns[0].visuals[0]["type"] == "math"
    await engine.dispose()
