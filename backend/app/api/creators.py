import math
from collections import defaultdict
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi import Query as QueryParam
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.videos import VIDEO_SORT_FIELDS, _stats_to_schema
from app.core.background_tasks import track_task
from app.core.deps import get_db
from app.core.time import as_china_time
from app.models import (
    AIConversation,
    AIMessage,
    CreatorStatsSnapshot,
    Query,
    QueryVideo,
    RankingEntry,
    User,
    Video,
    VideoStats,
)
from app.schemas.analytics import (
    InteractionData,
    StatsSummary,
    TrendPoint,
    VideoComparison,
)
from app.schemas.creator import CreatorDetail, CreatorSummary
from app.schemas.growth import (
    AccountGrowthPoint,
    CreatorAccountGrowth,
    CreatorGrowth,
)
from app.schemas.video import PaginatedVideos, RankingMatch, VideoSummary
from app.services.creator_library import (
    creator_meta,
    creator_snapshot,
    latest_videos_for_creator,
)
from app.services.fetch_credentials import (
    FetchCredentialError,
    load_fetch_credentials,
)
from app.services.growth import creator_growth
from app.services.stats_refresh import run_stats_refresh

router = APIRouter()


@router.get("/creators", response_model=list[CreatorSummary])
async def list_creators(db: AsyncSession = Depends(get_db)):
    users = (
        await db.execute(
            select(User).order_by(
                User.last_fetched_at.desc(),
                User.name,
            )
        )
    ).scalars().all()
    creators: list[CreatorSummary] = []
    for user in users:
        snapshot = await creator_snapshot(db, user.uid)
        if snapshot is not None:
            creators.append(CreatorSummary(**creator_meta(snapshot)))
    return creators


@router.get("/creators/{uid}", response_model=CreatorDetail)
async def get_creator(uid: int, db: AsyncSession = Depends(get_db)):
    snapshot = await creator_snapshot(db, uid)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Creator not found")
    ranking_rows = (
        await db.execute(
            select(RankingEntry)
            .where(RankingEntry.owner_uid == uid)
            .order_by(RankingEntry.fetched_at.desc(), RankingEntry.rank)
        )
    ).scalars().all()
    seen_rankings: set[tuple[str, str]] = set()
    rankings: list[RankingMatch] = []
    for entry in ranking_rows:
        key = (entry.kind, entry.bvid)
        if key in seen_rankings:
            continue
        seen_rankings.add(key)
        rankings.append(
            RankingMatch(
                kind=entry.kind,
                period=entry.period,
                period_name=entry.period_name,
                rank=entry.rank,
                bvid=entry.bvid,
                title=entry.title,
                views=entry.views,
                likes=entry.likes,
                fetched_at=entry.fetched_at,
                in_library=entry.bvid in snapshot.videos,
            )
        )
    return CreatorDetail(
        **creator_meta(snapshot),
        total_likes=snapshot.total_likes,
        total_coins=snapshot.total_coins,
        total_favorites=snapshot.total_favorites,
        total_shares=snapshot.total_shares,
        total_danmaku=snapshot.total_danmaku,
        total_comments=snapshot.total_comments,
        rankings=rankings[:30],
    )


@router.delete("/creators/{uid}")
async def delete_creator(uid: int, db: AsyncSession = Depends(get_db)):
    user = await db.get(User, uid)
    if not user:
        raise HTTPException(status_code=404, detail="Creator not found")
    active_query = (
        await db.execute(
            select(Query.id)
            .where(
                Query.uid == uid,
                Query.status.in_(("pending", "fetching")),
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if active_query is not None or user.refresh_status in ("pending", "fetching"):
        raise HTTPException(
            status_code=409,
            detail="Wait for the running fetch or stats refresh to finish",
        )

    query_ids = list(
        (
            await db.execute(select(Query.id).where(Query.uid == uid))
        ).scalars().all()
    )
    bvids = set(
        (
            await db.execute(select(Video.bvid).where(Video.uid == uid))
        ).scalars().all()
    )
    if query_ids:
        bvids.update(
            (
                await db.execute(
                    select(QueryVideo.bvid).where(
                        QueryVideo.query_id.in_(query_ids)
                    )
                )
            ).scalars().all()
        )

    conversation_ids = list(
        (
            await db.execute(
                select(AIConversation.id).where(
                    or_(
                        AIConversation.uid == uid,
                        AIConversation.query_id.in_(query_ids),
                        AIConversation.bvid.in_(bvids),
                    )
                )
            )
        ).scalars().all()
    )
    if conversation_ids:
        await db.execute(
            delete(AIMessage).where(
                AIMessage.conversation_id.in_(conversation_ids)
            )
        )
        await db.execute(
            delete(AIConversation).where(
                AIConversation.id.in_(conversation_ids)
            )
        )

    if query_ids or bvids:
        await db.execute(
            delete(QueryVideo).where(
                or_(
                    QueryVideo.query_id.in_(query_ids),
                    QueryVideo.bvid.in_(bvids),
                )
            )
        )
    if query_ids:
        await db.execute(delete(Query).where(Query.id.in_(query_ids)))
    if bvids:
        await db.execute(
            delete(VideoStats).where(VideoStats.bvid.in_(bvids))
        )
        await db.execute(delete(Video).where(Video.bvid.in_(bvids)))
    await db.execute(
        delete(CreatorStatsSnapshot).where(CreatorStatsSnapshot.uid == uid)
    )
    await db.execute(delete(User).where(User.uid == uid))
    await db.commit()
    return {"status": "deleted"}


@router.get("/creators/{uid}/videos", response_model=PaginatedVideos)
async def list_creator_videos(
    uid: int,
    sort_by: str = "views",
    order: str = "desc",
    page: int = QueryParam(default=1, ge=1),
    page_size: int = QueryParam(default=20, le=100),
    search: str = QueryParam(default="", max_length=200),
    db: AsyncSession = Depends(get_db),
):
    if not await db.get(User, uid):
        raise HTTPException(status_code=404, detail="Creator not found")
    latest = await latest_videos_for_creator(db, uid)
    items = list(latest.values())

    search_text = search.strip()
    if search_text:
        pattern = f"%{search_text}%"
        items = [
            (video, stats)
            for video, stats in items
            if pattern.lower().strip("%") in (video.title or "").lower()
            or pattern.lower().strip("%") in video.bvid.lower()
            or pattern.lower().strip("%") in (video.tags or "").lower()
        ]

    sort_key = sort_by if sort_by in {
        "views", "likes", "coins", "favorites", "shares",
        "danmaku", "comments", "published_at", "duration",
    } else "views"
    if sort_key in VIDEO_SORT_FIELDS:
        items.sort(
            key=lambda item: getattr(item[0], sort_key)
            or (datetime.min if sort_key == "published_at" else 0),
            reverse=(order == "desc"),
        )
    else:
        field_name = {
            "danmaku": "danmaku_count",
            "comments": "comment_count",
        }.get(sort_key, sort_key)
        items.sort(
            key=lambda item: getattr(item[1], field_name, 0),
            reverse=(order == "desc"),
        )

    total = len(items)
    total_pages = math.ceil(total / page_size) if total else 1
    page_items = items[(page - 1) * page_size : page * page_size]
    return PaginatedVideos(
        items=[
            VideoSummary(
                bvid=video.bvid,
                title=video.title,
                cover_url=video.cover_url,
                duration=video.duration,
                published_at=video.published_at,
                tags=video.tags,
                stats=_stats_to_schema(stats),
            )
            for video, stats in page_items
        ],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.get("/creators/{uid}/stats/summary", response_model=StatsSummary)
async def creator_stats_summary(uid: int, db: AsyncSession = Depends(get_db)):
    snapshot = await creator_snapshot(db, uid)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Creator not found")
    return StatsSummary(
        total_views=snapshot.total_views,
        total_likes=snapshot.total_likes,
        total_coins=snapshot.total_coins,
        total_favorites=snapshot.total_favorites,
        total_shares=snapshot.total_shares,
        total_danmaku=snapshot.total_danmaku,
        total_comments=snapshot.total_comments,
        video_count=snapshot.video_count,
    )


@router.get("/creators/{uid}/stats/trend", response_model=list[TrendPoint])
async def creator_stats_trend(uid: int, db: AsyncSession = Depends(get_db)):
    if not await db.get(User, uid):
        raise HTTPException(status_code=404, detail="Creator not found")
    latest = await latest_videos_for_creator(db, uid)
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

    buckets: dict[str, int] = defaultdict(int)
    for video, stats in latest.values():
        if not video.published_at:
            continue
        published_at = as_china_time(video.published_at)
        if fmt == "week":
            iso = published_at.isocalendar()
            key = f"{iso[0]}-W{iso[1]:02d}"
        else:
            key = published_at.strftime(fmt)
        buckets[key] += stats.views

    return [
        TrendPoint(date=key, views=views)
        for key, views in sorted(buckets.items())
    ]


@router.get("/creators/{uid}/stats/interaction", response_model=InteractionData)
async def creator_stats_interaction(uid: int, db: AsyncSession = Depends(get_db)):
    snapshot = await creator_snapshot(db, uid)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Creator not found")
    return InteractionData(
        likes=snapshot.total_likes,
        coins=snapshot.total_coins,
        favorites=snapshot.total_favorites,
        shares=snapshot.total_shares,
    )


@router.get("/creators/{uid}/stats/growth", response_model=CreatorGrowth)
async def creator_stats_growth(uid: int, db: AsyncSession = Depends(get_db)):
    if not await db.get(User, uid):
        raise HTTPException(status_code=404, detail="Creator not found")
    return await creator_growth(db, uid)


@router.post("/creators/{uid}/stats/refresh")
async def refresh_creator_stats(uid: int, db: AsyncSession = Depends(get_db)):
    user = await db.get(User, uid)
    if user is None:
        raise HTTPException(status_code=404, detail="Creator not found")
    active_query = (
        await db.execute(
            select(Query.id)
            .where(
                Query.uid == uid,
                Query.status.in_(("pending", "fetching")),
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if active_query is not None:
        raise HTTPException(status_code=409, detail="A fetch batch is already running")
    if user.refresh_status in ("pending", "fetching"):
        return {"status": user.refresh_status}

    try:
        sessdata, proxies = await load_fetch_credentials(db)
    except FetchCredentialError as exc:
        raise HTTPException(
            status_code=400,
            detail="Stored credential could not be decrypted — re-enter it in Settings",
        ) from exc
    if not sessdata:
        raise HTTPException(status_code=400, detail="SESSDATA is not configured")

    user.refresh_status = "pending"
    user.refresh_progress = "Queued to capture a new stats snapshot"
    user.refresh_error = None
    user.refresh_retry_at = None
    await db.commit()
    track_task(run_stats_refresh(uid, sessdata, proxy_urls=proxies))
    return {"status": "pending"}


@router.get(
    "/creators/{uid}/stats/account-growth",
    response_model=CreatorAccountGrowth,
)
async def creator_account_growth(
    uid: int,
    db: AsyncSession = Depends(get_db),
):
    if not await db.get(User, uid):
        raise HTTPException(status_code=404, detail="Creator not found")
    snapshots = (
        await db.execute(
            select(CreatorStatsSnapshot)
            .where(CreatorStatsSnapshot.uid == uid)
            .order_by(
                CreatorStatsSnapshot.fetched_at,
                CreatorStatsSnapshot.id,
            )
        )
    ).scalars().all()
    return CreatorAccountGrowth(
        uid=uid,
        points=[
            AccountGrowthPoint(
                fetched_at=snapshot.fetched_at,
                followers=snapshot.followers,
                total_views=snapshot.total_views,
                total_likes=snapshot.total_likes,
            )
            for snapshot in snapshots
        ],
    )


@router.get(
    "/creators/{uid}/videos/{bvid}/comparison",
    response_model=VideoComparison,
)
async def creator_video_comparison(
    uid: int,
    bvid: str,
    db: AsyncSession = Depends(get_db),
):
    # Kept in sync with the query-scoped endpoint's response while accepting
    # creator scope instead of requiring one particular fetch batch.
    latest = await latest_videos_for_creator(db, uid)
    target = latest.get(bvid)
    if target is None:
        raise HTTPException(status_code=404, detail="Video not found in creator library")

    metrics = [
        "views", "likes", "coins", "favorites",
        "shares", "danmaku_count", "comment_count",
    ]
    labels = ["views", "likes", "coins", "favorites", "shares", "danmaku", "comments"]
    values = list(latest.values())
    count = len(values)
    target_stats = target[1]
    video_values = [float(getattr(target_stats, metric)) for metric in metrics]
    averages = [
        sum(getattr(stats, metric) for _, stats in values) / count
        for metric in metrics
    ]
    maximums = [
        max(getattr(stats, metric) for _, stats in values)
        for metric in metrics
    ]
    return {
        "metrics": labels,
        "video_values": video_values,
        "average_values": [round(value, 1) for value in averages],
        "max_values": [round(value, 1) for value in maximums],
        "percentage_diff": [
            round((value - average) / average * 100, 1) if average > 0 else 0.0
            for value, average in zip(video_values, averages)
        ],
    }
