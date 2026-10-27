from datetime import date, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models  # noqa: F401
from app.api.videos import list_videos
from app.core.database import Base
from app.main import app
from app.models import Query, QueryVideo, User, Video, VideoStats

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture
async def session_factory():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


async def _seed_query_videos(session) -> int:
    session.add(User(uid=1, name="Roxy", avatar_url=None))
    query = Query(
        uid=1,
        user_name="Roxy",
        start_date=date(2026, 3, 1),
        end_date=date(2026, 3, 31),
    )
    session.add(query)
    await session.flush()

    session.add_all([
        Video(bvid="BVTOP", uid=1, title="Top video", duration=30, tags="music,clip"),
        Video(bvid="BVTUTOR", uid=1, title="Tutorial basics", duration=600, tags="guide,starter"),
        Video(bvid="BVLONG", uid=1, title="Other entry", duration=7200, tags="archive,longform"),
    ])
    session.add_all([
        QueryVideo(query_id=query.id, bvid="BVTOP"),
        QueryVideo(query_id=query.id, bvid="BVTUTOR"),
        QueryVideo(query_id=query.id, bvid="BVLONG"),
    ])

    fetched_at = datetime(2026, 4, 1, 12, 0, 0)
    session.add_all([
        VideoStats(bvid="BVTOP", views=1000, fetched_at=fetched_at),
        VideoStats(bvid="BVTUTOR", views=100, fetched_at=fetched_at + timedelta(minutes=1)),
        VideoStats(bvid="BVLONG", views=50, fetched_at=fetched_at + timedelta(minutes=2)),
    ])
    await session.commit()
    return query.id


@pytest.mark.asyncio
async def test_list_videos_sorts_by_duration_desc(session_factory):
    async with session_factory() as session:
        query_id = await _seed_query_videos(session)

        result = await list_videos(
            query_id=query_id,
            sort_by="duration",
            order="desc",
            page=1,
            page_size=10,
            search="",
            db=session,
        )

    assert [item.bvid for item in result.items] == ["BVLONG", "BVTUTOR", "BVTOP"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("search", "expected_bvid"),
    [("tutorial", "BVTUTOR"), ("guide", "BVTUTOR"), ("bvlong", "BVLONG")],
)
async def test_list_videos_search_filters_before_pagination_and_matches_multiple_fields(
    session_factory,
    search,
    expected_bvid,
):
    async with session_factory() as session:
        query_id = await _seed_query_videos(session)

        result = await list_videos(
            query_id=query_id,
            sort_by="views",
            order="desc",
            page=1,
            page_size=1,
            search=search,
            db=session,
        )

    assert result.total == 1
    assert result.total_pages == 1
    assert [item.bvid for item in result.items] == [expected_bvid]
def test_openapi_has_no_word_table_endpoints():
    paths = app.openapi()["paths"]

    assert not any("wordcloud" in path for path in paths)
