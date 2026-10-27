from pydantic import BaseModel, Field


class SettingsResponse(BaseModel):
    sessdata: str  # masked if set
    ai_base_url: str
    ai_api_key: str  # masked if set
    ai_model: str
    proxy_list: str
    refresh_window_size: int


class SettingsUpdate(BaseModel):
    sessdata: str | None = None
    ai_base_url: str | None = None
    ai_api_key: str | None = None
    ai_model: str | None = None
    proxy_list: str | None = None
    refresh_window_size: int | None = Field(default=None, ge=30, le=50)


class SessdataTestRequest(BaseModel):
    sessdata: str | None = None


class AiTestRequest(BaseModel):
    ai_base_url: str | None = None
    ai_api_key: str | None = None
    ai_model: str | None = None
