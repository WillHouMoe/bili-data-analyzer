from datetime import UTC, datetime, timedelta

import pytest

from app.models import Video, VideoStats
from app.services.video_maintenance import (
    MAINTENANCE_UNLIMITED,
    MAINTENANCE_WINDOWED,
    base_refresh_interval,
    schedule_after_snapshot,
    video_is_maintained,
)


def test_base_refresh_interval_matches_the_confirmed_age_tiers():
    published = datetime(2026, 1, 1, tzinfo=UTC)
    cases = [
        (timedelta(hours=23), timedelta(hours=1)),
        (timedelta(days=2), timedelta(hours=2)),
        (timedelta(days=5), timedelta(hours=4)),
        (timedelta(days=10), timedelta(hours=8)),
        (timedelta(days=20), timedelta(hours=12)),
        (timedelta(days=100), timedelta(days=1)),
        (timedelta(days=400), timedelta(days=7)),
    ]
    for age, expected in cases:
        assert base_refresh_interval(published, published + age) == expected


def test_maintenance_window_stops_at_one_year_unless_unlimited():
    now = datetime(2026, 10, 27, tzinfo=UTC)
    active = Video(
        bvid="BVACTIVE",
        uid=1,
        title="Active",
        published_at=now - timedelta(days=364),
    )
    retired = Video(
        bvid="BVRETIRED",
        uid=1,
        title="Retired",
        published_at=now - timedelta(days=366),
    )

    assert video_is_maintained(active, MAINTENANCE_WINDOWED, now) is True
    assert video_is_maintained(retired, MAINTENANCE_WINDOWED, now) is False
    assert video_is_maintained(retired, MAINTENANCE_UNLIMITED, now) is True


def test_growth_spike_boosts_next_sample_for_six_observations():
    now = datetime(2026, 10, 27, 12, tzinfo=UTC)
    video = Video(
        bvid="BVSPIKE",
        uid=1,
        title="Spike",
        published_at=now - timedelta(days=40),
        stats_boost_remaining=0,
    )
    history = [
        VideoStats(
            bvid=video.bvid,
            views=1000 + index * 100,
            fetched_at=now - timedelta(days=4 - index),
        )
        for index in range(4)
    ]

    schedule_after_snapshot(
        video,
        history,
        now,
        views=2300,
    )

    assert video.stats_boost_remaining == 6
    assert video.next_stats_refresh_at == now + timedelta(hours=12)


@pytest.mark.asyncio
async def test_new_ranking_hit_boosts_even_without_a_growth_spike():
    now = datetime(2026, 10, 27, 12, tzinfo=UTC)
    video = Video(
        bvid="BVRANKED",
        uid=1,
        title="Ranked",
        published_at=now - timedelta(days=100),
        stats_boost_remaining=0,
    )
    history = [
        VideoStats(
            bvid=video.bvid,
            views=10_000 + index * 100,
            fetched_at=now - timedelta(days=4 - index),
        )
        for index in range(4)
    ]

    schedule_after_snapshot(
        video,
        history,
        now,
        views=10_320,
        ranking_fetched_at=now - timedelta(hours=1),
    )

    assert video.stats_boost_remaining == 6
    assert video.next_stats_refresh_at == now + timedelta(hours=12)
