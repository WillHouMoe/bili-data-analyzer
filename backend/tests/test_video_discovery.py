from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models  # noqa: F401
from app.core.database import Base
from app.models import User, Video, VideoStats
from app.services import video_discovery

EXISTING_TS = int(datetime(2026, 10, 20, tzinfo=UTC).timestamp())
NEW_TS = int(datetime(2026, 10, 27, tzinfo=UTC).timestamp())


@pytest.fixture
async def session_factory(tmp_path):
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'discovery.db'}"
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


class FakeDiscoveryClient:
    def __init__(self, sessdata=None, proxy_urls=None):
        self.sessdata = sessdata
        self.proxy_urls = proxy_urls

    async def get_video_stubs_since(self, uid, since_ts):
        return [
            {
                "bvid": "BVNEW",
                "title": "New video",
                "published_ts": NEW_TS,
                "created": NEW_TS,
            },
            {
                "bvid": "BVOLD",
                "title": "Existing video",
                "published_ts": EXISTING_TS,
                "created": EXISTING_TS,
            },
            {
                "bvid": "BVEARLIER",
                "title": "Earlier unseen video",
                "published_ts": EXISTING_TS - 100,
                "created": EXISTING_TS - 100,
            },
        ]

    async def get_video_detail(self, bvid):
        assert bvid == "BVNEW"
        return {
            "bvid": bvid,
            "owner_uid": 946974,
            "owner_name": "Creator",
            "is_live_replay": False,
            "title": "New video",
            "description": "",
            "cover_url": "",
            "duration": 60,
            "published_at": NEW_TS,
            "tags": "tag",
            "honors": [],
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

    async def aclose(self):
        return None


@pytest.mark.asyncio
async def test_discovers_only_newer_unseen_uploads(
    monkeypatch,
    session_factory,
):
    async with session_factory() as db:
        db.add(User(uid=946974, name="Creator"))
        db.add(
            Video(
                bvid="BVOLD",
                uid=946974,
                title="Existing video",
                published_at=datetime.fromtimestamp(EXISTING_TS, tz=UTC),
            )
        )
        await db.commit()

    async def fake_credentials(_db):
        return "sessdata", []

    monkeypatch.setattr(video_discovery, "async_session", session_factory)
    monkeypatch.setattr(video_discovery, "BilibiliClient", FakeDiscoveryClient)
    monkeypatch.setattr(
        video_discovery,
        "load_fetch_credentials",
        fake_credentials,
    )

    assert await video_discovery.discover_new_videos() == 1

    async with session_factory() as db:
        videos = (
            await db.execute(select(Video.bvid).order_by(Video.bvid))
        ).scalars().all()
        stats_count = (
            await db.execute(select(func.count()).select_from(VideoStats))
        ).scalar_one()
        user = await db.get(User, 946974)
        new_video = await db.get(Video, "BVNEW")

    assert videos == ["BVNEW", "BVOLD"]
    assert stats_count == 1
    assert new_video.next_stats_refresh_at is not None
    assert user.last_video_scan_at is not None
