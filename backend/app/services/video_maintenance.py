"""Age-based video snapshot maintenance and hotness boost scheduling."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from statistics import median

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AppSettings, Video, VideoStats

MAINTENANCE_MODE_KEY = "video_maintenance_mode"
MAINTENANCE_WINDOWED = "windowed"
MAINTENANCE_UNLIMITED = "unlimited"
MAINTENANCE_MODES = {MAINTENANCE_WINDOWED, MAINTENANCE_UNLIMITED}
MAINTENANCE_WINDOW_DAYS = 365

BOOST_SAMPLE_COUNT = 6
BOOST_MULTIPLIER = 2.0
MIN_BOOST_INTERVAL = timedelta(hours=1)


@dataclass(frozen=True)
class MaintenanceTier:
    key: str
    max_age: timedelta
    interval: timedelta


MAINTENANCE_TIERS = (
    MaintenanceTier("under1d", timedelta(days=1), timedelta(hours=1)),
    MaintenanceTier("1to3d", timedelta(days=3), timedelta(hours=2)),
    MaintenanceTier("3to7d", timedelta(days=7), timedelta(hours=4)),
    MaintenanceTier("7to14d", timedelta(days=14), timedelta(hours=8)),
    MaintenanceTier("14to30d", timedelta(days=30), timedelta(hours=12)),
    MaintenanceTier("30to365d", timedelta(days=365), timedelta(days=1)),
    MaintenanceTier("over365d", timedelta.max, timedelta(days=7)),
)


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def normalize_maintenance_mode(value: str | None) -> str:
    return value if value in MAINTENANCE_MODES else MAINTENANCE_WINDOWED


async def get_maintenance_mode(db: AsyncSession) -> str:
    row = await db.get(AppSettings, MAINTENANCE_MODE_KEY)
    return normalize_maintenance_mode(row.value if row else None)


def video_is_maintained(
    video: Video,
    mode: str,
    now: datetime | None = None,
) -> bool:
    if normalize_maintenance_mode(mode) == MAINTENANCE_UNLIMITED:
        return True
    if video.published_at is None:
        return True
    current = as_utc(now or datetime.now(UTC))
    published = as_utc(video.published_at)
    return current - published <= timedelta(days=MAINTENANCE_WINDOW_DAYS)


def base_refresh_interval(
    published_at: datetime | None,
    now: datetime | None = None,
) -> timedelta:
    if published_at is None:
        return timedelta(days=1)
    current = as_utc(now or datetime.now(UTC))
    age = max(timedelta(0), current - as_utc(published_at))
    for tier in MAINTENANCE_TIERS:
        if age <= tier.max_age:
            return tier.interval
    return MAINTENANCE_TIERS[-1].interval


def _refresh_jitter(video: Video) -> timedelta:
    digest = hashlib.sha256(video.bvid.encode()).hexdigest()
    seconds = int(digest[:8], 16) % (10 * 60)
    return timedelta(seconds=seconds)


def _is_growth_spike(
    video: Video,
    history: list[VideoStats],
    sample_at: datetime,
    views: int,
) -> bool:
    if video.published_at is None:
        return False
    current = as_utc(sample_at)
    if current - as_utc(video.published_at) <= timedelta(days=1):
        return False
    if len(history) < 4:
        return False

    points = [(as_utc(item.fetched_at), item.views) for item in history[-4:]]
    points.append((current, views))
    rates: list[float] = []
    for (previous_at, previous_views), (next_at, next_views) in zip(
        points,
        points[1:],
    ):
        elapsed = (next_at - previous_at).total_seconds()
        if elapsed <= 0:
            continue
        rates.append(max(0, next_views - previous_views) / elapsed)
    if len(rates) < 3:
        return False

    baseline = median(rates[-4:-1])
    current_rate = rates[-1]
    current_delta = max(0, views - points[-2][1])
    significant_delta = max(10, int(views * 0.001))
    if current_delta < significant_delta:
        return False
    return current_rate > 0 and (
        baseline == 0 or current_rate >= baseline * BOOST_MULTIPLIER
    )


def schedule_after_snapshot(
    video: Video,
    history: list[VideoStats],
    sample_at: datetime,
    views: int,
    ranking_fetched_at: datetime | None = None,
) -> None:
    """Set the next due time, accelerating after a spike or fresh ranking hit."""
    sampled = as_utc(sample_at)
    ranking_is_new = ranking_fetched_at is not None and (
        not history
        or as_utc(ranking_fetched_at) > as_utc(history[-1].fetched_at)
    )
    if _is_growth_spike(video, history, sampled, views) or ranking_is_new:
        video.stats_boost_remaining = BOOST_SAMPLE_COUNT
    else:
        video.stats_boost_remaining = max(
            0,
            (video.stats_boost_remaining or 0) - 1,
        )

    delay = base_refresh_interval(video.published_at, sampled)
    if video.stats_boost_remaining > 0:
        delay = max(MIN_BOOST_INTERVAL, delay / 2)
    video.next_stats_refresh_at = sampled + delay


def defer_video_after_failure(video: Video, now: datetime | None = None) -> None:
    video.next_stats_refresh_at = as_utc(now or datetime.now(UTC)) + timedelta(
        hours=1
    )


async def ensure_video_refresh_schedules(db: AsyncSession) -> int:
    """Give legacy and newly linked videos a staggered next due time."""
    videos = (
        await db.execute(
            select(Video).where(Video.next_stats_refresh_at.is_(None))
        )
    ).scalars().all()
    if not videos:
        return 0

    bvids = [video.bvid for video in videos]
    stats_rows = (
        await db.execute(
            select(VideoStats)
            .where(VideoStats.bvid.in_(bvids))
            .order_by(VideoStats.fetched_at, VideoStats.id)
        )
    ).scalars().all()
    latest: dict[str, VideoStats] = {}
    for stats in stats_rows:
        latest[stats.bvid] = stats

    now = datetime.now(UTC)
    for video in videos:
        previous = latest.get(video.bvid)
        anchor = as_utc(previous.fetched_at) if previous else now
        interval = base_refresh_interval(video.published_at, anchor)
        video.next_stats_refresh_at = (
            anchor + interval + _refresh_jitter(video)
        )
    return len(videos)
