from datetime import date, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models  # noqa: F401
from app.api.videos import get_video, list_videos
from app.core.database import Base
from app.main import app
from app.models import Query, QueryVideo, RankingEntry, User, Video, VideoStats

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
        Video(
            bvid="BVTOP",
            uid=1,
            title="Top video",
            duration=30,
            tags="music,clip",
            published_at=datetime(2026, 3, 30),
        ),
        Video(
            bvid="BVTUTOR",
            uid=1,
            title="Tutorial basics",
            duration=600,
            tags="guide,starter",
            published_at=datetime(2026, 3, 20),
        ),
        Video(
            bvid="BVLONG",
            uid=1,
            title="Other entry",
            duration=7200,
            tags="archive,longform",
            published_at=datetime(2026, 3, 10),
        ),
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
async def test_list_videos_defaults_to_newest_first(session_factory):
    async with session_factory() as session:
        query_id = await _seed_query_videos(session)

        result = await list_videos(
            query_id=query_id,
            page=1,
            page_size=10,
            search="",
            db=session,
        )

    assert [item.bvid for item in result.items] == ["BVTOP", "BVTUTOR", "BVLONG"]


@pytest.mark.asyncio
async def test_video_achievements_only_use_weekly_and_historical_high_rank(
    session_factory,
):
    async with session_factory() as session:
        await _seed_query_videos(session)
        session.add_all(
            [
                RankingEntry(
                    kind="weekly",
                    period="weekly-396",
                    period_name="第396期每周必看",
                    rank=0,
                    bvid="BVTOP",
                    title="Top video",
                    owner_uid=1,
                    owner_name="Roxy",
                ),
                RankingEntry(
                    kind="highest",
                    period="all-time",
                    period_name="全站排行榜最高第1名",
                    rank=1,
                    bvid="BVTOP",
                    title="Top video",
                    owner_uid=1,
                    owner_name="Roxy",
                ),
                RankingEntry(
                    kind="popular",
                    period="2026-10-27",
                    period_name="Current chart",
                    rank=3,
                    bvid="BVTOP",
                    title="Top video",
                    owner_uid=1,
                    owner_name="Roxy",
                ),
            ]
        )
        await session.commit()

        detail = await get_video("BVTOP", session)

    assert {(item.kind, item.rank) for item in detail.rankings} == {
        ("weekly", None),
        ("highest", 1),
    }


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
