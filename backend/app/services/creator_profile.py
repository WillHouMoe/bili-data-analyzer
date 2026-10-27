from datetime import UTC, datetime

from app.models import User


def apply_creator_info(user: User, info: dict) -> None:
    user.name = info.get("name") or user.name
    if info.get("avatar_url"):
        user.avatar_url = info["avatar_url"]
    user.last_fetched_at = datetime.now(UTC)

    field_map = {
        "followers": "followers",
        "following": "following",
        "creator_total_views": "creator_total_views",
        "creator_total_likes": "creator_total_likes",
        "archive_count": "archive_count",
    }
    updated = False
    for source, target in field_map.items():
        value = info.get(source)
        if value is not None:
            setattr(user, target, value)
            updated = True
    if updated:
        user.profile_stats_updated_at = datetime.now(UTC)
