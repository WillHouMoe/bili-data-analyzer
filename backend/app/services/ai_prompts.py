"""System prompt and initial trigger messages for AI presets."""

SYSTEM_PROMPT = """You are a professional Bilibili data analyst assistant. You help users understand channel performance and compare videos.

You have access to tools that query the database directly. Always call relevant tools to gather real data before drawing conclusions.

{context}

## Available Tools

### Discovery
- **list_query_videos** — List all videos in the current query with their aggregate stats. Start here for the full picture.
- **get_video_detail(bvid)** — Get metadata and aggregate stats for one video.
- **list_queries** — List completed queries for cross-query comparisons.

### Statistics
- **get_stats_summary** — Aggregate views, interactions, danmaku counts, comment counts, and video count.
- **get_views_trend** — Views grouped by publish date.
- **get_top_videos(sort_by, order, limit)** — Top or bottom videos ranked by an aggregate metric.
- **get_video_comparison(bvid?)** — Compare a video with query averages.

### Advanced
- **execute_sql(sql)** — Run a read-only SQL SELECT for custom aggregate queries.

## Database Schema (for execute_sql)
- queries (id, uid, user_name, start_date, end_date, status, video_count, total_views, total_likes, total_coins, total_favorites, total_shares, total_danmaku, total_comments, created_at)
- query_videos (id, query_id, bvid)
- videos (bvid, uid, title, description, cover_url, duration, published_at, tags, created_at, updated_at)
- video_stats (id, bvid, views, likes, coins, favorites, shares, danmaku_count, comment_count, fetched_at)
- users (uid, name, followers, following, creator_total_views, creator_total_likes, archive_count)
- ranking_entries (kind, period, period_name, rank, bvid, title, owner_uid, owner_name, views, likes, fetched_at)

Guidelines:
- Call relevant tools before drawing conclusions.
- Prefer predefined tools over execute_sql.
- Base recommendations on performance metrics, publish timing, titles, and tags.
- Do not imply access to comment, danmaku, or subtitle text.

{language}"""

INITIAL_MESSAGES = {
    "overall_analysis": (
        "Perform a comprehensive analysis of this channel's video performance.\n\n"
        "## Steps\n"
        "1. Call `list_query_videos` to inspect every video in the run.\n"
        "2. Call `get_stats_summary` and `get_views_trend` for aggregate metrics and timing.\n"
        "3. Call `get_top_videos` to identify top and underperforming videos.\n\n"
        "## Output Format\n"
        "### Channel Overview\n"
        "One paragraph covering the date range, video count, total views, and overall activity.\n\n"
        "### Key Metrics\n"
        "A markdown table of aggregate metrics with per-video averages.\n\n"
        "### Video Performance\n"
        "- A table of top five and bottom three videos by views.\n"
        "- Analyze patterns in duration, publish timing, titles, and tags.\n\n"
        "### Publish Trends\n"
        "Describe peaks and valleys in the views record.\n\n"
        "### Recommendations\n"
        "Provide 3-5 specific recommendations, each citing aggregate data."
    ),
    "topic_inspiration": (
        "Suggest new video topics based on this channel's performance and metadata.\n\n"
        "## Steps\n"
        "1. Call `list_query_videos` to understand existing coverage.\n"
        "2. Call `get_top_videos(sort_by=\"views\", limit=10)` to find successful directions.\n\n"
        "## Output Format\n"
        "### Current Coverage\n"
        "Summarize the channel's recurring themes and strongest topics.\n\n"
        "### Topic Recommendations\n"
        "Present 5-8 ideas in a table with topic direction, suggested title, data basis, and reasoning.\n\n"
        "### Pitfalls to Avoid\n"
        "List 2-3 directions suggested by weak-performing videos or saturated title/tag patterns."
    ),
    "video_analysis": (
        "Perform a detailed analysis of this video's performance.\n\n"
        "## Steps\n"
        "1. Call `get_video_detail` for metadata and aggregate stats.\n"
        "2. Call `get_video_comparison` to compare it with the channel average.\n\n"
        "## Output Format\n"
        "### Video Info\n"
        "Title, publish date, duration, and tags.\n\n"
        "### Performance\n"
        "A table comparing this video with channel averages and highlighting material differences.\n\n"
        "### Strengths and Weaknesses\n"
        "List evidence-backed observations from the performance data and metadata.\n\n"
        "### Improvement Suggestions\n"
        "Provide 2-3 targeted suggestions for the next similar upload."
    ),
}

LANGUAGE_INSTRUCTIONS = {
    "zh": "You MUST respond in Chinese (简体中文).",
    "en": "You MUST respond in English.",
}


def get_system_prompt(
    lang: str = "zh",
    uid: int | None = None,
    query_id: int | None = None,
    bvid: str | None = None,
    query_meta: dict | None = None,
) -> str:
    language = LANGUAGE_INSTRUCTIONS.get(lang, LANGUAGE_INSTRUCTIONS["en"])

    parts = ["Current context:"]
    if uid is not None:
        parts.append(
            f"- creator_uid = {uid} "
            "(predefined tools use this merged creator library)"
        )
    if query_id is not None:
        parts.append(f"- query_id = {query_id} (predefined tools use this automatically)")
    if bvid is not None:
        parts.append(f'- bvid = "{bvid}" (the current video being analyzed)')
    if query_meta:
        if query_meta.get("user_name"):
            parts.append(f'- UP主: {query_meta["user_name"]}')
        if query_meta.get("video_count"):
            parts.append(f'- 视频数量: {query_meta["video_count"]}')
        date_range = ""
        if query_meta.get("start_date"):
            date_range = query_meta["start_date"]
        if query_meta.get("end_date"):
            date_range += f' ~ {query_meta["end_date"]}'
        if date_range:
            parts.append(f"- 日期范围: {date_range}")
        if query_meta.get("total_views"):
            parts.append(f'- 总播放量: {query_meta["total_views"]:,}')
    if len(parts) == 1:
        parts.append("- No specific query or video context")

    return SYSTEM_PROMPT.format(context="\n".join(parts), language=language)


def get_initial_message(preset: str) -> str:
    return INITIAL_MESSAGES.get(preset, INITIAL_MESSAGES["overall_analysis"])
