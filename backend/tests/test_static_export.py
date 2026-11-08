from datetime import date, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models  # noqa: F401
from app.core.database import Base
from app.models import (
    AIConversation,
    AIMessage,
    AppSettings,
    Query,
    QueryVideo,
    User,
    Video,
    VideoStats,
)
from scripts.export_static import build_static_snapshot, write_snapshot


@pytest.mark.asyncio
async def test_static_snapshot_contains_dashboard_data_but_no_private_tables(
    tmp_path,
):
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path / 'export.db'}",
        echo=False,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        session.add(User(uid=42, name="Creator"))
        query = Query(
            uid=42,
            user_name="Creator",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 4, 1),
            status="done",
        )
        session.add(query)
        await session.flush()

        published = datetime(2026, 1, 1)
        videos = [
            Video(
                bvid=f"BV{index}",
                uid=42,
                title=f"Video {index}",
                duration=60 * index,
                published_at=published + timedelta(days=index * 30),
            )
            for index in range(1, 5)
        ]
        session.add_all(videos)
        await session.flush()
        session.add_all(
            [
                QueryVideo(query_id=query.id, bvid=video.bvid)
                for video in videos
            ]
        )
        session.add_all(
            [
                VideoStats(
                    bvid=video.bvid,
                    views=index * 100,
                    likes=index * 10,
                    fetched_at=datetime(2026, 4, 2),
                )
                for index, video in enumerate(videos, start=1)
            ]
        )
        session.add_all(
            [
                AppSettings(
                    key="sessdata",
                    value="encrypted-secret",
                    is_sensitive=True,
                ),
                AIConversation(preset="free_chat", title="Private"),
            ]
        )
        await session.flush()
        conversation = await session.get(AIConversation, 1)
        session.add(
            AIMessage(
                conversation_id=conversation.id,
                role="user",
                content="Private message",
            )
        )
        await session.commit()

    snapshot = await build_static_snapshot(session_factory)
    output = tmp_path / "static-data" / "snapshot.json"
    write_snapshot(snapshot, output)

    assert snapshot["creators"][0]["name"] == "Creator"
    assert snapshot["creators"][0]["status"] == "done"
    assert snapshot["creators"][0]["refresh_status"] == "idle"
    assert len(snapshot["creator_videos"]["42"]) == 4
    assert set(snapshot["video_details"]) == {"BV1", "BV2", "BV3", "BV4"}
    assert snapshot["video_growth"]["BV4"]["points"][0]["views"] == 400
    assert "BV4" in snapshot["video_comparisons"]
    assert "app_settings" not in snapshot
    assert "ai_conversations" not in snapshot
    assert "encrypted-secret" not in output.read_text()
    assert "Private message" not in output.read_text()

    await engine.dispose()


def test_writing_unchanged_data_preserves_generated_timestamp(tmp_path):
    output = tmp_path / "snapshot.json"
    snapshot = {
        "schema_version": 1,
        "generated_at": "2026-11-08T14:00:00+00:00",
        "creators": [{"uid": 42}],
    }
    write_snapshot(snapshot, output)
    original = output.read_text()

    refreshed = dict(snapshot)
    refreshed["generated_at"] = "2026-11-08T15:00:00+00:00"
    write_snapshot(refreshed, output)

    assert output.read_text() == original

    refreshed["creators"] = [{"uid": 42}, {"uid": 43}]
    write_snapshot(refreshed, output)

    assert '"generated_at":"2026-11-08T15:00:00+00:00"' in output.read_text()
