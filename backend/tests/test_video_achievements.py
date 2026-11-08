from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models  # noqa: F401
from app.core.database import Base
from app.models import RankingEntry, User, Video
from app.services.video_achievements import record_video_honors


@pytest.fixture
async def session_factory(tmp_path):
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'achievements.db'}"
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


def detail(rank: int) -> dict:
    return {
        "owner_uid": 946974,
        "owner_name": "Creator",
        "title": "Video",
        "cover_url": "",
        "stats": {"views": 100, "likes": 10},
        "honors": [
            {
                "type": 2,
                "desc": "第396期每周必看",
                "weekly_recommend_num": 396,
            },
            {
                "type": 3,
                "desc": f"全站排行榜最高第{rank}名",
            },
        ],
    }


@pytest.mark.asyncio
async def test_records_weekly_and_highest_achievements_without_losing_best_rank(
    session_factory,
):
    async with session_factory() as db:
        db.add(User(uid=946974, name="Creator"))
        video = Video(
            bvid="BVACHIEVEMENT",
            uid=946974,
            title="Video",
        )
        db.add(video)
        await db.flush()

        await record_video_honors(
            db,
            video,
            detail(1),
            fetched_at=datetime(2026, 10, 27, tzinfo=UTC),
        )
        await db.commit()

        await record_video_honors(
            db,
            video,
            detail(3),
            fetched_at=datetime(2026, 10, 28, tzinfo=UTC),
        )
        await db.commit()

        rows = (
            await db.execute(
                select(RankingEntry).order_by(RankingEntry.kind)
            )
        ).scalars().all()

    assert [(row.kind, row.rank) for row in rows] == [
        ("highest", 1),
        ("weekly", 0),
    ]
    assert video.honors_checked_at is not None
