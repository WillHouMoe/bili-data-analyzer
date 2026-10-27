from datetime import datetime

import pytest
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

import app.models  # noqa: F401 — side-effect import registers all tables
from app.core.database import Base
from app.schemas.video import VideoDetail, VideoStatsSchema

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(autouse=True)
async def setup_db():
    test_engine = create_async_engine(TEST_DB_URL, echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield test_engine
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


async def test_all_tables_created(setup_db):
    async with setup_db.connect() as connection:
        table_names = await connection.run_sync(
            lambda conn: inspect(conn).get_table_names()
        )

    assert {
        "users",
        "videos",
        "video_stats",
        "queries",
        "query_videos",
        "ranking_entries",
        "creator_stats_snapshots",
        "app_settings",
        "ai_conversations",
    }.issubset(table_names)
    assert "video_content" not in table_names
    assert "video_sentiment" not in table_names


def test_api_datetimes_are_serialized_in_china_time():
    detail = VideoDetail(
        bvid="BV1",
        title="Video",
        cover_url=None,
        duration=60,
        published_at=datetime(2026, 10, 25, 0, 30),
        tags=None,
        description=None,
        rankings=[],
        stats=VideoStatsSchema(
            views=0,
            likes=0,
            coins=0,
            favorites=0,
            shares=0,
            danmaku_count=0,
            comment_count=0,
            interaction_rate=0,
        ),
    )

    payload = detail.model_dump(mode="json")

    assert payload["published_at"] == "2026-10-25T08:30:00+08:00"
