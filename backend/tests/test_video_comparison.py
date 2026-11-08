from datetime import datetime

from app.models import Video, VideoStats
from app.services.video_comparison import build_video_comparison


def _video(bvid: str, published_at: datetime) -> Video:
    return Video(
        bvid=bvid,
        uid=1,
        title=bvid,
        published_at=published_at,
    )


def _stats(
    bvid: str,
    views: int,
    *,
    likes: int = 0,
) -> VideoStats:
    return VideoStats(
        bvid=bvid,
        views=views,
        likes=likes,
        fetched_at=datetime(2026, 7, 2),
    )


def test_comparison_uses_recent_cohort_median_and_percentile():
    target_video = _video("TARGET", datetime(2026, 7, 1))
    target_stats = _stats("TARGET", 600, likes=60)
    videos = [
        (target_video, target_stats),
        (_video("PEER1", datetime(2026, 6, 20)), _stats("PEER1", 400, likes=40)),
        (_video("PEER2", datetime(2026, 6, 10)), _stats("PEER2", 500, likes=50)),
        (_video("PEER3", datetime(2026, 5, 20)), _stats("PEER3", 900, likes=90)),
        (_video("OLD", datetime(2024, 1, 1)), _stats("OLD", 1, likes=1)),
    ]

    comparison = build_video_comparison(target_video, target_stats, videos)

    assert comparison is not None
    assert comparison.baseline.sample_size == 3
    assert comparison.baseline.published_from == datetime(2026, 5, 20)
    assert comparison.baseline.published_to == datetime(2026, 6, 20)
    assert comparison.baseline_values[0] == 500
    assert comparison.percentage_diff[0] == 20
    assert comparison.percentile_ranks[0] == 66.7
    assert comparison.baseline_values[1] == 50
    assert comparison.percentage_diff[1] == 20


def test_comparison_requires_three_comparable_videos():
    target_video = _video("TARGET", datetime(2026, 7, 1))
    target_stats = _stats("TARGET", 600)
    videos = [
        (target_video, target_stats),
        (_video("PEER1", datetime(2026, 6, 20)), _stats("PEER1", 400)),
        (_video("PEER2", datetime(2026, 6, 10)), _stats("PEER2", 500)),
    ]

    assert build_video_comparison(target_video, target_stats, videos) is None


def test_zero_median_does_not_invent_a_percentage_change():
    target_video = _video("TARGET", datetime(2026, 7, 1))
    target_stats = _stats("TARGET", 10)
    videos = [
        (target_video, target_stats),
        (_video("PEER1", datetime(2026, 6, 20)), _stats("PEER1", 0)),
        (_video("PEER2", datetime(2026, 6, 10)), _stats("PEER2", 0)),
        (_video("PEER3", datetime(2026, 5, 20)), _stats("PEER3", 0)),
    ]

    comparison = build_video_comparison(target_video, target_stats, videos)

    assert comparison is not None
    assert comparison.percentage_diff[0] is None
    assert comparison.percentile_ranks[0] == 100
