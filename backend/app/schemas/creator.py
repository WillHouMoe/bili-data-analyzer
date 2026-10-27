from datetime import date, datetime

from app.schemas.base import APIModel
from app.schemas.video import RankingMatch


class CreatorSummary(APIModel):
    uid: int
    name: str
    avatar_url: str | None
    start_date: date | None
    end_date: date | None
    video_count: int
    query_count: int
    total_views: int
    followers: int | None
    following: int | None
    creator_total_views: int | None
    creator_total_likes: int | None
    archive_count: int | None
    profile_stats_updated_at: datetime | None
    last_fetched_at: datetime | None
    last_stats_refresh_at: datetime | None
    refresh_status: str
    refresh_progress: str | None
    refresh_error: str | None
    status: str
    progress: str | None
    error_message: str | None


class CreatorDetail(CreatorSummary):
    total_likes: int
    total_coins: int
    total_favorites: int
    total_shares: int
    total_danmaku: int
    total_comments: int
    rankings: list[RankingMatch]
