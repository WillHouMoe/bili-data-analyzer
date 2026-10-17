from datetime import UTC, date, datetime

import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models  # noqa: F401
from app.core.database import Base
from app.models import Query, QueryVideo, Video, VideoStats
from app.services import fetch_task

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
        return {
            "bvid": bvid,
            "aid": 123,
            "cid": 456,
            "is_live_replay": False,
            "has_subtitle": False,
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

    async def get_comments(self, aid):
        return []

    async def get_danmakus(self, cid):
        return []

    async def get_subtitle(self, bvid, aid, cid):
        return ""


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
    monkeypatch.setattr(fetch_task, "track_task", lambda coro: coro.close())


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
