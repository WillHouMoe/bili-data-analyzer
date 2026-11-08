from datetime import datetime

from app.schemas.base import APIModel


class StatsSummary(APIModel):
    total_views: int
    total_likes: int
    total_coins: int
    total_favorites: int
    total_shares: int
    total_danmaku: int
    total_comments: int
    video_count: int


class TrendPoint(APIModel):
    date: str
    views: int


class InteractionData(APIModel):
    likes: int
    coins: int
    favorites: int
    shares: int


class ComparisonBaseline(APIModel):
    """The local cohort and window used as the comparison reference."""

    sample_size: int
    window_days: int
    published_from: datetime
    published_to: datetime


class VideoComparison(APIModel):
    """A video's values and standing against nearby earlier uploads."""

    metrics: list[str]
    video_values: list[float]
    baseline_values: list[float]
    percentage_diff: list[float | None]
    percentile_ranks: list[float]
    baseline: ComparisonBaseline
