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


class VideoComparison(APIModel):
    """For radar chart: this video's stats vs query average"""
    metrics: list[str]
    video_values: list[float]
    average_values: list[float]
    percentage_diff: list[float]
    max_values: list[float]  # Global max for each metric across all videos in query
