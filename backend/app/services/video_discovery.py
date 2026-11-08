import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.core.background_tasks import scrape_semaphore
from app.core.config import settings
from app.core.database import async_session
from app.models import User, Video, VideoStats
from app.services.bilibili import BilibiliBlockedError, BilibiliClient
from app.services.fetch_credentials import (
    FetchCredentialError,
    load_fetch_credentials,
)
from app.services.video_achievements import record_video_honors
from app.services.video_maintenance import schedule_after_snapshot

logger = logging.getLogger(__name__)

VIDEO_DISCOVERY_CHECK_SECONDS = 60
VIDEO_DISCOVERY_CREATOR_BATCH = 8
VIDEO_DISCOVERY_RETRY_DELAY = timedelta(hours=1)


async def discover_new_videos() -> int:
    """Create library records for uploads newer than each creator's local max."""
    minutes = settings.NEW_VIDEO_REFRESH_MINUTES
    if minutes <= 0:
        return 0

    now = datetime.now(UTC)
    cutoff = now - timedelta(minutes=minutes)
    async with async_session() as db:
        creator_uids = select(Video.uid).distinct()
        users = (
            await db.execute(
                select(User)
                .where(
                    User.uid.in_(creator_uids),
                    (
                        User.video_scan_retry_at.is_(None)
                        | (User.video_scan_retry_at <= now)
                    ),
                    (
                        User.last_video_scan_at.is_(None)
                        | (User.last_video_scan_at < cutoff)
                    ),
                )
                .order_by(
                    User.last_video_scan_at.asc().nullsfirst(),
                    User.uid,
                )
                .limit(VIDEO_DISCOVERY_CREATOR_BATCH)
            )
        ).scalars().all()
        if not users:
            return 0
        try:
            sessdata, proxies = await load_fetch_credentials(db)
        except FetchCredentialError:
            logger.warning("New-video discovery skipped: credentials unreadable")
            return 0
        if not sessdata:
            logger.warning("New-video discovery skipped: SESSDATA is not configured")
            return 0
        uid_list = [user.uid for user in users]

    created = 0
    async with scrape_semaphore:
        client = BilibiliClient(sessdata=sessdata, proxy_urls=proxies)
        try:
            for uid in uid_list:
                async with async_session() as db:
                    user = await db.get(User, uid)
                    if user is None:
                        continue
                    try:
                        latest_existing = (
                            await db.execute(
                                select(func.max(Video.published_at)).where(
                                    Video.uid == uid
                                )
                            )
                        ).scalar_one_or_none()
                        if latest_existing is not None and latest_existing.tzinfo is None:
                            latest_existing = latest_existing.replace(tzinfo=UTC)
                        since_ts = (
                            int(latest_existing.timestamp())
                            if latest_existing is not None
                            else int((now - timedelta(days=30)).timestamp())
                        )
                        candidates = await client.get_video_stubs_since(
                            uid,
                            since_ts=since_ts,
                        )
                        existing_bvids = set(
                            (
                                await db.execute(
                                    select(Video.bvid).where(
                                        Video.bvid.in_(
                                            [video["bvid"] for video in candidates]
                                        )
                                    )
                                )
                            ).scalars().all()
                        )
                        for candidate in candidates:
                            bvid = candidate["bvid"]
                            if int(candidate.get("published_ts", 0) or 0) < since_ts:
                                continue
                            if bvid in existing_bvids:
                                continue
                            detail = await client.get_video_detail(bvid)
                            if detail.get("is_live_replay"):
                                continue
                            owner_uid = detail.get("owner_uid")
                            if owner_uid is not None and owner_uid != uid:
                                logger.warning(
                                    "Skipping new video %s for uid %s: owner is %s",
                                    bvid,
                                    uid,
                                    owner_uid,
                                )
                                continue

                            sampled_at = datetime.now(UTC)
                            published_at = datetime.fromtimestamp(
                                detail["published_at"],
                                tz=UTC,
                            )
                            video = Video(
                                bvid=bvid,
                                uid=uid,
                                title=detail["title"],
                                description=detail["description"],
                                cover_url=detail["cover_url"],
                                duration=detail["duration"],
                                published_at=published_at,
                                tags=detail["tags"],
                            )
                            db.add(video)
                            await db.flush()
                            stats = detail["stats"]
                            db.add(
                                VideoStats(
                                    bvid=bvid,
                                    views=stats["views"],
                                    likes=stats["likes"],
                                    coins=stats["coins"],
                                    favorites=stats["favorites"],
                                    shares=stats["shares"],
                                    danmaku_count=stats["danmaku_count"],
                                    comment_count=stats["comment_count"],
                                    fetched_at=sampled_at,
                                )
                            )
                            await record_video_honors(db, video, detail, sampled_at)
                            schedule_after_snapshot(
                                video,
                                [],
                                sampled_at,
                                stats["views"],
                            )
                            await db.commit()
                            existing_bvids.add(bvid)
                            created += 1
                            logger.info(
                                "Discovered new video %s for uid %s",
                                bvid,
                                uid,
                            )

                        user = await db.get(User, uid)
                        if user is not None:
                            user.last_video_scan_at = datetime.now(UTC)
                            user.video_scan_retry_at = None
                            await db.commit()
                    except BilibiliBlockedError:
                        await db.rollback()
                        user = await db.get(User, uid)
                        if user is not None:
                            user.video_scan_retry_at = (
                                datetime.now(UTC) + VIDEO_DISCOVERY_RETRY_DELAY
                            )
                            await db.commit()
                        raise
                    except Exception:
                        logger.exception(
                            "New-video discovery failed for uid %s",
                            uid,
                        )
                        await db.rollback()
                        user = await db.get(User, uid)
                        if user is not None:
                            user.video_scan_retry_at = (
                                datetime.now(UTC) + VIDEO_DISCOVERY_RETRY_DELAY
                            )
                            await db.commit()
        except BilibiliBlockedError as exc:
            logger.warning("New-video discovery blocked: %s", exc)
        finally:
            await client.aclose()
    return created


async def video_discovery_loop() -> None:
    while True:
        try:
            await discover_new_videos()
        except Exception:
            logger.exception("Automatic new-video discovery loop failed")
        await asyncio.sleep(VIDEO_DISCOVERY_CHECK_SECONDS)
