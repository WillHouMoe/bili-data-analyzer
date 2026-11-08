from sqlalchemy import event, inspect, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class Base(DeclarativeBase):
    pass


@event.listens_for(engine.sync_engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
    """SQLite does not enforce foreign keys unless told to on every connection —
    without this, every ondelete="CASCADE" declared on the models is inert."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # The simplify migration removed these models, but create_all() never
        # dropped their tables. Their foreign keys still block deleting videos
        # from databases created before that migration.
        await conn.execute(text("DROP TABLE IF EXISTS video_content"))
        await conn.execute(text("DROP TABLE IF EXISTS video_sentiment"))
        # create_all() does not alter tables in an existing single-machine DB.
        # This one additive migration keeps existing creator conversations
        # usable after the UI changed from query-scoped to UID-scoped data.
        columns = await conn.run_sync(
            lambda sync_conn: {
                column["name"]
                for column in inspect(sync_conn).get_columns("ai_conversations")
            }
        )
        if "uid" not in columns:
            await conn.execute(
                text("ALTER TABLE ai_conversations ADD COLUMN uid INTEGER")
            )
        user_columns = await conn.run_sync(
            lambda sync_conn: {
                column["name"]
                for column in inspect(sync_conn).get_columns("users")
            }
        )
        user_migrations = {
            "followers": "INTEGER",
            "following": "INTEGER",
            "creator_total_views": "INTEGER",
            "creator_total_likes": "INTEGER",
            "archive_count": "INTEGER",
            "profile_stats_updated_at": "DATETIME",
            "last_stats_refresh_at": "DATETIME",
            "refresh_status": "TEXT DEFAULT 'idle'",
            "refresh_progress": "TEXT",
            "refresh_error": "TEXT",
            "refresh_retry_at": "DATETIME",
            "last_video_scan_at": "DATETIME",
            "video_scan_retry_at": "DATETIME",
        }
        for column, sql_type in user_migrations.items():
            if column not in user_columns:
                await conn.execute(
                    text(f"ALTER TABLE users ADD COLUMN {column} {sql_type}")
                )
        video_columns = await conn.run_sync(
            lambda sync_conn: {
                column["name"]
                for column in inspect(sync_conn).get_columns("videos")
            }
        )
        video_migrations = {
            "next_stats_refresh_at": "DATETIME",
            "stats_boost_remaining": "INTEGER DEFAULT 0",
            "honors_checked_at": "DATETIME",
        }
        for column, sql_type in video_migrations.items():
            if column not in video_columns:
                await conn.execute(
                    text(f"ALTER TABLE videos ADD COLUMN {column} {sql_type}")
                )
        await conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_videos_next_stats_refresh_at
                ON videos (next_stats_refresh_at)
                """
            )
        )
        # Weekly must-watch is an editorial list, not a ranked chart. Older
        # refreshes stored the response position as a rank; normalize it.
        await conn.execute(
            text("UPDATE ranking_entries SET rank = 0 WHERE kind = 'weekly'")
        )
        # Seed one account-history point for existing installs from their
        # current profile totals. Future refreshes append real observations.
        await conn.execute(
            text(
                """
                INSERT INTO creator_stats_snapshots
                    (uid, followers, following, total_views, total_likes,
                     archive_count, fetched_at)
                SELECT u.uid, u.followers, u.following, u.creator_total_views,
                       u.creator_total_likes, u.archive_count,
                       COALESCE(u.profile_stats_updated_at, u.last_fetched_at)
                FROM users u
                WHERE u.profile_stats_updated_at IS NOT NULL
                  AND NOT EXISTS (
                      SELECT 1 FROM creator_stats_snapshots s WHERE s.uid = u.uid
                  )
                """
            )
        )
