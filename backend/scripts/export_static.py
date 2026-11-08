"""Export the dashboard's read-only API surface as one static JSON snapshot.

The public build never receives the SQLite database. This exporter reads the
local library through the same response functions the API uses, then keeps only
the data the dashboard and video pages need. Settings, credentials and AI
conversations are intentionally absent.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATABASE = REPO_ROOT / "data" / "bilianalyzer.db"
DEFAULT_OUTPUT = (
    REPO_ROOT / "frontend" / "public" / "static-data" / "snapshot.json"
)


def _database_url(database: Path) -> str:
    return f"sqlite+aiosqlite:///{database.resolve()}"


# Configure imports before app.core.config creates its global engine. The
# exporter uses its own read-only connection, but every backend module still
# resolves settings at import time.
os.environ.setdefault("DATABASE_URL", _database_url(DEFAULT_DATABASE))
os.environ.setdefault("DATA_DIR", str(DEFAULT_DATABASE.parent))

from fastapi import HTTPException  # noqa: E402
from sqlalchemy import event  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.api.creators import (  # noqa: E402
    creator_account_growth,
    creator_stats_interaction,
    creator_stats_summary,
    creator_stats_trend,
    creator_video_comparison,
    get_creator,
    list_creator_videos,
    list_creators,
)
from app.api.videos import get_video  # noqa: E402
from app.services.growth import creator_growth, video_growth  # noqa: E402


def _json_model(model: Any) -> dict[str, Any]:
    return model.model_dump(mode="json")


def _json_creator(model: Any) -> dict[str, Any]:
    """Keep the data, but replace local task state with a stable public state."""
    creator = _json_model(model)
    creator.update(
        {
            "status": "done",
            "progress": None,
            "error_message": None,
            "refresh_status": "idle",
            "refresh_progress": None,
            "refresh_error": None,
        }
    )
    return creator


async def build_static_snapshot(
    session_factory: async_sessionmaker[AsyncSession],
) -> dict[str, Any]:
    """Build the public snapshot from a local database session factory."""
    snapshot: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "creators": [],
        "creator_details": {},
        "creator_stats": {},
        "creator_trends": {},
        "creator_interactions": {},
        "creator_growth": {},
        "creator_account_growth": {},
        "creator_videos": {},
        "video_details": {},
        "video_growth": {},
        "video_comparisons": {},
    }

    async with session_factory() as db:
        creators = [
            creator
            for creator in await list_creators(db)
            if creator.video_count > 0
        ]
        busy = [
            creator.name
            for creator in creators
            if creator.status in {"pending", "fetching"}
            or creator.refresh_status in {"pending", "fetching"}
        ]
        if busy:
            raise RuntimeError(
                "Wait for local fetches and statistics refreshes to finish "
                f"before exporting: {', '.join(busy)}"
            )
        snapshot["creators"] = [_json_creator(creator) for creator in creators]

        for creator in creators:
            uid = creator.uid
            uid_key = str(uid)

            snapshot["creator_details"][uid_key] = _json_creator(
                await get_creator(uid, db)
            )
            snapshot["creator_stats"][uid_key] = _json_model(
                await creator_stats_summary(uid, db)
            )
            snapshot["creator_trends"][uid_key] = [
                _json_model(point) for point in await creator_stats_trend(uid, db)
            ]
            snapshot["creator_interactions"][uid_key] = _json_model(
                await creator_stats_interaction(uid, db)
            )
            snapshot["creator_growth"][uid_key] = _json_model(
                await creator_growth(db, uid)
            )
            snapshot["creator_account_growth"][uid_key] = _json_model(
                await creator_account_growth(uid, db)
            )

            first_page = await list_creator_videos(
                uid=uid,
                sort_by="published_at",
                order="desc",
                page=1,
                page_size=100,
                search="",
                db=db,
            )
            pages = [first_page]
            for page_number in range(2, first_page.total_pages + 1):
                pages.append(
                    await list_creator_videos(
                        uid=uid,
                        sort_by="published_at",
                        order="desc",
                        page=page_number,
                        page_size=100,
                        search="",
                        db=db,
                    )
                )

            videos = [video for page in pages for video in page.items]
            snapshot["creator_videos"][uid_key] = [
                _json_model(video) for video in videos
            ]

            for video in videos:
                bvid = video.bvid
                snapshot["video_details"][bvid] = _json_model(
                    await get_video(bvid, db)
                )
                snapshot["video_growth"][bvid] = _json_model(
                    await video_growth(db, bvid)
                )
                try:
                    comparison = await creator_video_comparison(uid, bvid, db)
                except HTTPException as exc:
                    if exc.status_code != 409:
                        raise
                else:
                    snapshot["video_comparisons"][bvid] = _json_model(comparison)

    return snapshot


def write_snapshot(snapshot: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(f"{output.suffix}.tmp")
    temporary.write_text(
        json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    temporary.replace(output)


async def export_database(database: Path, output: Path) -> dict[str, Any]:
    engine = create_async_engine(_database_url(database), echo=False)

    @event.listens_for(engine.sync_engine, "connect")
    def _read_only_connection(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA query_only=ON")
        cursor.close()

    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    try:
        snapshot = await build_static_snapshot(session_factory)
    finally:
        await engine.dispose()

    write_snapshot(snapshot, output)
    return snapshot


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export a sanitized, read-only BiliDataAnalyzer snapshot."
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=DEFAULT_DATABASE,
        help="SQLite database to read",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="JSON snapshot written for the frontend",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    database = args.database.resolve()
    output = args.output.resolve()
    if not database.is_file():
        raise SystemExit(f"Database not found: {database}")

    snapshot = asyncio.run(export_database(database, output))
    video_count = len(snapshot["video_details"])
    creator_count = len(snapshot["creators"])
    print(
        f"Exported {creator_count} creator(s), {video_count} video(s) "
        f"to {output} ({output.stat().st_size:,} bytes)"
    )


if __name__ == "__main__":
    main()
