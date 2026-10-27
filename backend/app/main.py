import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from app.api import ai, analytics, creators, fetch, queries, videos
from app.api import settings as settings_api
from app.core.background_tasks import track_task
from app.core.config import settings
from app.core.database import async_session, init_db
from app.models import Query, User
from app.services.fetch_credentials import (
    FetchCredentialError,
    load_fetch_credentials,
)
from app.services.fetch_task import run_fetch
from app.services.stats_refresh import stats_refresh_loop

logger = logging.getLogger(__name__)

NON_TERMINAL_QUERY_STATUSES = ("pending", "fetching")


async def _resume_interrupted_queries() -> None:
    """Resume scrapes interrupted by a container restart.

    The fetch loop skips videos already linked to the same query, so resuming is
    safe after only part of an index has been persisted.
    """
    async with async_session() as db:
        result = await db.execute(select(Query).where(Query.status.in_(NON_TERMINAL_QUERY_STATUSES)))
        stuck_queries = result.scalars().all()
        for query in stuck_queries:
            query.status = "pending"
            query.error_message = None
            query.progress = "Queued to resume after server restart"
        if stuck_queries:
            await db.commit()
            logger.info("Resuming %d interrupted query task(s)", len(stuck_queries))

        try:
            sessdata, proxies = await load_fetch_credentials(db)
        except FetchCredentialError:
            sessdata, proxies = None, []

    for query in stuck_queries:
        track_task(
            run_fetch(
                query.id,
                query.uid,
                query.start_date,
                query.end_date,
                sessdata,
                proxy_urls=proxies,
            )
        )


async def _reset_interrupted_refreshes() -> None:
    async with async_session() as db:
        users = (
            await db.execute(
                select(User).where(User.refresh_status.in_(("pending", "fetching")))
            )
        ).scalars().all()
        for user in users:
            user.refresh_status = "error"
            user.refresh_progress = None
            user.refresh_error = "Interrupted by server restart"
        if users:
            await db.commit()
            logger.warning("Reset %d interrupted stats refresh(es)", len(users))


@asynccontextmanager
async def lifespan(app: FastAPI):
    Path(settings.DATA_DIR).mkdir(parents=True, exist_ok=True)
    await init_db()
    await _resume_interrupted_queries()
    await _reset_interrupted_refreshes()
    if settings.STATS_REFRESH_HOURS > 0:
        track_task(stats_refresh_loop())
    yield


app = FastAPI(title="BiliDataAnalyzer", lifespan=lifespan)

# CORS
if settings.CORS_ORIGINS:
    origins = [o.strip() for o in settings.CORS_ORIGINS.split(",")]
    allow_credentials = True
    if origins == ["*"]:
        # A wildcard origin combined with allow_credentials=True is rejected by
        # browsers anyway (and is a CSRF-adjacent misconfiguration), so drop
        # credentials rather than silently shipping a broken/insecure policy.
        allow_credentials = False
        logger.warning("CORS_ORIGINS=* set; disabling allow_credentials for a wildcard CORS policy")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )


app.include_router(fetch.router, prefix="/api", tags=["fetch"])
app.include_router(creators.router, prefix="/api", tags=["creators"])
app.include_router(queries.router, prefix="/api", tags=["queries"])
app.include_router(videos.router, prefix="/api", tags=["videos"])
app.include_router(analytics.router, prefix="/api", tags=["analytics"])
app.include_router(ai.router, prefix="/api", tags=["ai"])
app.include_router(settings_api.router, prefix="/api", tags=["settings"])


@app.get("/api/health", include_in_schema=False)
async def health():
    return {"status": "ok"}


# Serve the built frontend, when there is one.
#
# In the container the build is copied to /app/frontend/dist. Running from a
# checkout it sits next to the backend instead, so look there too — otherwise
# `uvicorn app.main:app` serves the API with no UI and the only way to see the
# app locally is to run Vite on a second port.
def _find_dist() -> Path:
    candidates = (
        Path("/app/frontend/dist"),
        Path(__file__).resolve().parents[2] / "frontend" / "dist",
    )
    return next((p for p in candidates if p.is_dir()), candidates[0])


_dist = _find_dist()
if _dist.exists():
    app.mount("/assets", StaticFiles(directory=_dist / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        return FileResponse(_dist / "index.html")
