from datetime import timedelta
from statistics import median

from app.models import Video, VideoStats
from app.schemas.analytics import ComparisonBaseline, VideoComparison

COMPARISON_METRICS = (
    ("views", "views"),
    ("likes", "likes"),
    ("coins", "coins"),
    ("favorites", "favorites"),
    ("shares", "shares"),
    ("danmaku", "danmaku_count"),
    ("comments", "comment_count"),
)

BASELINE_WINDOW_DAYS = 180
BASELINE_VIDEO_LIMIT = 20
MINIMUM_BASELINE_VIDEOS = 3


def _percentile_rank(value: float, peers: list[float]) -> float:
    """Rank a value without letting one extreme peer define the scale."""
    below = sum(peer < value for peer in peers)
    equal = sum(peer == value for peer in peers)
    return round((below + equal * 0.5) / len(peers) * 100, 1)


def build_video_comparison(
    target_video: Video,
    target_stats: VideoStats,
    videos: list[tuple[Video, VideoStats]],
) -> VideoComparison | None:
    """Compare a video with the creator's immediately preceding cohort.

    An all-time average mixes different stages of a creator's audience growth
    and lets a few outliers move every other video's baseline. A local cohort
    keeps the comparison tied to the channel's level around publication.
    """
    if target_video.published_at is None:
        return None

    window_start = target_video.published_at - timedelta(days=BASELINE_WINDOW_DAYS)
    peers = [
        (video, stats)
        for video, stats in videos
        if video.bvid != target_video.bvid
        and video.published_at is not None
        and window_start <= video.published_at < target_video.published_at
    ]
    peers.sort(key=lambda item: item[0].published_at, reverse=True)
    peers = peers[:BASELINE_VIDEO_LIMIT]
    if len(peers) < MINIMUM_BASELINE_VIDEOS:
        return None

    video_values: list[float] = []
    baseline_values: list[float] = []
    percentage_diff: list[float | None] = []
    percentile_ranks: list[float] = []

    for _, attribute in COMPARISON_METRICS:
        value = float(getattr(target_stats, attribute) or 0)
        peer_values = [
            float(getattr(stats, attribute) or 0)
            for _, stats in peers
        ]
        baseline = float(median(peer_values))

        video_values.append(value)
        baseline_values.append(round(baseline, 1))
        percentage_diff.append(
            round((value - baseline) / baseline * 100, 1)
            if baseline > 0
            else (0.0 if value == 0 else None)
        )
        percentile_ranks.append(_percentile_rank(value, peer_values))

    published_at = [video.published_at for video, _ in peers]
    return VideoComparison(
        metrics=[label for label, _ in COMPARISON_METRICS],
        video_values=video_values,
        baseline_values=baseline_values,
        percentage_diff=percentage_diff,
        percentile_ranks=percentile_ranks,
        baseline=ComparisonBaseline(
            sample_size=len(peers),
            window_days=BASELINE_WINDOW_DAYS,
            published_from=min(published_at),
            published_to=max(published_at),
        ),
    )
