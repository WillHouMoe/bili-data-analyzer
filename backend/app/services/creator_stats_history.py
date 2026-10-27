from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CreatorStatsSnapshot, User


async def record_creator_stats_snapshot(
    db: AsyncSession,
    user: User,
    fetched_at: datetime | None = None,
) -> None:
    if all(
        value is None
        for value in (
            user.followers,
            user.following,
            user.creator_total_views,
            user.creator_total_likes,
            user.archive_count,
        )
    ):
        return
    db.add(
        CreatorStatsSnapshot(
            uid=user.uid,
            followers=user.followers,
            following=user.following,
            total_views=user.creator_total_views,
            total_likes=user.creator_total_likes,
            archive_count=user.archive_count,
            fetched_at=fetched_at or datetime.now(UTC),
        )
    )
