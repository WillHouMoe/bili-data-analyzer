from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CreatorStatsSnapshot(Base):
    __tablename__ = "creator_stats_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uid: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.uid", ondelete="CASCADE"),
        nullable=False,
    )
    followers: Mapped[int | None] = mapped_column(Integer, nullable=True)
    following: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_views: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_likes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    archive_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
