from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models  # noqa: F401
from app.core.database import Base
from app.models import AppSettings, Query, QueryVideo, User, Video, VideoStats
from app.services import fetch_task, stats_refresh

VIDEO_DATE = date(2026, 10, 15)
VIDEO_TS = int(datetime(2026, 10, 15, 12, 0, tzinfo=UTC).timestamp())


@pytest.fixture
async def fk_session_factory(tmp_path):
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'fetch.db'}",
        echo=False,
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


class FakeBilibiliClient:
    title = "A fetched video"
    detail_calls = 0

    def __init__(self, sessdata=None, proxy_urls=None, **kwargs):
        self.sessdata = sessdata
        self.proxy_urls = proxy_urls

    async def aclose(self):
        return None

    async def get_user_info(self, uid):
        return {"uid": uid, "name": "Test Creator", "avatar_url": ""}

    async def get_video_index_in_range(self, uid, start_date, end_date):
        return {"videos": [{"bvid": "BVFETCH1", "published_ts": VIDEO_TS}]}

    async def get_video_detail(self, bvid):
        type(self).detail_calls += 1
        return {
            "bvid": bvid,
            "is_live_replay": False,
            "title": self.title,
            "description": "",
            "cover_url": "",
            "duration": 60,
            "published_at": VIDEO_TS,
            "tags": "",
            "stats": {
                "views": 100,
                "likes": 10,
                "coins": 2,
                "favorites": 3,
                "shares": 1,
                "danmaku_count": 4,
                "comment_count": 5,
            },
        }

async def _create_query(session_factory) -> int:
    async with session_factory() as db:
        query = Query(
            uid=946974,
            start_date=VIDEO_DATE,
            end_date=VIDEO_DATE,
            status="pending",
        )
        db.add(query)
        await db.commit()
        await db.refresh(query)
        return query.id


def _patch_fetch(monkeypatch, session_factory, client_factory):
    monkeypatch.setattr(fetch_task, "async_session", session_factory)
    monkeypatch.setattr(fetch_task, "BilibiliClient", client_factory)


@pytest.mark.asyncio
async def test_run_fetch_persists_first_video_with_foreign_keys_enabled(
    monkeypatch, fk_session_factory
):
    query_id = await _create_query(fk_session_factory)
    _patch_fetch(monkeypatch, fk_session_factory, FakeBilibiliClient)

    await fetch_task.run_fetch(
        query_id,
        946974,
        VIDEO_DATE,
        VIDEO_DATE,
        sessdata="test",
    )

    async with fk_session_factory() as db:
        assert (await db.execute(text("PRAGMA foreign_keys"))).scalar_one() == 1
        query = await db.get(Query, query_id)
        assert query.status == "done"
        assert query.progress is None
        assert query.video_count == 1
        assert (await db.execute(select(func.count()).select_from(Video))).scalar_one() == 1
        assert (await db.execute(select(func.count()).select_from(VideoStats))).scalar_one() == 1
        assert (await db.execute(select(func.count()).select_from(QueryVideo))).scalar_one() == 1


@pytest.mark.asyncio
async def test_run_fetch_records_error_after_database_failure(
    monkeypatch, fk_session_factory
):
    class InvalidVideoClient(FakeBilibiliClient):
        title = None

    query_id = await _create_query(fk_session_factory)
    _patch_fetch(monkeypatch, fk_session_factory, InvalidVideoClient)

    await fetch_task.run_fetch(
        query_id,
        946974,
        VIDEO_DATE,
        VIDEO_DATE,
        sessdata="test",
    )

    async with fk_session_factory() as db:
        query = await db.get(Query, query_id)
        assert query.status == "error"
        assert query.progress is None
        assert query.error_message == "Fetch failed. Check server logs for details."


@pytest.mark.asyncio
async def test_run_fetch_reuses_existing_videos_for_overlapping_query(
    monkeypatch, fk_session_factory
):
    FakeBilibiliClient.detail_calls = 0
    first_query_id = await _create_query(fk_session_factory)
    second_query_id = await _create_query(fk_session_factory)
    _patch_fetch(monkeypatch, fk_session_factory, FakeBilibiliClient)

    await fetch_task.run_fetch(
        first_query_id,
        946974,
        VIDEO_DATE,
        VIDEO_DATE,
        sessdata="test",
    )
    await fetch_task.run_fetch(
        second_query_id,
        946974,
        VIDEO_DATE,
        VIDEO_DATE,
        sessdata="test",
    )

    async with fk_session_factory() as db:
        assert (await db.execute(select(func.count()).select_from(Video))).scalar_one() == 1
        assert (await db.execute(select(func.count()).select_from(VideoStats))).scalar_one() == 1
        assert (await db.execute(select(func.count()).select_from(QueryVideo))).scalar_one() == 2
        query = await db.get(Query, second_query_id)
        assert query.status == "done"
        assert query.video_count == 1
        assert FakeBilibiliClient.detail_calls == 1


@pytest.mark.asyncio
async def test_run_fetch_is_idempotent_when_resuming_same_query(
    monkeypatch, fk_session_factory
):
    FakeBilibiliClient.detail_calls = 0
    query_id = await _create_query(fk_session_factory)
    _patch_fetch(monkeypatch, fk_session_factory, FakeBilibiliClient)

    await fetch_task.run_fetch(
        query_id,
        946974,
        VIDEO_DATE,
        VIDEO_DATE,
        sessdata="test",
    )
    await fetch_task.run_fetch(
        query_id,
        946974,
        VIDEO_DATE,
        VIDEO_DATE,
        sessdata="test",
    )

    async with fk_session_factory() as db:
        assert (await db.execute(select(func.count()).select_from(VideoStats))).scalar_one() == 1
        assert (await db.execute(select(func.count()).select_from(QueryVideo))).scalar_one() == 1
        assert FakeBilibiliClient.detail_calls == 1


@pytest.mark.asyncio
async def test_run_fetch_skips_video_owned_by_another_creator(
    monkeypatch, fk_session_factory
):
    class CrossOwnerClient(FakeBilibiliClient):
        async def get_video_detail(self, bvid):
            detail = await super().get_video_detail(bvid)
            detail["owner_uid"] = 123456
            return detail

    query_id = await _create_query(fk_session_factory)
    async with fk_session_factory() as db:
        db.add(User(uid=123456, name="Other creator"))
        db.add(Video(bvid="BVFETCH1", uid=123456, title="Foreign video"))
        await db.commit()

    _patch_fetch(monkeypatch, fk_session_factory, CrossOwnerClient)
    await fetch_task.run_fetch(
        query_id,
        946974,
        VIDEO_DATE,
        VIDEO_DATE,
        sessdata="test",
    )

    async with fk_session_factory() as db:
        query = await db.get(Query, query_id)
        video = await db.get(Video, "BVFETCH1")
        query_video_count = (
            await db.execute(select(func.count()).select_from(QueryVideo))
        ).scalar_one()

    assert query.status == "done"
    assert query.video_count == 0
    assert video.uid == 123456
    assert query_video_count == 0


@pytest.mark.asyncio
async def test_stats_refresh_captures_new_snapshot_for_existing_video(
    monkeypatch, fk_session_factory
):
    async with fk_session_factory() as db:
        db.add(User(uid=946974, name="Test Creator"))
        db.add(
            Video(
                bvid="BVFETCH1",
                uid=946974,
                title="Existing video",
                published_at=datetime(2026, 10, 15),
            )
        )
        await db.commit()

    monkeypatch.setattr(stats_refresh, "async_session", fk_session_factory)
    monkeypatch.setattr(stats_refresh, "BilibiliClient", FakeBilibiliClient)
    await stats_refresh.run_stats_refresh(946974, sessdata="test")

    async with fk_session_factory() as db:
        user = await db.get(User, 946974)
        stats_count = (
            await db.execute(select(func.count()).select_from(VideoStats))
        ).scalar_one()

    assert stats_count == 1
    assert user.refresh_status == "done"
    assert user.refresh_progress is None
    assert user.last_stats_refresh_at is not None


@pytest.mark.asyncio
async def test_stats_refresh_respects_configured_recent_video_window(
    monkeypatch, fk_session_factory
):
    async with fk_session_factory() as db:
        db.add(User(uid=946974, name="Test Creator"))
        db.add(AppSettings(key="refresh_window_size", value="30"))
        for index in range(35):
            db.add(
                Video(
                    bvid=f"BVWINDOW{index:02d}",
                    uid=946974,
                    title=f"Video {index}",
                    published_at=datetime(2026, 10, 1, 12) + timedelta(days=index),
                )
            )
        await db.commit()

    monkeypatch.setattr(stats_refresh, "async_session", fk_session_factory)
    monkeypatch.setattr(stats_refresh, "BilibiliClient", FakeBilibiliClient)
    await stats_refresh.run_stats_refresh(946974, sessdata="test")

    async with fk_session_factory() as db:
        stats_count = (
            await db.execute(select(func.count()).select_from(VideoStats))
        ).scalar_one()

    assert stats_count == 30


@pytest.mark.asyncio
async def test_refresh_one_due_creator_selects_stale_library(
    monkeypatch, fk_session_factory
):
    async with fk_session_factory() as db:
        db.add(User(uid=946974, name="Test Creator"))
        db.add(Video(bvid="BVFETCH1", uid=946974, title="Existing video"))
        await db.commit()

    calls: list[tuple[int, str]] = []

    async def fake_credentials(_db):
        return "sessdata", []

    async def fake_refresh(uid, sessdata, proxy_urls=None):
        calls.append((uid, sessdata))

    monkeypatch.setattr(stats_refresh, "async_session", fk_session_factory)
    monkeypatch.setattr(
        stats_refresh,
        "load_fetch_credentials",
        fake_credentials,
    )
    monkeypatch.setattr(stats_refresh, "run_stats_refresh", fake_refresh)

    refreshed = await stats_refresh.refresh_one_due_creator()

    assert refreshed is True
    assert calls == [(946974, "sessdata")]


@pytest.mark.asyncio
async def test_refresh_due_creators_catches_up_every_overdue_library(
    monkeypatch, fk_session_factory
):
    now = datetime.now(UTC)
    async with fk_session_factory() as db:
        db.add_all(
            [
                User(
                    uid=1,
                    name="Oldest",
                    last_stats_refresh_at=now - timedelta(hours=72),
                ),
                User(
                    uid=2,
                    name="Older",
                    last_stats_refresh_at=now - timedelta(hours=48),
                ),
                Video(bvid="BVONE", uid=1, title="One"),
                Video(bvid="BVTWO", uid=2, title="Two"),
            ]
        )
        await db.commit()

    calls: list[int] = []

    async def fake_credentials(_db):
        return "sessdata", []

    async def fake_refresh(uid, sessdata, proxy_urls=None):
        calls.append(uid)
        async with fk_session_factory() as db:
            user = await db.get(User, uid)
            user.last_stats_refresh_at = datetime.now(UTC)
            await db.commit()

    monkeypatch.setattr(stats_refresh, "async_session", fk_session_factory)
    monkeypatch.setattr(
        stats_refresh,
        "load_fetch_credentials",
        fake_credentials,
    )
    monkeypatch.setattr(stats_refresh, "run_stats_refresh", fake_refresh)

    refreshed = await stats_refresh.refresh_due_creators()

    assert refreshed == 2
    assert calls == [1, 2]


@pytest.mark.asyncio
async def test_refresh_retry_cooldown_does_not_starve_other_creators(
    monkeypatch, fk_session_factory
):
    now = datetime.now(UTC)
    async with fk_session_factory() as db:
        db.add_all(
            [
                User(
                    uid=1,
                    name="Failed creator",
                    last_stats_refresh_at=now - timedelta(days=5),
                    refresh_retry_at=now + timedelta(hours=1),
                ),
                User(
                    uid=2,
                    name="Due creator",
                    last_stats_refresh_at=now - timedelta(days=2),
                ),
                Video(bvid="BVONE", uid=1, title="One"),
                Video(bvid="BVTWO", uid=2, title="Two"),
            ]
        )
        await db.commit()

    calls: list[int] = []

    async def fake_credentials(_db):
        return "sessdata", []

    async def fake_refresh(uid, sessdata, proxy_urls=None):
        calls.append(uid)

    monkeypatch.setattr(stats_refresh, "async_session", fk_session_factory)
    monkeypatch.setattr(
        stats_refresh,
        "load_fetch_credentials",
        fake_credentials,
    )
    monkeypatch.setattr(stats_refresh, "run_stats_refresh", fake_refresh)

    assert await stats_refresh.refresh_one_due_creator() is True
    assert calls == [2]


@pytest.mark.asyncio
async def test_overlapping_append_does_not_reset_full_snapshot_time(
    monkeypatch, fk_session_factory
):
    FakeBilibiliClient.detail_calls = 0
    first_query_id = await _create_query(fk_session_factory)
    _patch_fetch(monkeypatch, fk_session_factory, FakeBilibiliClient)
    await fetch_task.run_fetch(
        first_query_id,
        946974,
        VIDEO_DATE,
        VIDEO_DATE,
        sessdata="test",
    )

    stale_at = datetime(2026, 1, 1)
    async with fk_session_factory() as db:
        user = await db.get(User, 946974)
        user.last_stats_refresh_at = stale_at
        await db.commit()

    second_query_id = await _create_query(fk_session_factory)
    await fetch_task.run_fetch(
        second_query_id,
        946974,
        VIDEO_DATE,
        VIDEO_DATE,
        sessdata="test",
    )

    async with fk_session_factory() as db:
        user = await db.get(User, 946974)

    assert user.last_stats_refresh_at == stale_at
