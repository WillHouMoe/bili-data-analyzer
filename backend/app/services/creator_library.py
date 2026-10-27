"""Read models and aggregation helpers for a creator's merged video library.

Queries remain useful as an audit trail of individual fetch requests, but they
are no longer the user's primary directory. A creator's library is the union of
every video linked to that UID, with the newest snapshot of each video's stats.
"""
from dataclasses import dataclass
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Query, User, Video, VideoStats


@dataclass
class CreatorSnapshot:
    user: User
    videos: dict[str, tuple[Video, VideoStats]]
    query_count: int
    status: str
    progress: str | None
    error_message: str | None
    start_date: date | None
    end_date: date | None
    total_views: int
    total_likes: int
    total_coins: int
    total_favorites: int
    total_shares: int
    total_danmaku: int
    total_comments: int

    @property
    def video_count(self) -> int:
        return len(self.videos)


def _is_newer(candidate: VideoStats, current: VideoStats) -> bool:
    return (candidate.fetched_at, candidate.id) > (current.fetched_at, current.id)


async def latest_videos_for_creator(
    db: AsyncSession, uid: int
) -> dict[str, tuple[Video, VideoStats]]:
    result = await db.execute(
        select(Video, VideoStats)
        .join(VideoStats, VideoStats.bvid == Video.bvid)
        .where(Video.uid == uid)
    )
    latest: dict[str, tuple[Video, VideoStats]] = {}
    for video, stats in result.all():
        current = latest.get(video.bvid)
        if current is None or _is_newer(stats, current[1]):
            latest[video.bvid] = (video, stats)
    return latest


async def creator_snapshot(db: AsyncSession, uid: int) -> CreatorSnapshot | None:
    user = await db.get(User, uid)
    if not user:
        return None

    videos = await latest_videos_for_creator(db, uid)
    queries = (
        await db.execute(
            select(Query)
            .where(Query.uid == uid)
            .order_by(Query.created_at.desc(), Query.id.desc())
        )
    ).scalars().all()
    query_count = (
        await db.execute(
            select(func.count()).select_from(Query).where(Query.uid == uid)
        )
    ).scalar_one()

    latest_query = queries[0] if queries else None
    published_dates = [
        video.published_at.date()
        for video, _ in videos.values()
        if video.published_at is not None
    ]
    if published_dates:
        start_date = min(published_dates)
        end_date = max(published_dates)
    elif latest_query:
        start_date = latest_query.start_date
        end_date = latest_query.end_date
    else:
        start_date = None
        end_date = None

    values = list(videos.values())
    query_status = latest_query.status if latest_query else "done"
    if query_status in ("pending", "fetching"):
        status = query_status
    elif values:
        status = "done"
    else:
        status = query_status

    return CreatorSnapshot(
        user=user,
        videos=videos,
        query_count=query_count,
        status=status,
        progress=latest_query.progress if latest_query else None,
        error_message=latest_query.error_message if latest_query else None,
        start_date=start_date,
        end_date=end_date,
        total_views=sum(stats.views for _, stats in values),
        total_likes=sum(stats.likes for _, stats in values),
        total_coins=sum(stats.coins for _, stats in values),
        total_favorites=sum(stats.favorites for _, stats in values),
        total_shares=sum(stats.shares for _, stats in values),
        total_danmaku=sum(stats.danmaku_count for _, stats in values),
        total_comments=sum(stats.comment_count for _, stats in values),
    )


def creator_meta(snapshot: CreatorSnapshot) -> dict:
    """Fields shared by the list and detail schemas."""
    return {
        "uid": snapshot.user.uid,
        "name": snapshot.user.name,
        "avatar_url": snapshot.user.avatar_url,
        "start_date": snapshot.start_date,
        "end_date": snapshot.end_date,
        "video_count": snapshot.video_count,
        "query_count": snapshot.query_count,
        "total_views": snapshot.total_views,
        "followers": snapshot.user.followers,
        "following": snapshot.user.following,
        "creator_total_views": snapshot.user.creator_total_views,
        "creator_total_likes": snapshot.user.creator_total_likes,
        "archive_count": snapshot.user.archive_count,
        "profile_stats_updated_at": snapshot.user.profile_stats_updated_at,
        "last_fetched_at": snapshot.user.last_fetched_at,
        "last_stats_refresh_at": snapshot.user.last_stats_refresh_at,
        "refresh_status": snapshot.user.refresh_status or "idle",
        "refresh_progress": snapshot.user.refresh_progress,
        "refresh_error": snapshot.user.refresh_error,
        "status": snapshot.status,
        "progress": snapshot.progress,
        "error_message": snapshot.error_message,
    }
