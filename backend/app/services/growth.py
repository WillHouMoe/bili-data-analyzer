from collections import defaultdict
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Video, VideoStats
from app.schemas.growth import (
    CreatorGrowth,
    GrowthPoint,
    GrowthTimelinePoint,
    VideoGrowth,
    VideoGrowthPoint,
)

GROWTH_BUCKETS = (
    ("under1", 0.0, 1.0),
    ("1to3", 1.0, 3.0),
    ("3to7", 3.0, 7.0),
    ("7to14", 7.0, 14.0),
    ("14to30", 14.0, 30.0),
    ("30to90", 30.0, 90.0),
    ("90to180", 90.0, 180.0),
    ("over180", 180.0, None),
)


def _bucket_for_age(age_days: float) -> tuple[str, float, float | None] | None:
    if age_days < 0:
        return None
    for key, minimum, maximum in GROWTH_BUCKETS:
        if age_days >= minimum and (maximum is None or age_days < maximum):
            return key, minimum, maximum
    return None


def _percentile(values: list[int], fraction: float) -> int:
    if len(values) == 1:
        return values[0]
    position = (len(values) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    weight = position - lower
    return round(values[lower] * (1 - weight) + values[upper] * weight)


async def creator_growth(db: AsyncSession, uid: int) -> CreatorGrowth:
    rows = (
        await db.execute(
            select(Video, VideoStats)
            .join(VideoStats, VideoStats.bvid == Video.bvid)
            .where(Video.uid == uid, Video.published_at.is_not(None))
        )
    ).all()

    latest_per_bucket: dict[tuple[str, str], tuple[datetime, int, VideoStats]] = {}
    observations_per_video: dict[str, int] = defaultdict(int)
    snapshot_times: list[datetime] = []
    video_uids: set[str] = set()

    for video, stats in rows:
        age_seconds = (stats.fetched_at - video.published_at).total_seconds()
        bucket = _bucket_for_age(age_seconds / 86400)
        if bucket is None:
            continue
        video_uids.add(video.bvid)
        observations_per_video[video.bvid] += 1
        snapshot_times.append(stats.fetched_at)
        key = (video.bvid, bucket[0])
        current = latest_per_bucket.get(key)
        if current is None or (stats.fetched_at, stats.id) > (current[0], current[2].id):
            latest_per_bucket[key] = (stats.fetched_at, bucket[1], stats)

    values_by_bucket: dict[str, list[int]] = defaultdict(list)
    for (_, bucket_key), (_, _, stats) in latest_per_bucket.items():
        values_by_bucket[bucket_key].append(stats.views)

    points: list[GrowthPoint] = []
    for key, minimum, maximum in GROWTH_BUCKETS:
        values = sorted(values_by_bucket.get(key, []))
        if not values:
            continue
        points.append(
            GrowthPoint(
                key=key,
                min_days=minimum,
                max_days=maximum,
                median_views=_percentile(values, 0.5),
                p25_views=_percentile(values, 0.25),
                p75_views=_percentile(values, 0.75),
                samples=len(values),
            )
        )

    observations_by_time: dict[
        datetime, list[tuple[Video, VideoStats]]
    ] = defaultdict(list)
    for video, stats in rows:
        observations_by_time[stats.fetched_at].append((video, stats))

    latest_observed: dict[str, VideoStats] = {}
    timeline: list[GrowthTimelinePoint] = []
    for fetched_at in sorted(observations_by_time):
        for video, stats in observations_by_time[fetched_at]:
            current = latest_observed.get(video.bvid)
            if current is None or (stats.fetched_at, stats.id) > (
                current.fetched_at,
                current.id,
            ):
                latest_observed[video.bvid] = stats
        values = sorted(point.views for point in latest_observed.values())
        if not values:
            continue
        timeline.append(
            GrowthTimelinePoint(
                fetched_at=fetched_at,
                median_views=_percentile(values, 0.5),
                p25_views=_percentile(values, 0.25),
                p75_views=_percentile(values, 0.75),
                samples=len(values),
            )
        )

    return CreatorGrowth(
        points=points,
        timeline=timeline,
        video_count=len(video_uids),
        observation_count=len(rows),
        videos_with_history=sum(
            count > 1 for count in observations_per_video.values()
        ),
        first_snapshot_at=min(snapshot_times) if snapshot_times else None,
        last_snapshot_at=max(snapshot_times) if snapshot_times else None,
    )


async def video_growth(db: AsyncSession, bvid: str) -> VideoGrowth:
    stats = (
        await db.execute(
            select(VideoStats)
            .where(VideoStats.bvid == bvid)
            .order_by(VideoStats.fetched_at, VideoStats.id)
        )
    ).scalars().all()
    return VideoGrowth(
        bvid=bvid,
        points=[
            VideoGrowthPoint(
                fetched_at=point.fetched_at,
                views=point.views,
                likes=point.likes,
                interaction_rate=(
                    round(
                        (
                            point.likes
                            + point.coins
                            + point.favorites
                            + point.shares
                        )
                        / point.views
                        * 100,
                        2,
                    )
                    if point.views
                    else 0.0
                ),
            )
            for point in stats
        ],
    )
