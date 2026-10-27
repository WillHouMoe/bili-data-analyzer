from datetime import datetime

from sqlalchemy import DateTime, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    uid: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    followers: Mapped[int | None] = mapped_column(Integer, nullable=True)
    following: Mapped[int | None] = mapped_column(Integer, nullable=True)
    creator_total_views: Mapped[int | None] = mapped_column(Integer, nullable=True)
    creator_total_likes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    archive_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    profile_stats_updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_stats_refresh_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    refresh_status: Mapped[str] = mapped_column(Text, default="idle")
    refresh_progress: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_retry_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
