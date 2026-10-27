from datetime import datetime

from app.schemas.base import APIModel


class GrowthPoint(APIModel):
    key: str
    min_days: float
    max_days: float | None
    median_views: int
    p25_views: int
    p75_views: int
    samples: int


class GrowthTimelinePoint(APIModel):
    fetched_at: datetime
    median_views: int
    p25_views: int
    p75_views: int
    samples: int


class CreatorGrowth(APIModel):
    points: list[GrowthPoint]
    timeline: list[GrowthTimelinePoint]
    video_count: int
    observation_count: int
    videos_with_history: int
    first_snapshot_at: datetime | None
    last_snapshot_at: datetime | None


class VideoGrowthPoint(APIModel):
    fetched_at: datetime
    views: int
    likes: int
    interaction_rate: float


class VideoGrowth(APIModel):
    bvid: str
    points: list[VideoGrowthPoint]


class AccountGrowthPoint(APIModel):
    fetched_at: datetime
    followers: int | None
    total_views: int | None
    total_likes: int | None


class CreatorAccountGrowth(APIModel):
    uid: int
    points: list[AccountGrowthPoint]
