import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select, update

from app.core.background_tasks import scrape_semaphore
from app.core.config import settings
from app.core.database import async_session
from app.models import RankingEntry, Video
from app.services.bilibili import BilibiliClient
from app.services.fetch_credentials import (
    FetchCredentialError,
    load_fetch_credentials,
)
from app.services.video_achievements import record_video_honors

logger = logging.getLogger(__name__)

RANKING_CHECK_SECONDS = 60


async def _store_entries(
    kind: str,
    period: str,
    entries: list[dict],
    *,
    mark_videos_due: bool = True,
) -> set[str]:
    now = datetime.now(UTC)
    async with async_session() as db:
        changed_bvids: set[str] = set()
        if mark_videos_due:
            previous = {
                row.bvid: row.rank
                for row in (
                    await db.execute(
                        select(RankingEntry).where(
                            RankingEntry.kind == kind,
                            RankingEntry.period == period,
                        )
                    )
                ).scalars().all()
            }
            changed_bvids = {
                entry["bvid"]
                for entry in entries
                if entry.get("bvid")
                and previous.get(entry["bvid"]) != entry.get("rank")
            }
        await db.execute(
            delete(RankingEntry).where(
                RankingEntry.kind == kind,
                RankingEntry.period == period,
            )
        )
        for entry in entries:
            db.add(RankingEntry(**entry, fetched_at=now))
        if changed_bvids:
            await db.execute(
                update(Video)
                .where(Video.bvid.in_(changed_bvids))
                .values(next_stats_refresh_at=now)
            )
        await db.commit()
    return changed_bvids


async def _refresh_changed_honors(
    client: BilibiliClient,
    bvids: set[str],
) -> None:
    if not bvids:
        return
    for bvid in bvids:
        async with async_session() as db:
            video = await db.get(Video, bvid)
            if video is None:
                continue
            try:
                detail = await client.get_video_detail(
                    bvid,
                    include_tags=False,
                )
                await record_video_honors(db, video, detail)
                await db.commit()
            except Exception:
                logger.exception(
                    "Could not refresh achievement for changed ranking %s",
                    bvid,
                )
                await db.rollback()
        await asyncio.sleep(0.12)


async def refresh_rankings_if_due() -> bool:
    if settings.RANKING_REFRESH_MINUTES <= 0:
        return False
    cutoff = datetime.now(UTC) - timedelta(
        minutes=settings.RANKING_REFRESH_MINUTES
    )
    async with async_session() as db:
        latest_popular = (
            await db.execute(
                select(func.max(RankingEntry.fetched_at)).where(
                    RankingEntry.kind == "popular"
                )
            )
        ).scalar_one_or_none()
        if latest_popular is not None and latest_popular.tzinfo is None:
            latest_popular = latest_popular.replace(tzinfo=UTC)
        popular_due = latest_popular is None or latest_popular < cutoff
        if not popular_due:
            return False
        try:
            sessdata, proxies = await load_fetch_credentials(db)
        except FetchCredentialError:
            sessdata, proxies = None, []

    refreshed = False
    async with scrape_semaphore:
        client = BilibiliClient(sessdata=sessdata, proxy_urls=proxies)
        try:
            if popular_due:
                try:
                    popular = await client.get_site_ranking()
                    if popular:
                        changed_bvids = await _store_entries(
                            "popular",
                            popular[0]["period"],
                            popular,
                        )
                        await _refresh_changed_honors(
                            client,
                            changed_bvids,
                        )
                        refreshed = True
                except Exception:
                    logger.exception("Could not refresh the site-wide ranking")

        finally:
            await client.aclose()
    return refreshed


async def rankings_refresh_loop() -> None:
    """Poll rankings independently from creator-profile and video snapshots."""
    while True:
        try:
            await refresh_rankings_if_due()
        except Exception:
            logger.exception("Automatic rankings refresh failed")
        await asyncio.sleep(RANKING_CHECK_SECONDS)
