from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models  # noqa: F401
from app.core.database import Base
from app.models import RankingEntry, Video
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


@pytest.fixture(autouse=True)
def skip_live_achievement_fetch(monkeypatch):
    async def noop(client, bvids):
        return None

    monkeypatch.setattr(rankings, "_refresh_changed_honors", noop)


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

    async def get_weekly_series(self):
        return [
            {
                "number": 396,
                "status": 2,
                "name": "Week 396",
            },
            {
                "number": 395,
                "status": 2,
                "name": "Week 395",
            }
        ]

    async def get_weekly_must_watch(self, number=None, period_name=None):
        assert number in {395, 396}
        assert period_name == f"Week {number}"
        return [
            {
                "kind": "weekly",
                "period": f"weekly-{number}",
                "period_name": f"Week {number}",
                "rank": 0,
                "bvid": "BVWEEKLY1",
                "title": f"Weekly video {number}",
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
async def test_ranking_refresh_stores_current_chart_entries(
    monkeypatch, session_factory
):
    future = datetime.now(UTC) + timedelta(days=5)
    async with session_factory() as db:
        db.add_all(
            [
                Video(
                    bvid="BVRANK1",
                    uid=42,
                    title="Ranked video",
                    next_stats_refresh_at=future,
                ),
                Video(
                    bvid="BVWEEKLY1",
                    uid=42,
                    title="Weekly video",
                    next_stats_refresh_at=future,
                ),
            ]
        )
        await db.commit()

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
        videos = (
            await db.execute(
                select(Video).order_by(Video.bvid)
            )
        ).scalars().all()

    assert refreshed is True
    assert [row.kind for row in rows] == ["popular"]
    assert all(isinstance(row.fetched_at, datetime) for row in rows)
    by_bvid = {video.bvid: video for video in videos}
    assert by_bvid["BVRANK1"].next_stats_refresh_at.replace(tzinfo=UTC) < future
    assert by_bvid["BVWEEKLY1"].next_stats_refresh_at.replace(tzinfo=UTC) == future


@pytest.mark.asyncio
async def test_ranking_refresh_respects_the_short_poll_interval(
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
    assert count == 1


@pytest.mark.asyncio
async def test_intraday_rank_change_is_persisted_and_queues_video_refresh(
    monkeypatch, session_factory
):
    future = datetime.now(UTC) + timedelta(days=5)

    class ChangingRankingClient(FakeRankingClient):
        calls = 0

        async def get_site_ranking(self):
            type(self).calls += 1
            entries = await super().get_site_ranking()
            entries[0]["rank"] = 2 if type(self).calls == 1 else 1
            return entries

    async with session_factory() as db:
        db.add(
            Video(
                bvid="BVRANK1",
                uid=42,
                title="Ranked video",
                next_stats_refresh_at=future,
            )
        )
        await db.commit()

    async def fake_credentials(_db):
        return "sessdata", []

    monkeypatch.setattr(rankings, "async_session", session_factory)
    monkeypatch.setattr(rankings, "BilibiliClient", ChangingRankingClient)
    monkeypatch.setattr(
        rankings,
        "load_fetch_credentials",
        fake_credentials,
    )

    assert await rankings.refresh_rankings_if_due() is True
    async with session_factory() as db:
        await db.execute(
            update(RankingEntry)
            .where(RankingEntry.kind == "popular")
            .values(fetched_at=datetime.now(UTC) - timedelta(hours=1))
        )
        await db.commit()

    assert await rankings.refresh_rankings_if_due() is True
    async with session_factory() as db:
        popular = (
            await db.execute(
                select(RankingEntry).where(RankingEntry.kind == "popular")
            )
        ).scalars().all()
        video = await db.get(Video, "BVRANK1")

    assert [(row.rank, row.bvid) for row in popular] == [(1, "BVRANK1")]
    assert video.next_stats_refresh_at.replace(tzinfo=UTC) < future
