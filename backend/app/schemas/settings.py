from typing import Literal

from pydantic import BaseModel


class SettingsResponse(BaseModel):
    sessdata: str  # masked if set
    ai_base_url: str
    ai_api_key: str  # masked if set
    ai_model: str
    proxy_list: str
    maintenance_mode: Literal["windowed", "unlimited"]


class SettingsUpdate(BaseModel):
    sessdata: str | None = None
    ai_base_url: str | None = None
    ai_api_key: str | None = None
    ai_model: str | None = None
    proxy_list: str | None = None
    maintenance_mode: Literal["windowed", "unlimited"] | None = None


class SessdataTestRequest(BaseModel):
    sessdata: str | None = None


class AiTestRequest(BaseModel):
    ai_base_url: str | None = None
    ai_api_key: str | None = None
    ai_model: str | None = None
