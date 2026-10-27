from datetime import date, datetime

from pydantic import Field, model_validator

from app.schemas.base import APIModel


class FetchRequest(APIModel):
    uid: int = Field(gt=0)
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def _check_date_range(self) -> "FetchRequest":
        if self.start_date > self.end_date:
            raise ValueError("start_date must not be after end_date")
        return self


class FetchResponse(APIModel):
    query_id: int
    uid: int
    status: str


class QuerySummary(APIModel):
    id: int
    uid: int
    user_name: str | None
    start_date: date
    end_date: date
    status: str
    progress: str | None
    video_count: int
    total_views: int
    created_at: datetime


class QueryDetail(QuerySummary):
    error_message: str | None
    total_likes: int
    total_coins: int
    total_favorites: int
    total_shares: int
    total_danmaku: int
    total_comments: int
