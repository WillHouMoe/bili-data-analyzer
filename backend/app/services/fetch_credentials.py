from cryptography.fernet import InvalidToken
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decrypt_value
from app.models import AppSettings


class FetchCredentialError(ValueError):
    pass


def decrypt_setting(row: AppSettings | None) -> str | None:
    if not row or not row.value:
        return None
    if not row.is_sensitive:
        return row.value
    try:
        return decrypt_value(row.value)
    except InvalidToken as exc:
        raise FetchCredentialError(
            "Stored credential could not be decrypted — re-enter it in Settings"
        ) from exc


async def load_fetch_credentials(
    db: AsyncSession,
) -> tuple[str | None, list[str]]:
    sessdata = decrypt_setting(await db.get(AppSettings, "sessdata"))
    proxy_value = decrypt_setting(await db.get(AppSettings, "proxy_list"))
    proxy_urls = [
        url.strip()
        for url in (proxy_value or "").splitlines()
        if url.strip()
    ]
    return sessdata, proxy_urls
