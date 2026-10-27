from datetime import date, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models  # noqa: F401
from app.api import creators as creators_api
from app.api import fetch as fetch_api
from app.api.creators import (
    creator_stats_summary,
    delete_creator,
    get_creator,
    list_creator_videos,
)
from app.api.fetch import create_fetch
from app.core.database import Base
from app.models import (
    AIConversation,
    AIMessage,
    CreatorStatsSnapshot,
    Query,
    QueryVideo,
    User,
    Video,
    VideoStats,
)
from app.schemas.query import FetchRequest


@pytest.fixture
async def session_factory(tmp_path):
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'creators.db'}",
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def _seed_library(session):
    session.add(User(uid=42, name="Creator", avatar_url=None))
    first = Query(
        uid=42,
        user_name="Creator",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 2, 1),
        status="done",
    )
    second = Query(
        uid=42,
        user_name="Creator",
        start_date=date(2026, 2, 1),
        end_date=date(2026, 3, 1),
        status="done",
    )
    session.add_all([first, second])
    await session.flush()
    session.add_all(
        [
            Video(
                bvid="BVOLD",
                uid=42,
                title="Old video",
                duration=60,
                published_at=datetime(2026, 1, 10),
            ),
            Video(
                bvid="BVNEW",
                uid=42,
                title="New video",
                duration=90,
                published_at=datetime(2026, 2, 10),
            ),
            QueryVideo(query_id=first.id, bvid="BVOLD"),
            QueryVideo(query_id=second.id, bvid="BVOLD"),
            QueryVideo(query_id=second.id, bvid="BVNEW"),
        ]
    )
    fetched = datetime(2026, 3, 2, 12, 0)
    session.add_all(
        [
            VideoStats(bvid="BVOLD", views=100, likes=10, fetched_at=fetched),
            VideoStats(
                bvid="BVOLD",
                views=150,
                likes=15,
                fetched_at=fetched + timedelta(hours=1),
            ),
            VideoStats(bvid="BVNEW", views=50, likes=5, fetched_at=fetched),
        ]
    )
    await session.commit()


@pytest.mark.asyncio
async def test_creator_detail_merges_fetch_batches_and_uses_latest_stats(
    session_factory,
):
    async with session_factory() as session:
        await _seed_library(session)
        detail = await get_creator(42, session)
        summary = await creator_stats_summary(42, session)

    assert detail.query_count == 2
    assert detail.video_count == 2
    assert detail.start_date == date(2026, 1, 10)
    assert detail.end_date == date(2026, 2, 10)
    assert summary.total_views == 200
    assert summary.total_likes == 20


@pytest.mark.asyncio
async def test_creator_video_list_is_deduplicated_and_searchable(session_factory):
    async with session_factory() as session:
        await _seed_library(session)
        result = await list_creator_videos(
            uid=42,
            sort_by="views",
            order="desc",
            page=1,
            page_size=100,
            search="old",
            db=session,
        )

    assert result.total == 1
    assert [item.bvid for item in result.items] == ["BVOLD"]
    assert result.items[0].stats.views == 150


@pytest.mark.asyncio
async def test_exact_repeated_fetch_reuses_existing_batch(session_factory):
    async with session_factory() as session:
        await _seed_library(session)
        existing = (
            await session.execute(
                Query.__table__.select().where(Query.start_date == date(2026, 2, 1))
            )
        ).first()
        response = await create_fetch(
            FetchRequest(
                uid=42,
                start_date=date(2026, 2, 1),
                end_date=date(2026, 3, 1),
            ),
            session,
        )

    assert response.query_id == existing.id
    assert response.status == "done"


@pytest.mark.asyncio
async def test_failed_latest_batch_does_not_mark_usable_library_as_failed(
    session_factory,
):
    async with session_factory() as session:
        session.add(User(uid=43, name="Recovered creator"))
        session.add(
            Query(
                uid=43,
                start_date=date(2026, 10, 1),
                end_date=date(2026, 10, 2),
                status="error",
                error_message="upstream failed",
            )
        )
        session.add(Video(bvid="BVRECOVERED", uid=43, title="Saved video"))
        session.add(VideoStats(bvid="BVRECOVERED", views=1))
        await session.commit()

        detail = await get_creator(43, session)

    assert detail.status == "done"
    assert detail.error_message == "upstream failed"


@pytest.mark.asyncio
async def test_new_fetch_returns_immediately_and_creates_pending_creator(
    session_factory, monkeypatch
):
    monkeypatch.setattr(fetch_api, "track_task", lambda coro: coro.close())
    async with session_factory() as session:
        response = await create_fetch(
            FetchRequest(
                uid=77,
                start_date=date(2026, 1, 1),
                end_date=date(2026, 1, 31),
            ),
            session,
        )
        creator = await session.get(User, 77)
        query = await session.get(Query, response.query_id)

    assert response.status == "pending"
    assert creator is not None
    assert creator.name == "UID 77"
    assert query is not None
    assert query.status == "pending"


@pytest.mark.asyncio
async def test_growth_curve_uses_latest_observation_per_video_and_age_bucket(
    session_factory,
):
    async with session_factory() as session:
        session.add(User(uid=88, name="Growth creator"))
        session.add_all(
            [
                Video(
                    bvid="BVGROWTH1",
                    uid=88,
                    title="First",
                    published_at=datetime(2026, 1, 1),
                ),
                Video(
                    bvid="BVGROWTH2",
                    uid=88,
                    title="Second",
                    published_at=datetime(2026, 1, 5),
                ),
            ]
        )
        await session.flush()
        session.add_all(
            [
                VideoStats(
                    bvid="BVGROWTH1",
                    views=10,
                    fetched_at=datetime(2026, 1, 1, 12),
                ),
                VideoStats(
                    bvid="BVGROWTH1",
                    views=30,
                    fetched_at=datetime(2026, 1, 4),
                ),
                VideoStats(
                    bvid="BVGROWTH1",
                    views=100,
                    fetched_at=datetime(2026, 1, 10),
                ),
                VideoStats(
                    bvid="BVGROWTH2",
                    views=20,
                    fetched_at=datetime(2026, 1, 5, 12),
                ),
                VideoStats(
                    bvid="BVGROWTH2",
                    views=40,
                    fetched_at=datetime(2026, 1, 7, 12),
                ),
            ]
        )
        await session.commit()

        growth = await creators_api.creator_stats_growth(88, session)

    assert growth.video_count == 2
    assert growth.observation_count == 5
    assert growth.videos_with_history == 2
    assert [(point.key, point.median_views) for point in growth.points] == [
        ("under1", 15),
        ("1to3", 40),
        ("3to7", 30),
        ("7to14", 100),
    ]


@pytest.mark.asyncio
async def test_creator_trend_buckets_publication_date_in_china_time(
    session_factory,
):
    async with session_factory() as session:
        session.add(User(uid=100, name="Timezone creator"))
        session.add(
            Video(
                bvid="BVMIDNIGHT",
                uid=100,
                title="Midnight release",
                published_at=datetime(2026, 10, 24, 16, 30),
            )
        )
        session.add(
            VideoStats(
                bvid="BVMIDNIGHT",
                views=123,
                fetched_at=datetime(2026, 10, 25, 1),
            )
        )
        await session.commit()

        trend = await creators_api.creator_stats_trend(100, session)

    assert [(point.date, point.views) for point in trend] == [
        ("2026-10-25", 123)
    ]


@pytest.mark.asyncio
async def test_account_growth_returns_followers_and_views_in_time_order(
    session_factory,
):
    async with session_factory() as session:
        session.add(User(uid=101, name="History creator"))
        session.add_all(
            [
                CreatorStatsSnapshot(
                    uid=101,
                    followers=1000,
                    total_views=50000,
                    total_likes=2500,
                    fetched_at=datetime(2026, 10, 24, 8),
                ),
                CreatorStatsSnapshot(
                    uid=101,
                    followers=1200,
                    total_views=62000,
                    total_likes=3100,
                    fetched_at=datetime(2026, 10, 25, 8),
                ),
            ]
        )
        await session.commit()

        growth = await creators_api.creator_account_growth(101, session)

    assert growth.uid == 101
    assert [
        (point.followers, point.total_views, point.total_likes)
        for point in growth.points
    ] == [
        (1000, 50000, 2500),
        (1200, 62000, 3100),
    ]


@pytest.mark.asyncio
async def test_manual_stats_refresh_queues_background_snapshot(
    session_factory, monkeypatch
):
    async with session_factory() as session:
        session.add(User(uid=99, name="Snapshot creator"))
        session.add(Video(bvid="BVSNAPSHOT", uid=99, title="Video"))
        await session.commit()

        async def fake_credentials(_db):
            return "sessdata", []

        monkeypatch.setattr(
            creators_api,
            "load_fetch_credentials",
            fake_credentials,
        )
        monkeypatch.setattr(
            creators_api,
            "track_task",
            lambda coro: coro.close(),
        )
        response = await creators_api.refresh_creator_stats(99, session)
        user = await session.get(User, 99)

    assert response == {"status": "pending"}
    assert user.refresh_status == "pending"
    assert user.refresh_progress == "Queued to capture a new stats snapshot"


@pytest.mark.asyncio
async def test_delete_creator_removes_dependent_rows_in_foreign_key_order(
    session_factory,
):
    async with session_factory() as session:
        await _seed_library(session)
        conversation = AIConversation(
            uid=42,
            preset="free_chat",
            title="Test",
        )
        session.add(conversation)
        await session.flush()
        session.add(
            AIMessage(
                conversation_id=conversation.id,
                role="user",
                content="Hello",
            )
        )
        session.add(
            CreatorStatsSnapshot(
                uid=42,
                followers=10,
                total_views=100,
                fetched_at=datetime(2026, 10, 25),
            )
        )
        await session.commit()

        response = await delete_creator(42, session)
        user = await session.get(User, 42)
        remaining = {
            "videos": (
                await session.execute(
                    Video.__table__.select().where(Video.uid == 42)
                )
            ).first(),
            "stats": (
                await session.execute(
                    VideoStats.__table__.select().where(
                        VideoStats.bvid.in_(("BVOLD", "BVNEW"))
                    )
                )
            ).first(),
            "query_videos": (
                await session.execute(QueryVideo.__table__.select())
            ).first(),
            "queries": (
                await session.execute(Query.__table__.select().where(Query.uid == 42))
            ).first(),
            "messages": (
                await session.execute(AIMessage.__table__.select())
            ).first(),
            "conversations": (
                await session.execute(AIConversation.__table__.select())
            ).first(),
            "account_snapshots": (
                await session.execute(
                    CreatorStatsSnapshot.__table__.select().where(
                        CreatorStatsSnapshot.uid == 42
                    )
                )
            ).first(),
        }

    assert response == {"status": "deleted"}
    assert user is None
    assert all(value is None for value in remaining.values())
