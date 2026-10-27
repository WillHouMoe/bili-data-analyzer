import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.background_tasks import scrape_semaphore
from app.core.config import settings
from app.core.database import async_session
from app.models import AppSettings, Query, User, Video, VideoStats
from app.services.bilibili import BilibiliBlockedError, BilibiliClient
from app.services.creator_profile import apply_creator_info
from app.services.creator_stats_history import record_creator_stats_snapshot
from app.services.fetch_credentials import (
    FetchCredentialError,
    load_fetch_credentials,
)
from app.services.rankings import refresh_rankings_if_due

logger = logging.getLogger(__name__)

REFRESH_CHECK_SECONDS = 15 * 60
REFRESH_WINDOW_DEFAULT = 40
REFRESH_WINDOW_MIN = 30
REFRESH_WINDOW_MAX = 50


async def _refresh_window_size(db) -> int:
    row = await db.get(AppSettings, "refresh_window_size")
    try:
        value = int(row.value) if row else REFRESH_WINDOW_DEFAULT
    except (TypeError, ValueError):
        value = REFRESH_WINDOW_DEFAULT
    return min(REFRESH_WINDOW_MAX, max(REFRESH_WINDOW_MIN, value))


async def _fail_refresh(uid: int, message: str) -> None:
    async with async_session() as db:
        user = await db.get(User, uid)
        if user is None:
            return
        user.refresh_status = "error"
        user.refresh_progress = None
        user.refresh_error = message
        user.refresh_retry_at = datetime.now(UTC) + timedelta(hours=1)
        await db.commit()


async def run_stats_refresh(
    uid: int,
    sessdata: str | None,
    proxy_urls: list[str] | None = None,
) -> None:
    """Capture a new stats snapshot for every video in a creator library."""
    async with scrape_semaphore:
        async with async_session() as db:
            user = await db.get(User, uid)
            if user is None:
                return
            window_size = await _refresh_window_size(db)
            videos = (
                await db.execute(
                    select(Video)
                    .where(Video.uid == uid)
                    .order_by(Video.published_at.desc())
                    .limit(window_size)
                )
            ).scalars().all()

            client = BilibiliClient(sessdata=sessdata, proxy_urls=proxy_urls)
            try:
                creator_info = await client.get_user_info(uid)
                apply_creator_info(user, creator_info)
                await record_creator_stats_snapshot(db, user)
                user.refresh_status = "fetching"
                user.refresh_error = None
                user.refresh_retry_at = None
                user.refresh_progress = f"Refreshing statistics 0/{len(videos)}"
                await db.commit()

                for index, video in enumerate(videos, start=1):
                    user.refresh_progress = (
                        f"Refreshing statistics {index}/{len(videos)}"
                    )
                    await db.commit()

                    detail = await client.get_video_detail(video.bvid)
                    owner_uid = detail.get("owner_uid")
                    if owner_uid is not None and owner_uid != uid:
                        logger.warning(
                            "Skipping %s in uid %s stats refresh: owner is %s",
                            video.bvid,
                            uid,
                            owner_uid,
                        )
                        continue

                    video.title = detail["title"]
                    video.description = detail["description"]
                    video.cover_url = detail["cover_url"]
                    video.duration = detail["duration"]
                    video.published_at = datetime.fromtimestamp(
                        detail["published_at"], tz=UTC
                    )
                    video.tags = detail["tags"]
                    video.updated_at = datetime.now(UTC)

                    stats = detail["stats"]
                    db.add(
                        VideoStats(
                            bvid=video.bvid,
                            views=stats["views"],
                            likes=stats["likes"],
                            coins=stats["coins"],
                            favorites=stats["favorites"],
                            shares=stats["shares"],
                            danmaku_count=stats["danmaku_count"],
                            comment_count=stats["comment_count"],
                        )
                    )
                    await db.commit()

                user.refresh_status = "done"
                user.refresh_progress = None
                user.refresh_error = None
                user.last_stats_refresh_at = datetime.now(UTC)
                await db.commit()
            except BilibiliBlockedError as exc:
                await db.rollback()
                await _fail_refresh(uid, str(exc))
            except Exception:
                logger.exception("Stats refresh failed for uid %s", uid)
                await db.rollback()
                await _fail_refresh(uid, "Stats refresh failed; check server logs")
            finally:
                await client.aclose()


async def refresh_one_due_creator() -> bool:
    """Refresh the stalest creator if its automatic snapshot is due."""
    hours = settings.STATS_REFRESH_HOURS
    if hours <= 0:
        return False

    cutoff = datetime.now(UTC) - timedelta(hours=hours)
    async with async_session() as db:
        creator_uids = select(Video.uid).distinct()
        active_query_uids = select(Query.uid).where(
            Query.status.in_(("pending", "fetching"))
        )
        user = (
            await db.execute(
                select(User)
                .where(
                    User.uid.in_(creator_uids),
                    User.uid.not_in(active_query_uids),
                    User.refresh_status.not_in(("pending", "fetching")),
                    (
                        User.refresh_retry_at.is_(None)
                        | (User.refresh_retry_at <= datetime.now(UTC))
                    ),
                    (
                        User.last_stats_refresh_at.is_(None)
                        | (User.last_stats_refresh_at < cutoff)
                    ),
                )
                .order_by(
                    User.last_stats_refresh_at.asc().nullsfirst(),
                    User.uid,
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if user is None:
            return False
        try:
            sessdata, proxies = await load_fetch_credentials(db)
        except FetchCredentialError:
            logger.warning("Automatic stats refresh skipped: credentials unreadable")
            return False
        if not sessdata:
            logger.warning("Automatic stats refresh skipped: SESSDATA is not configured")
            return False
        uid = user.uid

    await run_stats_refresh(uid, sessdata, proxy_urls=proxies)
    return True


async def stats_refresh_loop() -> None:
    while True:
        try:
            await refresh_rankings_if_due()
        except Exception:
            logger.exception("Automatic rankings refresh failed")
        try:
            await refresh_due_creators()
        except Exception:
            logger.exception("Automatic stats refresh loop failed")
        await asyncio.sleep(REFRESH_CHECK_SECONDS)


async def refresh_due_creators() -> int:
    """Drain every overdue creator, including work missed while offline."""
    refreshed = 0
    while await refresh_one_due_creator():
        refreshed += 1
    return refreshed
