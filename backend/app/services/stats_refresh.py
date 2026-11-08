import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.background_tasks import scrape_semaphore
from app.core.config import settings
from app.core.database import async_session
from app.models import Query, RankingEntry, User, Video, VideoStats
from app.services.bilibili import BilibiliBlockedError, BilibiliClient
from app.services.creator_profile import apply_creator_info
from app.services.creator_stats_history import record_creator_stats_snapshot
from app.services.fetch_credentials import (
    FetchCredentialError,
    load_fetch_credentials,
)
from app.services.video_achievements import record_video_honors
from app.services.video_maintenance import (
    MAINTENANCE_WINDOW_DAYS,
    MAINTENANCE_WINDOWED,
    defer_video_after_failure,
    get_maintenance_mode,
    schedule_after_snapshot,
)

logger = logging.getLogger(__name__)

REFRESH_CHECK_SECONDS = 5 * 60
REFRESH_VIDEO_BATCH = 20
HONOR_BACKFILL_BATCH = 20


class SkippedVideoError(Exception):
    """A video response cannot be stored for this creator."""


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


async def _mark_profile_started(db: AsyncSession, user: User) -> None:
    user.refresh_status = "fetching"
    user.refresh_progress = "Refreshing creator profile"
    user.refresh_error = None
    user.refresh_retry_at = None
    await db.commit()


async def _capture_profile(
    db: AsyncSession,
    user: User,
    client: BilibiliClient,
    *,
    sampled_at: datetime | None = None,
) -> None:
    creator_info = await client.get_user_info(user.uid)
    apply_creator_info(user, creator_info)
    await record_creator_stats_snapshot(
        db,
        user,
        fetched_at=sampled_at or datetime.now(UTC),
    )


async def _due_video_statement(
    db: AsyncSession,
    *,
    uid: int | None = None,
    limit: int | None = None,
):
    now = datetime.now(UTC)
    mode = await get_maintenance_mode(db)
    statement = select(Video).where(
        or_(
            Video.next_stats_refresh_at.is_(None),
            Video.next_stats_refresh_at <= now,
        )
    )
    if mode == MAINTENANCE_WINDOWED:
        cutoff = now - timedelta(days=MAINTENANCE_WINDOW_DAYS)
        statement = statement.where(
            or_(
                Video.published_at.is_(None),
                Video.published_at >= cutoff,
            )
        )
    if uid is not None:
        statement = statement.where(Video.uid == uid)
    statement = statement.order_by(
        Video.next_stats_refresh_at.asc().nullsfirst(),
        Video.bvid,
    )
    if limit is not None:
        statement = statement.limit(limit)
    return statement


async def _history_for_video(
    db: AsyncSession,
    bvid: str,
    limit: int = 4,
) -> list[VideoStats]:
    history = (
        await db.execute(
            select(VideoStats)
            .where(VideoStats.bvid == bvid)
            .order_by(VideoStats.fetched_at.desc(), VideoStats.id.desc())
            .limit(limit)
        )
    ).scalars().all()
    return list(reversed(history))


async def _capture_video_stats(
    db: AsyncSession,
    client: BilibiliClient,
    video: Video,
    *,
    sampled_at: datetime | None = None,
) -> None:
    now = sampled_at or datetime.now(UTC)
    history = await _history_for_video(db, video.bvid)
    detail = await client.get_video_detail(video.bvid, include_tags=False)
    if detail.get("is_live_replay"):
        raise SkippedVideoError("live replay")
    owner_uid = detail.get("owner_uid")
    if owner_uid is not None and owner_uid != video.uid:
        raise SkippedVideoError(
            f"owner is {owner_uid}, expected {video.uid}"
        )

    video.title = detail["title"]
    video.description = detail["description"]
    video.cover_url = detail["cover_url"]
    video.duration = detail["duration"]
    video.published_at = datetime.fromtimestamp(
        detail["published_at"],
        tz=UTC,
    )
    video.updated_at = now
    if detail.get("tags"):
        video.tags = detail["tags"]

    stats_values = detail["stats"]
    db.add(
        VideoStats(
            bvid=video.bvid,
            views=stats_values["views"],
            likes=stats_values["likes"],
            coins=stats_values["coins"],
            favorites=stats_values["favorites"],
            shares=stats_values["shares"],
            danmaku_count=stats_values["danmaku_count"],
            comment_count=stats_values["comment_count"],
            fetched_at=now,
        )
    )
    ranking_fetched_at = (
        await db.execute(
            select(func.max(RankingEntry.fetched_at)).where(
                RankingEntry.bvid == video.bvid
            )
        )
    ).scalar_one_or_none()
    await record_video_honors(db, video, detail, fetched_at=now)
    schedule_after_snapshot(
        video,
        history,
        now,
        stats_values["views"],
        ranking_fetched_at=ranking_fetched_at,
    )
    await db.commit()


async def run_stats_refresh(
    uid: int,
    sessdata: str | None,
    proxy_urls: list[str] | None = None,
) -> None:
    """Refresh creator totals and every currently due video in the library."""
    async with scrape_semaphore:
        async with async_session() as db:
            user = await db.get(User, uid)
            if user is None:
                return
            client = BilibiliClient(sessdata=sessdata, proxy_urls=proxy_urls)
            try:
                await _mark_profile_started(db, user)
                await _capture_profile(db, user, client)
                await db.commit()

                videos = (
                    await db.execute(await _due_video_statement(db, uid=uid))
                ).scalars().all()
                user.refresh_progress = (
                    f"Refreshing due statistics 0/{len(videos)}"
                )
                await db.commit()

                for index, video in enumerate(videos, start=1):
                    user.refresh_progress = (
                        f"Refreshing due statistics {index}/{len(videos)}"
                    )
                    await db.commit()
                    await _capture_video_stats(db, client, video)

                user.refresh_status = "done"
                user.refresh_progress = None
                user.refresh_error = None
                user.refresh_retry_at = None
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


async def run_creator_profile_refresh(
    uid: int,
    sessdata: str | None,
    proxy_urls: list[str] | None = None,
) -> None:
    """Capture only follower, account-view, account-like and archive totals."""
    async with scrape_semaphore:
        async with async_session() as db:
            user = await db.get(User, uid)
            if user is None:
                return
            client = BilibiliClient(sessdata=sessdata, proxy_urls=proxy_urls)
            try:
                await _mark_profile_started(db, user)
                sampled_at = datetime.now(UTC)
                await _capture_profile(
                    db,
                    user,
                    client,
                    sampled_at=sampled_at,
                )
                user.refresh_status = "done"
                user.refresh_progress = None
                user.refresh_error = None
                user.refresh_retry_at = None
                user.last_stats_refresh_at = sampled_at
                await db.commit()
            except BilibiliBlockedError as exc:
                await db.rollback()
                await _fail_refresh(uid, str(exc))
            except Exception:
                logger.exception("Creator profile refresh failed for uid %s", uid)
                await db.rollback()
                await _fail_refresh(
                    uid,
                    "Creator profile refresh failed; check server logs",
                )
            finally:
                await client.aclose()


async def refresh_one_due_creator() -> bool:
    """Refresh the stalest creator account profile if its daily snapshot is due."""
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
            logger.warning("Automatic profile refresh skipped: credentials unreadable")
            return False
        if not sessdata:
            logger.warning(
                "Automatic profile refresh skipped: SESSDATA is not configured"
            )
            return False
        uid = user.uid

    await run_creator_profile_refresh(uid, sessdata, proxy_urls=proxies)
    return True


async def refresh_due_creators() -> int:
    """Drain every overdue creator account profile, including offline gaps."""
    refreshed = 0
    while await refresh_one_due_creator():
        refreshed += 1
    return refreshed


async def refresh_due_videos(limit: int = REFRESH_VIDEO_BATCH) -> int:
    """Capture one snapshot for the oldest due videos across every creator."""
    if settings.STATS_REFRESH_HOURS <= 0:
        return 0
    async with async_session() as db:
        try:
            sessdata, proxies = await load_fetch_credentials(db)
        except FetchCredentialError:
            logger.warning(
                "Automatic video refresh skipped: credentials unreadable"
            )
            return 0
        if not sessdata:
            logger.warning(
                "Automatic video refresh skipped: SESSDATA is not configured"
            )
            return 0

    refreshed = 0
    async with scrape_semaphore:
        async with async_session() as db:
            due = (
                await db.execute(
                    await _due_video_statement(db, limit=limit)
                )
            ).scalars().all()
            if not due:
                return 0
            bvids = [video.bvid for video in due]
        client = BilibiliClient(sessdata=sessdata, proxy_urls=proxies)
        try:
            for bvid in bvids:
                async with async_session() as db:
                    video = await db.get(Video, bvid)
                    if video is None:
                        continue
                    try:
                        await _capture_video_stats(db, client, video)
                        refreshed += 1
                    except SkippedVideoError as exc:
                        logger.warning(
                            "Skipping %s during scheduled stats refresh: %s",
                            bvid,
                            exc,
                        )
                        defer_video_after_failure(video)
                        await db.commit()
                    except BilibiliBlockedError:
                        raise
                    except Exception:
                        logger.exception(
                            "Scheduled stats refresh failed for %s",
                            bvid,
                        )
                        await db.rollback()
                        video = await db.get(Video, bvid)
                        if video is not None:
                            defer_video_after_failure(video)
                            await db.commit()
        except BilibiliBlockedError as exc:
            logger.warning("Scheduled stats refresh blocked: %s", exc)
        finally:
            await client.aclose()
    return refreshed


async def backfill_video_honors(limit: int = HONOR_BACKFILL_BATCH) -> int:
    """Check each library video once for long-lived Bilibili achievements."""
    if settings.STATS_REFRESH_HOURS <= 0:
        return 0
    async with async_session() as db:
        try:
            sessdata, proxies = await load_fetch_credentials(db)
        except FetchCredentialError:
            logger.warning(
                "Achievement backfill skipped: credentials unreadable"
            )
            return 0
        if not sessdata:
            logger.warning(
                "Achievement backfill skipped: SESSDATA is not configured"
            )
            return 0

    checked = 0
    async with scrape_semaphore:
        async with async_session() as db:
            bvids = (
                await db.execute(
                    select(Video.bvid)
                    .where(Video.honors_checked_at.is_(None))
                    .order_by(Video.published_at.desc(), Video.bvid)
                    .limit(limit)
                )
            ).scalars().all()
        if not bvids:
            return 0

        client = BilibiliClient(sessdata=sessdata, proxy_urls=proxies)
        try:
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
                        owner_uid = detail.get("owner_uid")
                        if owner_uid is None or owner_uid == video.uid:
                            await record_video_honors(db, video, detail)
                        else:
                            video.honors_checked_at = datetime.now(UTC)
                        await db.commit()
                        checked += 1
                    except BilibiliBlockedError:
                        raise
                    except Exception:
                        logger.exception(
                            "Achievement backfill failed for %s",
                            bvid,
                        )
                        await db.rollback()
        except BilibiliBlockedError as exc:
            logger.warning("Achievement backfill blocked: %s", exc)
        finally:
            await client.aclose()
    return checked


async def stats_refresh_loop() -> None:
    while True:
        try:
            await refresh_due_creators()
        except Exception:
            logger.exception("Automatic creator profile refresh loop failed")
        try:
            await refresh_due_videos()
        except Exception:
            logger.exception("Automatic video stats refresh loop failed")
        try:
            await backfill_video_honors()
        except Exception:
            logger.exception("Automatic achievement backfill failed")
        await asyncio.sleep(REFRESH_CHECK_SECONDS)
