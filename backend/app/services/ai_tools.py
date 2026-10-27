"""OpenAI function-calling tool definitions and executor for the AI agent."""
import json
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import as_china_time
from app.models import Query, QueryVideo, Video, VideoStats
from app.services.creator_library import creator_snapshot, latest_videos_for_creator

TOOL_GET_STATS_SUMMARY = {
    "type": "function",
    "function": {
        "name": "get_stats_summary",
        "description": "Get aggregate statistics for the current creator library or query.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
}

TOOL_GET_VIEWS_TREND = {
    "type": "function",
    "function": {
        "name": "get_views_trend",
        "description": "Get views grouped by publish date (auto-adaptive: daily/weekly/monthly). Returns [{date, views}].",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
}

TOOL_LIST_QUERY_VIDEOS = {
    "type": "function",
    "function": {
        "name": "list_query_videos",
        "description": "List all videos in the current creator library or query with aggregate stats, sorted by publish date descending.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
}

TOOL_GET_TOP_VIDEOS = {
    "type": "function",
    "function": {
        "name": "get_top_videos",
        "description": "Get top or bottom N videos sorted by a metric. Returns title, bvid, tags, and aggregate stats.",
        "parameters": {
            "type": "object",
            "properties": {
                "sort_by": {
                    "type": "string",
                    "enum": [
                        "views",
                        "likes",
                        "coins",
                        "favorites",
                        "shares",
                        "danmaku_count",
                        "comment_count",
                    ],
                    "description": "Metric to sort by",
                },
                "order": {
                    "type": "string",
                    "enum": ["desc", "asc"],
                    "description": "Sort order. desc=top, asc=bottom",
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of videos to return (default 5, max 20)",
                },
            },
            "required": ["sort_by"],
        },
    },
}

TOOL_GET_VIDEO_COMPARISON = {
    "type": "function",
    "function": {
        "name": "get_video_comparison",
        "description": "Compare a specific video's aggregate stats against the current library average.",
        "parameters": {
            "type": "object",
            "properties": {
                "bvid": {
                    "type": "string",
                    "description": "The video BV number to compare. If omitted, uses the current video context.",
                },
            },
            "required": [],
        },
    },
}

TOOL_GET_VIDEO_DETAIL = {
    "type": "function",
    "function": {
        "name": "get_video_detail",
        "description": "Get full metadata and aggregate stats for a specific video.",
        "parameters": {
            "type": "object",
            "properties": {
                "bvid": {
                    "type": "string",
                    "description": "The Bilibili video ID. If omitted and in video context, uses current video.",
                },
            },
            "required": [],
        },
    },
}

TOOL_LIST_QUERIES = {
    "type": "function",
    "function": {
        "name": "list_queries",
        "description": "List all completed queries with date ranges, video counts, and aggregate stats.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
}

TOOL_EXECUTE_SQL = {
    "type": "function",
    "function": {
        "name": "execute_sql",
        "description": (
            "Execute a read-only SQL SELECT against the SQLite database. Returns up to 200 rows. "
            "Use this only for custom aggregate queries that the predefined tools cannot handle.\n\n"
            "Tables:\n"
            "- queries (id, uid, user_name, start_date, end_date, status, video_count, total_views, total_likes, total_coins, total_favorites, total_shares, total_danmaku, total_comments, created_at)\n"
            "- query_videos (id, query_id, bvid)\n"
            "- videos (bvid, uid, title, description, cover_url, duration, published_at, tags, created_at, updated_at)\n"
            "- video_stats (id, bvid, views, likes, coins, favorites, shares, danmaku_count, comment_count, fetched_at)\n"
            "- users (uid, name, followers, following, creator_total_views, creator_total_likes, archive_count)\n"
            "- ranking_entries (kind, period, period_name, rank, bvid, title, owner_uid, owner_name, views, likes, fetched_at)"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "A SQL SELECT query to execute. Only SELECT is allowed.",
                },
            },
            "required": ["sql"],
        },
    },
}

ALL_TOOLS = [
    TOOL_LIST_QUERY_VIDEOS,
    TOOL_GET_STATS_SUMMARY,
    TOOL_GET_VIEWS_TREND,
    TOOL_GET_TOP_VIDEOS,
    TOOL_GET_VIDEO_COMPARISON,
    TOOL_GET_VIDEO_DETAIL,
    TOOL_LIST_QUERIES,
    TOOL_EXECUTE_SQL,
]


def get_tools() -> list[dict]:
    return ALL_TOOLS


async def execute_tool(
    name: str,
    arguments: dict,
    db: AsyncSession,
    context: dict,
) -> str:
    """Execute a tool and return its result as JSON."""
    query_id = context.get("query_id")
    uid = context.get("uid")
    bvid = context.get("bvid")

    try:
        if name == "list_query_videos":
            return await _exec_list_query_videos(db, query_id, uid)
        if name == "get_stats_summary":
            return await _exec_stats_summary(db, query_id, uid)
        if name == "get_views_trend":
            return await _exec_views_trend(db, query_id, uid)
        if name == "get_top_videos":
            return await _exec_top_videos(db, query_id, uid, arguments)
        if name == "get_video_comparison":
            return await _exec_video_comparison(
                db, query_id, uid, arguments.get("bvid") or bvid
            )
        if name == "get_video_detail":
            return await _exec_video_detail(db, arguments.get("bvid") or bvid)
        if name == "list_queries":
            return await _exec_list_queries(db, uid)
        if name == "execute_sql":
            return await _exec_sql_query(db, arguments)
        return json.dumps({"error": f"Unknown tool: {name}"})
    except Exception as exc:
        return json.dumps({"error": str(exc)})


async def _exec_stats_summary(
    db: AsyncSession, query_id: int | None, uid: int | None
) -> str:
    if uid is not None:
        snapshot = await creator_snapshot(db, uid)
        if snapshot is None:
            return json.dumps({"error": "Creator not found"})
        return json.dumps(
            {
                "video_count": snapshot.video_count,
                "total_views": snapshot.total_views,
                "total_likes": snapshot.total_likes,
                "total_coins": snapshot.total_coins,
                "total_favorites": snapshot.total_favorites,
                "total_shares": snapshot.total_shares,
                "total_danmaku": snapshot.total_danmaku,
                "total_comments": snapshot.total_comments,
                "followers": snapshot.user.followers,
                "creator_total_views": snapshot.user.creator_total_views,
                "creator_total_likes": snapshot.user.creator_total_likes,
                "archive_count": snapshot.user.archive_count,
            }
        )
    query = await db.get(Query, query_id)
    if not query:
        return json.dumps({"error": "Query not found"})
    return json.dumps(
        {
            "video_count": query.video_count,
            "total_views": query.total_views,
            "total_likes": query.total_likes,
            "total_coins": query.total_coins,
            "total_favorites": query.total_favorites,
            "total_shares": query.total_shares,
            "total_danmaku": query.total_danmaku,
            "total_comments": query.total_comments,
        }
    )


async def _get_latest_stats(
    db: AsyncSession, query_id: int | None, uid: int | None = None
) -> dict[str, tuple[Video, VideoStats]]:
    if uid is not None:
        return await latest_videos_for_creator(db, uid)
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
    return latest


async def _exec_list_query_videos(
    db: AsyncSession, query_id: int | None, uid: int | None
) -> str:
    if not query_id and uid is None:
        return json.dumps({"error": "No creator or query context"})
    latest = await _get_latest_stats(db, query_id, uid)
    items = [
        {
            "bvid": video.bvid,
            "title": video.title,
            "published_at": video.published_at.isoformat() if video.published_at else None,
            "duration": video.duration,
            "views": stats.views,
            "likes": stats.likes,
            "coins": stats.coins,
            "favorites": stats.favorites,
            "shares": stats.shares,
            "danmaku_count": stats.danmaku_count,
            "comment_count": stats.comment_count,
        }
        for video, stats in latest.values()
    ]
    items.sort(key=lambda item: item["published_at"] or "", reverse=True)
    return json.dumps(items, ensure_ascii=False)


async def _exec_views_trend(
    db: AsyncSession, query_id: int | None, uid: int | None
) -> str:
    if not query_id and uid is None:
        return json.dumps({"error": "No creator or query context"})
    latest = await _get_latest_stats(db, query_id, uid)
    dates = [
        as_china_time(video.published_at)
        for video, _ in latest.values()
        if video.published_at
    ]
    if not dates:
        return json.dumps([])

    span = (max(dates) - min(dates)).days
    if span <= 31:
        fmt = "%Y-%m-%d"
    elif span <= 180:
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

    return json.dumps(
        [{"date": key, "views": views} for key, views in sorted(buckets.items())]
    )


async def _exec_top_videos(
    db: AsyncSession,
    query_id: int | None,
    uid: int | None,
    args: dict,
) -> str:
    if not query_id and uid is None:
        return json.dumps({"error": "No creator or query context"})
    sort_by = args.get("sort_by", "views")
    reverse = args.get("order", "desc") == "desc"
    limit = min(args.get("limit", 5), 20)

    latest = await _get_latest_stats(db, query_id, uid)
    items = [
        {
            "bvid": video.bvid,
            "title": video.title,
            "tags": video.tags,
            "views": stats.views,
            "likes": stats.likes,
            "coins": stats.coins,
            "favorites": stats.favorites,
            "shares": stats.shares,
            "danmaku_count": stats.danmaku_count,
            "comment_count": stats.comment_count,
        }
        for video, stats in latest.values()
    ]
    items.sort(key=lambda item: item.get(sort_by, 0), reverse=reverse)
    return json.dumps(items[:limit], ensure_ascii=False)


async def _exec_video_comparison(
    db: AsyncSession,
    query_id: int | None,
    uid: int | None,
    bvid: str | None,
) -> str:
    if not bvid:
        return json.dumps({"error": "No video context (bvid) provided"})
    if not query_id and uid is None:
        return json.dumps({"error": "No creator or query context for comparison"})

    latest = await _get_latest_stats(db, query_id, uid)
    target = latest.get(bvid)
    if target is None:
        return json.dumps({"error": "Video stats not found in this context"})
    video_stats = target[1]
    count = len(latest) or 1
    metrics = [
        "views",
        "likes",
        "coins",
        "favorites",
        "shares",
        "danmaku_count",
        "comment_count",
    ]
    labels = ["views", "likes", "coins", "favorites", "shares", "danmaku", "comments"]
    result = {}
    for label, metric in zip(labels, metrics):
        video_value = getattr(video_stats, metric)
        average = sum(getattr(stats, metric) for _, stats in latest.values()) / count
        percent = round((video_value - average) / average * 100, 1) if average > 0 else 0
        result[label] = {
            "video": video_value,
            "average": round(average, 1),
            "diff_pct": percent,
        }
    return json.dumps(result)


async def _exec_video_detail(db: AsyncSession, bvid: str | None) -> str:
    if not bvid:
        return json.dumps({"error": "No bvid provided"})
    video = await db.get(Video, bvid)
    if not video:
        return json.dumps({"error": f"Video {bvid} not found"})

    stats_result = await db.execute(
        select(VideoStats)
        .where(VideoStats.bvid == bvid)
        .order_by(VideoStats.fetched_at.desc())
        .limit(1)
    )
    stats = stats_result.scalar_one_or_none()
    data = {
        "bvid": video.bvid,
        "title": video.title,
        "description": video.description,
        "tags": video.tags,
        "duration": video.duration,
        "published_at": video.published_at.isoformat() if video.published_at else None,
    }
    if stats:
        data.update(
            {
                "views": stats.views,
                "likes": stats.likes,
                "coins": stats.coins,
                "favorites": stats.favorites,
                "shares": stats.shares,
                "danmaku_count": stats.danmaku_count,
                "comment_count": stats.comment_count,
            }
        )
    return json.dumps(data, ensure_ascii=False)


async def _exec_list_queries(db: AsyncSession, uid: int | None = None) -> str:
    stmt = select(Query).where(Query.status == "done")
    if uid is not None:
        stmt = stmt.where(Query.uid == uid)
    result = await db.execute(stmt.order_by(Query.created_at.desc()))
    data = [
        {
            "id": query.id,
            "uid": query.uid,
            "user_name": query.user_name,
            "start_date": query.start_date.isoformat() if query.start_date else None,
            "end_date": query.end_date.isoformat() if query.end_date else None,
            "video_count": query.video_count,
            "total_views": query.total_views,
            "total_likes": query.total_likes,
            "total_coins": query.total_coins,
            "total_favorites": query.total_favorites,
            "total_shares": query.total_shares,
            "total_danmaku": query.total_danmaku,
            "total_comments": query.total_comments,
            "created_at": query.created_at.isoformat() if query.created_at else None,
        }
        for query in result.scalars().all()
    ]
    return json.dumps(data, ensure_ascii=False)


async def _exec_sql_query(db: AsyncSession, args: dict) -> str:
    sql = (args.get("sql") or "").strip()
    if not sql:
        return json.dumps({"error": "No SQL query provided"})

    upper = sql.upper().lstrip()
    if not upper.startswith("SELECT"):
        return json.dumps({"error": "Only SELECT queries are allowed"})
    for keyword in (
        "INSERT",
        "UPDATE",
        "DELETE",
        "DROP",
        "ALTER",
        "CREATE",
        "REPLACE",
        "ATTACH",
        "DETACH",
    ):
        if keyword in upper:
            return json.dumps({"error": f"Forbidden keyword: {keyword}"})

    from sqlalchemy import text

    try:
        result = await db.execute(text(sql))
        columns = list(result.keys())
        rows = result.fetchmany(200)
        data = [dict(zip(columns, row)) for row in rows]
        return json.dumps(data, ensure_ascii=False, default=str)
    except Exception as exc:
        return json.dumps({"error": f"SQL error: {exc}"})
