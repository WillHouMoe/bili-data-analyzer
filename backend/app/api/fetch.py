import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.background_tasks import track_task
from app.core.deps import get_db
from app.models import Query, User
from app.schemas.query import FetchRequest, FetchResponse
from app.services.fetch_credentials import (
    FetchCredentialError,
    load_fetch_credentials,
)
from app.services.fetch_task import run_fetch

logger = logging.getLogger(__name__)

router = APIRouter()

DECRYPT_ERROR_MESSAGE = "Stored credential could not be decrypted — re-enter it in Settings"


@router.post("/fetch", response_model=FetchResponse)
async def create_fetch(req: FetchRequest, db: AsyncSession = Depends(get_db)):
    existing = (
        await db.execute(
            select(Query)
            .where(
                Query.uid == req.uid,
                Query.start_date == req.start_date,
                Query.end_date == req.end_date,
                Query.status.in_(("pending", "fetching", "done")),
            )
            .order_by(Query.created_at.desc(), Query.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if existing is not None:
        return FetchResponse(
            query_id=existing.id,
            uid=existing.uid,
            status=existing.status,
        )

    # Get SESSDATA and proxy list before creating the query, so a decryption
    # failure doesn't leave a "pending" query behind that never starts.
    try:
        sessdata, proxy_urls = await load_fetch_credentials(db)
    except FetchCredentialError as exc:
        logger.warning("Failed to decrypt fetch credentials: %s", exc)
        raise HTTPException(
            status_code=400,
            detail=DECRYPT_ERROR_MESSAGE,
        ) from exc

    user = await db.get(User, req.uid)
    if user is None:
        db.add(User(uid=req.uid, name=f"UID {req.uid}"))
    query = Query(uid=req.uid, start_date=req.start_date, end_date=req.end_date, status="pending")
    db.add(query)
    await db.commit()
    await db.refresh(query)

    track_task(run_fetch(query.id, req.uid, req.start_date, req.end_date, sessdata, proxy_urls=proxy_urls))
    return FetchResponse(query_id=query.id, uid=req.uid, status="pending")
