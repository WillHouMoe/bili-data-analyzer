import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select

from app.core.background_tasks import scrape_semaphore
from app.core.config import settings
from app.core.database import async_session
from app.models import RankingEntry
from app.services.bilibili import BilibiliClient
from app.services.fetch_credentials import (
    FetchCredentialError,
    load_fetch_credentials,
)

logger = logging.getLogger(__name__)


async def _store_entries(kind: str, period: str, entries: list[dict]) -> None:
    now = datetime.now(UTC)
    async with async_session() as db:
        await db.execute(
            delete(RankingEntry).where(
                RankingEntry.kind == kind,
                RankingEntry.period == period,
            )
        )
        for entry in entries:
            db.add(RankingEntry(**entry, fetched_at=now))
        await db.commit()


async def refresh_rankings_if_due() -> bool:
    if settings.STATS_REFRESH_HOURS <= 0:
        return False
    cutoff = datetime.now(UTC) - timedelta(hours=settings.STATS_REFRESH_HOURS)
    async with async_session() as db:
        latest = (
            await db.execute(select(func.max(RankingEntry.fetched_at)))
        ).scalar_one_or_none()
        if latest is not None and latest.tzinfo is None:
            latest = latest.replace(tzinfo=UTC)
        if latest is not None and latest >= cutoff:
            return False
        try:
            sessdata, proxies = await load_fetch_credentials(db)
        except FetchCredentialError:
            sessdata, proxies = None, []

    refreshed = False
    async with scrape_semaphore:
        client = BilibiliClient(sessdata=sessdata, proxy_urls=proxies)
        try:
            try:
                popular = await client.get_site_ranking()
                if popular:
                    await _store_entries(
                        "popular",
                        popular[0]["period"],
                        popular,
                    )
                    refreshed = True
            except Exception:
                logger.exception("Could not refresh the site-wide ranking")

            if sessdata:
                try:
                    weekly = await client.get_weekly_must_watch()
                    if weekly:
                        await _store_entries(
                            "weekly",
                            weekly[0]["period"],
                            weekly,
                        )
                        refreshed = True
                except Exception:
                    logger.exception("Could not refresh weekly must-watch")
        finally:
            await client.aclose()
    return refreshed
