import asyncio
import logging
import random
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.background_tasks import scrape_semaphore
from app.core.database import async_session
from app.models import Query, QueryVideo, User, Video, VideoStats
from app.services.bilibili import BilibiliBlockedError, BilibiliClient
from app.services.creator_profile import apply_creator_info
from app.services.creator_stats_history import record_creator_stats_snapshot

logger = logging.getLogger(__name__)

# Batch processing config to avoid detection
BATCH_SIZE = 15  # Process 15 videos per batch
BATCH_BREAK_MIN = 8  # Min seconds between batches
BATCH_BREAK_MAX = 15  # Max seconds between batches


async def _record_fetch_error(db: AsyncSession, query: Query, message: str) -> None:
    """Record a terminal error after rolling back any failed transaction.

    A flush failure leaves the session unusable. Committing the status directly
    then raises PendingRollbackError, which leaves the query at its last
    progress string and makes a dead task look like it is still running.
    """
    await db.rollback()
    query.status = "error"
    query.error_message = message
    query.progress = None
    await db.commit()


async def run_fetch(query_id: int, uid: int, start_date, end_date, sessdata: str | None, proxy_urls: list[str] | None = None):
    """Background task: fetch all video data for a query.

    Only one scrape runs at a time across the whole process (scrape_semaphore),
    since two concurrent BilibiliClient instances would otherwise double the
    effective request rate into Bilibili's -799 risk control.
    """
    async with scrape_semaphore:
        async with async_session() as db:
            query = await db.get(Query, query_id)
            if not query:
                return
            client = BilibiliClient(sessdata=sessdata, proxy_urls=proxy_urls)
            try:
                # Step 1: Fetch user info
                query.status = "fetching"
                query.progress = "Fetching user info..."
                await db.commit()

                user_info = await client.get_user_info(uid)
                existing_user = await db.get(User, uid)
                if existing_user is None:
                    existing_user = User(
                        uid=uid,
                        name=user_info["name"],
                        avatar_url=user_info["avatar_url"],
                    )
                    db.add(existing_user)
                apply_creator_info(existing_user, user_info)
                await record_creator_stats_snapshot(db, existing_user)
                query.user_name = user_info["name"]
                await db.commit()

                # Step 2: Fetch video list
                video_index = await client.get_video_index_in_range(uid, start_date, end_date)
                all_videos = []
                for v in video_index["videos"]:
                    pub_ts = int(v.get("published_ts") or v.get("created") or 0)
                    if pub_ts <= 0:
                        continue
                    pub_date = datetime.fromtimestamp(pub_ts, tz=UTC).date()
                    if start_date <= pub_date <= end_date:
                        all_videos.append(v)

                total = len(all_videos)
                query.video_count = total
                await db.commit()
                existing_by_bvid = {
                    video.bvid: video
                    for video in (
                        await db.execute(select(Video))
                    ).scalars().all()
                }
                had_creator_videos = any(
                    video.uid == uid for video in existing_by_bvid.values()
                )
                already_linked = set(
                    (
                        await db.execute(
                            select(QueryVideo.bvid).where(
                                QueryVideo.query_id == query_id
                            )
                        )
                    ).scalars().all()
                )

                # Step 3: Fetch aggregate details only for videos this creator
                # library has not seen before. Re-requesting a covered range
                # should reuse local videos rather than scrape the whole index
                # again.
                for i, v in enumerate(all_videos, 1):
                    query.progress = f"Checking video {i}/{total}"
                    await db.commit()

                    bvid = v["bvid"]
                    existing = existing_by_bvid.get(bvid)
                    if existing is not None and existing.uid == uid:
                        if bvid not in already_linked:
                            db.add(QueryVideo(query_id=query_id, bvid=bvid))
                            already_linked.add(bvid)
                        continue

                    detail = await client.get_video_detail(bvid)
                    if detail.get("is_live_replay"):
                        logger.info("Skipping live replay video %s", bvid)
                        continue
                    owner_uid = detail.get("owner_uid")
                    if owner_uid is not None and owner_uid != uid:
                        logger.warning(
                            "Skipping %s for uid %s: video belongs to uid %s",
                            bvid,
                            uid,
                            owner_uid,
                        )
                        continue
                    if (
                        existing is not None
                        and existing.uid != uid
                        and owner_uid is None
                    ):
                        logger.warning(
                            "Skipping %s for uid %s: existing owner is uid %s "
                            "and the detail response did not confirm ownership",
                            bvid,
                            uid,
                            existing.uid,
                        )
                        continue

                    # Upsert Video
                    published_at = datetime.fromtimestamp(detail["published_at"], tz=UTC)
                    if not existing:
                        video = Video(
                            bvid=bvid, uid=uid, title=detail["title"],
                            description=detail["description"],
                            cover_url=detail["cover_url"], duration=detail["duration"],
                            published_at=published_at,
                            tags=detail["tags"],
                        )
                        db.add(video)
                    else:
                        if existing.uid != uid:
                            logger.warning(
                                "Correcting owner for %s from uid %s to uid %s",
                                bvid,
                                existing.uid,
                                uid,
                            )
                            existing.uid = uid
                        existing.title = detail["title"]
                        existing.description = detail["description"]
                        existing.cover_url = detail["cover_url"]
                        existing.duration = detail["duration"]
                        existing.published_at = published_at
                        existing.tags = detail["tags"]
                        existing.updated_at = datetime.now(UTC)

                    # QueryVideo has no ORM relationship to Video, so SQLAlchemy
                    # cannot infer the insert order. SQLite enforces the foreign
                    # key, and query_videos can otherwise be inserted before the
                    # video it references, rolling back the first video.
                    await db.flush()

                    # Add stats snapshot
                    s = detail["stats"]
                    db.add(VideoStats(
                        bvid=bvid, views=s["views"], likes=s["likes"],
                        coins=s["coins"], favorites=s["favorites"],
                        shares=s["shares"], danmaku_count=s["danmaku_count"],
                        comment_count=s["comment_count"],
                    ))

                    # Link to query
                    if bvid not in already_linked:
                        db.add(QueryVideo(query_id=query_id, bvid=bvid))
                        already_linked.add(bvid)
                    await db.commit()

                    # Batch break: pause after every BATCH_SIZE videos
                    if i % BATCH_SIZE == 0 and i < total:
                        break_time = random.uniform(BATCH_BREAK_MIN, BATCH_BREAK_MAX)
                        logger.info("Batch break after %d videos, pausing for %.1fs", i, break_time)
                        await asyncio.sleep(break_time)

                # Step 4: Compute aggregates
                await db.commit()
                query.video_count = len(already_linked)
                stmt = (select(VideoStats)
                        .join(QueryVideo, QueryVideo.bvid == VideoStats.bvid)
                        .where(QueryVideo.query_id == query_id))
                result = await db.execute(stmt)
                stats_list = result.scalars().all()

                # Use latest stats per video
                latest: dict[str, VideoStats] = {}
                for s in stats_list:
                    if s.bvid not in latest or s.fetched_at > latest[s.bvid].fetched_at:
                        latest[s.bvid] = s

                query.total_views = sum(s.views for s in latest.values())
                query.total_likes = sum(s.likes for s in latest.values())
                query.total_coins = sum(s.coins for s in latest.values())
                query.total_favorites = sum(s.favorites for s in latest.values())
                query.total_shares = sum(s.shares for s in latest.values())
                query.total_danmaku = sum(s.danmaku_count for s in latest.values())
                query.total_comments = sum(s.comment_count for s in latest.values())
                if latest and not had_creator_videos:
                    creator = await db.get(User, uid)
                    if creator is not None:
                        creator.last_stats_refresh_at = datetime.now(UTC)
                        creator.refresh_retry_at = None
                        creator.refresh_status = "done"
                        creator.refresh_progress = None
                        creator.refresh_error = None
                query.status = "done"
                query.progress = None
                await db.commit()

            except BilibiliBlockedError as e:
                # Actionable and safe to show: the text is ours, not an upstream
                # payload, so surfacing it leaks nothing while telling the user
                # the one thing that actually fixes the run.
                logger.warning("Fetch blocked for query %s: %s", query_id, e)
                await _record_fetch_error(db, query, str(e))
            except Exception:
                logger.exception("Fetch task failed for query %s", query_id)
                await _record_fetch_error(
                    db, query, "Fetch failed. Check server logs for details."
                )
            finally:
                await client.aclose()
