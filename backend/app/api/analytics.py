from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from fastapi import Query as QueryParam
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.time import as_china_time
from app.models import Query, QueryVideo, Video, VideoStats
from app.schemas.analytics import (
    InteractionData,
    StatsSummary,
    TrendPoint,
    VideoComparison,
)
from app.services.video_comparison import build_video_comparison

router = APIRouter()


@router.get("/queries/{query_id}/stats/summary", response_model=StatsSummary)
async def stats_summary(query_id: int, db: AsyncSession = Depends(get_db)):
    query = await db.get(Query, query_id)
    if not query:
        raise HTTPException(status_code=404)
    return StatsSummary(
        total_views=query.total_views, total_likes=query.total_likes,
        total_coins=query.total_coins, total_favorites=query.total_favorites,
        total_shares=query.total_shares, total_danmaku=query.total_danmaku,
        total_comments=query.total_comments, video_count=query.video_count,
    )


@router.get("/queries/{query_id}/stats/trend", response_model=list[TrendPoint])
async def stats_trend(query_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Video, VideoStats)
        .join(QueryVideo, QueryVideo.bvid == Video.bvid)
        .join(VideoStats, VideoStats.bvid == Video.bvid)
        .where(QueryVideo.query_id == query_id)
    )

    latest: dict[str, tuple[Video, VideoStats]] = {}
    for video, stats in result.all():
        if video.bvid not in latest or stats.fetched_at > latest[video.bvid][1].fetched_at:
            latest[video.bvid] = (video, stats)

    dates = [
        as_china_time(video.published_at)
        for video, _ in latest.values()
        if video.published_at
    ]
    if not dates:
        return []

    span_days = (max(dates) - min(dates)).days
    if span_days <= 31:
        fmt = "%Y-%m-%d"
    elif span_days <= 180:
        fmt = "week"
    else:
        fmt = "%Y-%m"

    bucket: dict[str, int] = defaultdict(int)
    for video, stats in latest.values():
        if not video.published_at:
            continue
        published_at = as_china_time(video.published_at)
        if fmt == "week":
            iso = published_at.isocalendar()
            key = f"{iso[0]}-W{iso[1]:02d}"
        else:
            key = published_at.strftime(fmt)
        bucket[key] += stats.views

    return [TrendPoint(date=key, views=views) for key, views in sorted(bucket.items())]


@router.get("/queries/{query_id}/stats/interaction", response_model=InteractionData)
async def stats_interaction(query_id: int, db: AsyncSession = Depends(get_db)):
    query = await db.get(Query, query_id)
    if not query:
        raise HTTPException(status_code=404)
    return InteractionData(
        likes=query.total_likes, coins=query.total_coins,
        favorites=query.total_favorites, shares=query.total_shares,
    )


@router.get("/videos/{bvid}/stats/comparison", response_model=VideoComparison)
async def video_comparison(
    bvid: str,
    query_id: int = QueryParam(...),
    db: AsyncSession = Depends(get_db),
):
    all_result = await db.execute(
        select(Video, VideoStats)
        .join(QueryVideo, QueryVideo.bvid == Video.bvid)
        .join(VideoStats, VideoStats.bvid == Video.bvid)
        .where(QueryVideo.query_id == query_id)
    )
    latest: dict[str, tuple[Video, VideoStats]] = {}
    for video, stats in all_result.all():
        current = latest.get(video.bvid)
        if current is None or (stats.fetched_at, stats.id) > (
            current[1].fetched_at,
            current[1].id,
        ):
            latest[video.bvid] = (video, stats)

    target = latest.get(bvid)
    if target is None:
        raise HTTPException(status_code=404)

    comparison = build_video_comparison(target[0], target[1], list(latest.values()))
    if comparison is None:
        raise HTTPException(
            status_code=409,
            detail="Not enough earlier videos for a local comparison",
        )
    return comparison
