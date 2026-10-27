from datetime import datetime

from app.schemas.base import APIModel


class VideoStatsSchema(APIModel):
    views: int
    likes: int
    coins: int
    favorites: int
    shares: int
    danmaku_count: int
    comment_count: int
    interaction_rate: float  # computed: (likes+coins+favorites+shares)/views*100


class VideoSummary(APIModel):
    bvid: str
    title: str
    cover_url: str | None
    duration: int
    published_at: datetime | None
    tags: str | None
    stats: VideoStatsSchema


class RankingMatch(APIModel):
    kind: str
    period: str
    period_name: str | None
    rank: int
    bvid: str
    title: str
    views: int
    likes: int
    fetched_at: datetime
    in_library: bool = False


class VideoDetail(VideoSummary):
    description: str | None
    rankings: list[RankingMatch]


class PaginatedVideos(APIModel):
    items: list[VideoSummary]
    total: int
    page: int
    page_size: int
    total_pages: int
