import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RankingEntry, Video

HIGHEST_RANK_RE = re.compile(r"全站排行榜最高第(\d+)名")
WEEKLY_NUMBER_RE = re.compile(r"第(\d+)期")


async def _upsert_honor(
    db: AsyncSession,
    video: Video,
    detail: dict,
    *,
    kind: str,
    period: str,
    rank: int,
    period_name: str,
    fetched_at: datetime,
) -> None:
    existing = (
        await db.execute(
            select(RankingEntry).where(
                RankingEntry.kind == kind,
                RankingEntry.period == period,
                RankingEntry.bvid == video.bvid,
            )
        )
    ).scalar_one_or_none()
    stats = detail["stats"]
    if existing is not None:
        existing.rank = min(existing.rank, rank) if rank > 0 else existing.rank
        existing.period_name = existing.period_name or period_name
        existing.title = detail["title"]
        existing.owner_name = (detail.get("owner_name") or existing.owner_name)
        existing.cover_url = detail.get("cover_url")
        existing.views = stats["views"]
        existing.likes = stats["likes"]
        existing.fetched_at = fetched_at
        return

    db.add(
        RankingEntry(
            kind=kind,
            period=period,
            period_name=period_name,
            rank=rank,
            bvid=video.bvid,
            title=detail["title"],
            owner_uid=detail.get("owner_uid") or video.uid,
            owner_name=detail.get("owner_name") or "",
            cover_url=detail.get("cover_url"),
            views=stats["views"],
            likes=stats["likes"],
            score=0,
            fetched_at=fetched_at,
        )
    )


async def record_video_honors(
    db: AsyncSession,
    video: Video,
    detail: dict,
    fetched_at: datetime | None = None,
) -> None:
    """Persist Bilibili's long-lived weekly and highest-ranking achievements."""
    now = fetched_at or datetime.now(UTC)
    for honor in detail.get("honors") or []:
        description = str(honor.get("desc") or "").strip()
        honor_type = honor.get("type")
        if honor_type == 2:
            number = int(honor.get("weekly_recommend_num") or 0)
            if number <= 0:
                match = WEEKLY_NUMBER_RE.search(description)
                number = int(match.group(1)) if match else 0
            if number <= 0:
                continue
            await _upsert_honor(
                db,
                video,
                detail,
                kind="weekly",
                period=f"weekly-{number}",
                rank=0,
                period_name=description or f"第{number}期每周必看",
                fetched_at=now,
            )
        elif honor_type == 3:
            match = HIGHEST_RANK_RE.search(description)
            if match is None:
                continue
            await _upsert_honor(
                db,
                video,
                detail,
                kind="highest",
                period="all-time",
                rank=int(match.group(1)),
                period_name=description,
                fetched_at=now,
            )
    video.honors_checked_at = now
