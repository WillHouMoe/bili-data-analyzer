from datetime import datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models  # noqa: F401
from app.core.database import Base
from app.models import RankingEntry
from app.services import rankings


@pytest.fixture
async def session_factory(tmp_path):
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'rankings.db'}",
        echo=False,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


class FakeRankingClient:
    def __init__(self, sessdata=None, proxy_urls=None):
        self.sessdata = sessdata

    async def get_site_ranking(self):
        return [
            {
                "kind": "popular",
                "period": "2026-10-25",
                "period_name": "Ranking",
                "rank": 1,
                "bvid": "BVRANK1",
                "title": "Ranked video",
                "owner_uid": 42,
                "owner_name": "Creator",
                "cover_url": "",
                "views": 100,
                "likes": 10,
                "score": 0,
            }
        ]

    async def get_weekly_must_watch(self):
        return [
            {
                "kind": "weekly",
                "period": "weekly-396",
                "period_name": "Week 396",
                "rank": 3,
                "bvid": "BVWEEKLY1",
                "title": "Weekly video",
                "owner_uid": 42,
                "owner_name": "Creator",
                "cover_url": "",
                "views": 200,
                "likes": 20,
                "score": 0,
            }
        ]

    async def aclose(self):
        return None


@pytest.mark.asyncio
async def test_ranking_refresh_stores_popular_and_weekly_entries(
    monkeypatch, session_factory
):
    async def fake_credentials(_db):
        return "sessdata", []

    monkeypatch.setattr(rankings, "async_session", session_factory)
    monkeypatch.setattr(rankings, "BilibiliClient", FakeRankingClient)
    monkeypatch.setattr(
        rankings,
        "load_fetch_credentials",
        fake_credentials,
    )

    refreshed = await rankings.refresh_rankings_if_due()

    async with session_factory() as db:
        rows = (
            await db.execute(select(RankingEntry).order_by(RankingEntry.kind))
        ).scalars().all()

    assert refreshed is True
    assert [row.kind for row in rows] == ["popular", "weekly"]
    assert all(isinstance(row.fetched_at, datetime) for row in rows)


@pytest.mark.asyncio
async def test_ranking_refresh_is_daily_not_every_loop(
    monkeypatch, session_factory
):
    async def fake_credentials(_db):
        return "sessdata", []

    monkeypatch.setattr(rankings, "async_session", session_factory)
    monkeypatch.setattr(rankings, "BilibiliClient", FakeRankingClient)
    monkeypatch.setattr(
        rankings,
        "load_fetch_credentials",
        fake_credentials,
    )

    assert await rankings.refresh_rankings_if_due() is True
    assert await rankings.refresh_rankings_if_due() is False

    async with session_factory() as db:
        count = (
            await db.execute(select(func.count()).select_from(RankingEntry))
        ).scalar_one()
    assert count == 2
