# backend/app/api/settings.py
import logging

from cryptography.fernet import InvalidToken
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.security import decrypt_value, encrypt_value
from app.models import AppSettings
from app.schemas.settings import (
    AiTestRequest,
    SessdataTestRequest,
    SettingsResponse,
    SettingsUpdate,
)
from app.services.bilibili import BilibiliClient

logger = logging.getLogger(__name__)

router = APIRouter()

DECRYPT_ERROR_MESSAGE = "Stored credential could not be decrypted — re-enter it in Settings"

# proxy_list is included because proxy URLs routinely embed credentials
# (http://user:pass@host:port), so it is encrypted and masked like the others.
SENSITIVE_KEYS = {"ai_api_key", "sessdata", "proxy_list"}
MASK = "***"

DEFAULTS = {
    "sessdata": "",
    "ai_base_url": "https://api.openai.com/v1",
    "ai_api_key": "",
    "ai_model": "gpt-4o",
    "proxy_list": "",
    "refresh_window_size": "40",
}


async def _get_setting(db: AsyncSession, key: str) -> str:
    row = await db.get(AppSettings, key)
    if not row:
        return DEFAULTS.get(key, "")
    if row.is_sensitive and row.value:
        return MASK
    return row.value


async def _set_setting(db: AsyncSession, key: str, value: str):
    if value == MASK:
        return  # Skip masked values
    is_sensitive = key in SENSITIVE_KEYS
    row = await db.get(AppSettings, key)
    if row:
        row.value = encrypt_value(value) if is_sensitive and value else value
        row.is_sensitive = is_sensitive
    else:
        db.add(AppSettings(
            key=key,
            value=encrypt_value(value) if is_sensitive and value else value,
            is_sensitive=is_sensitive,
        ))


async def _get_raw_setting(db: AsyncSession, key: str) -> str:
    row = await db.get(AppSettings, key)
    if not row or not row.value:
        return DEFAULTS.get(key, "")
    if row.is_sensitive:
        try:
            return decrypt_value(row.value)
        except InvalidToken:
            logger.warning("Failed to decrypt setting %r; SECRET_KEY may have been rotated", key)
            raise HTTPException(status_code=400, detail=DECRYPT_ERROR_MESSAGE)
    return row.value


async def _get_refresh_window_size(db: AsyncSession) -> int:
    try:
        value = int(await _get_setting(db, "refresh_window_size"))
    except (TypeError, ValueError):
        value = 40
    return min(50, max(30, value))


@router.get("/settings", response_model=SettingsResponse)
async def get_settings(db: AsyncSession = Depends(get_db)):
    return SettingsResponse(
        sessdata=await _get_setting(db, "sessdata"),
        ai_base_url=await _get_setting(db, "ai_base_url"),
        ai_api_key=await _get_setting(db, "ai_api_key"),
        ai_model=await _get_setting(db, "ai_model"),
        proxy_list=await _get_setting(db, "proxy_list"),
        refresh_window_size=await _get_refresh_window_size(db),
    )


@router.put("/settings", response_model=SettingsResponse)
async def update_settings(data: SettingsUpdate, db: AsyncSession = Depends(get_db)):
    if data.sessdata is not None:
        await _set_setting(db, "sessdata", data.sessdata)
    if data.ai_base_url is not None:
        await _set_setting(db, "ai_base_url", data.ai_base_url)
    if data.ai_api_key is not None:
        await _set_setting(db, "ai_api_key", data.ai_api_key)
    if data.ai_model is not None:
        await _set_setting(db, "ai_model", data.ai_model)
    if data.proxy_list is not None:
        await _set_setting(db, "proxy_list", data.proxy_list)
    if data.refresh_window_size is not None:
        await _set_setting(
            db,
            "refresh_window_size",
            str(data.refresh_window_size),
        )
    await db.commit()
    return await get_settings(db)


@router.post("/settings/test-sessdata")
async def test_sessdata_connection(data: SessdataTestRequest, db: AsyncSession = Depends(get_db)):
    sessdata = data.sessdata
    if sessdata == MASK:
        sessdata = await _get_raw_setting(db, "sessdata")

    if sessdata is None:
        sessdata = await _get_raw_setting(db, "sessdata")

    if not sessdata:
        return {"status": "error", "message": "SESSDATA not configured"}

    client = BilibiliClient(sessdata=sessdata)
    try:
        result = await client.validate_sessdata()
        uname = result.get("uname")
        return {"status": "ok", "message": f"Connected as {uname}" if uname else "SESSDATA is valid"}
    except Exception:
        logger.exception("SESSDATA validation failed")
        return {"status": "error", "message": "Failed to validate SESSDATA. Check server logs for details."}
    finally:
        await client.aclose()


@router.post("/settings/test-ai")
async def test_ai_connection(data: AiTestRequest, db: AsyncSession = Depends(get_db)):
    from openai import AsyncOpenAI

    base_url = data.ai_base_url if data.ai_base_url is not None else await _get_raw_setting(db, "ai_base_url")
    api_key = data.ai_api_key
    model = data.ai_model if data.ai_model is not None else await _get_raw_setting(db, "ai_model")

    if api_key == MASK or api_key is None:
        api_key = await _get_raw_setting(db, "ai_api_key")

    if not api_key:
        return {"status": "error", "message": "API key not configured"}

    try:
        client = AsyncOpenAI(base_url=base_url, api_key=api_key)
        await client.chat.completions.create(
            model=model, messages=[{"role": "user", "content": "Say OK"}], max_tokens=5
        )
        return {"status": "ok", "model": model}
    except Exception:
        logger.exception("AI connection test failed")
        return {"status": "error", "message": "Failed to connect to the AI provider. Check server logs for details."}
